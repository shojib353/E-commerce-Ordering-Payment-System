import json
import logging
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.orders.models import Order
from apps.orders.services import process_payment_success, process_payment_failure
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer, PaymentInitiateSerializer, PaymentExecuteSerializer
from apps.payments.strategies import PaymentContext

logger = logging.getLogger(__name__)

class PaymentInitiateView(generics.GenericAPIView):
    serializer_class = PaymentInitiateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order_id = serializer.validated_data['order_id']
        provider = serializer.validated_data['provider']
        
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
            
        if order.status != 'pending':
            return Response({'error': f'Order is already {order.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        # Call payment strategy
        try:
            context = PaymentContext(provider)
            callback_url = request.build_absolute_uri('/api/payments/webhook/bkash/')
            init_data = context.initiate(order, callback_url=callback_url)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Save payment transaction
        # If there's an existing pending payment for this order/provider, we can update or create a new one.
        # We will create a new Payment record.
        payment = Payment.objects.create(
            order=order,
            provider=provider,
            transaction_id=init_data['transaction_id'],
            status=init_data['status'],
            raw_response=init_data['raw_response']
        )

        response_data = {
            'payment_id': payment.id,
            'provider': provider,
            'transaction_id': payment.transaction_id,
            'status': payment.status,
            'payment_url': init_data.get('payment_url'),
            'client_secret': init_data.get('client_secret')
        }

        # If payment is already success (e.g. mock instant success)
        if payment.status == 'success':
            process_payment_success(payment.id)
            response_data['status'] = 'success'

        return Response(response_data, status=status.HTTP_201_CREATED)


class PaymentExecuteView(generics.GenericAPIView):
    serializer_class = PaymentExecuteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment_id = serializer.validated_data['payment_id']
        
        try:
            payment = Payment.objects.get(id=payment_id, order__user=request.user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if payment.status in ['success', 'failed']:
            return Response({
                'payment_id': payment.id,
                'status': payment.status,
                'message': f'Payment has already been processed as {payment.status}.'
            })

        # Execute payment via Strategy
        try:
            context = PaymentContext(payment.provider)
            exec_data = context.execute(payment)
            
            payment.raw_response = exec_data.get('raw_response', payment.raw_response)
            payment.save()
            
            status_val = exec_data['status']
            if status_val == 'success':
                process_payment_success(payment.id)
            elif status_val == 'failed':
                process_payment_failure(payment.id)
            else:
                payment.status = 'pending'
                payment.save()
                
            # Reload from DB to get the status updated by the success/failure processor
            payment.refresh_from_db()
            
            return Response({
                'payment_id': payment.id,
                'status': payment.status,
                'raw_response': payment.raw_response
            })
        except Exception as e:
            logger.error(f"Error executing payment #{payment_id}: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        # Fallback to direct json loading if webhook secret is placeholder
        # This makes local testing and API mocking easy!
        if not sig_header or settings.STRIPE_WEBHOOK_SECRET == 'whsec_placeholder':
            try:
                event = json.loads(payload.decode('utf-8'))
                logger.info("[Stripe Webhook Sandbox] Loaded webhook event payload directly.")
            except Exception as e:
                return Response({'error': f'Invalid payload: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
                )
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"Stripe Webhook Signature verification failed: {e}")
                return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get('type')
        data_object = event.get('data', {}).get('object', {})
        payment_intent_id = data_object.get('id')

        if not payment_intent_id:
            return Response({'message': 'PaymentIntent  received, but no payment intent ID found.'})

        try:
            payment = Payment.objects.get(transaction_id=payment_intent_id, provider='stripe')
        except Payment.DoesNotExist:
            logger.warning(f"Payment for transaction_id {payment_intent_id} not found in database.")
            return Response({'message': 'Payment intent not found'}, status=status.HTTP_200_OK)

        if event_type == 'payment_intent.succeeded':
            process_payment_success(payment.id)
        elif event_type in ['payment_intent.payment_failed', 'payment_intent.canceled']:
            process_payment_failure(payment.id)

        return Response({'status': 'success'}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class BkashWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        # bKash webhook handles callbacks or notifications
        payment_id = request.data.get('paymentID')
        status_val = request.data.get('status')
        
        if not payment_id:
            return Response({'error': 'Missing paymentID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(transaction_id=payment_id, provider='bkash')
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        if status_val == 'success':
            # Run query to verify status securely
            try:
                context = PaymentContext('bkash')
                query_data = context.query(payment.transaction_id)
                payment.raw_response = query_data.get('raw_response', payment.raw_response)
                
                if query_data['status'] == 'success':
                    process_payment_success(payment.id)
                else:
                    process_payment_failure(payment.id)
            except Exception as e:
                logger.error(f"Error querying bKash payment: {e}")
                process_payment_failure(payment.id)
        else:
            process_payment_failure(payment.id)

        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        # Handle GET redirect fallback callback from bKash checkout
        payment_id = request.query_params.get('paymentID')
        status_val = request.query_params.get('status')

        if not payment_id or not status_val:
            return Response({'error': 'Missing parameters'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(transaction_id=payment_id, provider='bkash')
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        if status_val == 'success':
            try:
                context = PaymentContext('bkash')
                query_data = context.query(payment.transaction_id)
                payment.raw_response = query_data.get('raw_response', payment.raw_response)
                
                if query_data['status'] == 'success':
                    process_payment_success(payment.id)
                else:
                    process_payment_failure(payment.id)
            except Exception as e:
                logger.error(f"Error checking bKash payment: {e}")
                process_payment_failure(payment.id)
        else:
            process_payment_failure(payment.id)

        from django.shortcuts import redirect
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5500')
        return redirect(f"{frontend_url}/?payment_id={payment.id}&status={payment.status}")
