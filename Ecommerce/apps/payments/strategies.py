import logging
import uuid
import requests
import stripe
from abc import ABC, abstractmethod
from django.conf import settings

logger = logging.getLogger(__name__)

class BasePaymentStrategy(ABC):
    @abstractmethod
    def initiate_payment(self, order, **kwargs) -> dict:
        """
        Initiate a payment transaction.
        Returns:
            dict: {
                'transaction_id': str,
                'status': 'pending' | 'success' | 'failed',
                'payment_url': str (optional),
                'client_secret': str (optional),
                'raw_response': dict
            }
        """
        pass

    @abstractmethod
    def execute_payment(self, payment, **kwargs) -> dict:
        """
        Execute or confirm an initiated payment.
        Returns:
            dict: {
                'status': 'pending' | 'success' | 'failed',
                'raw_response': dict
            }
        """
        pass

    @abstractmethod
    def query_payment(self, transaction_id) -> dict:
        """
        Query the status of a payment transaction from the provider.
        Returns:
            dict: {
                'status': 'pending' | 'success' | 'failed',
                'raw_response': dict
            }
        """
        pass


class StripePaymentStrategy(BasePaymentStrategy):
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def is_placeholder_key(self):
        return not settings.STRIPE_SECRET_KEY or "placeholder" in settings.STRIPE_SECRET_KEY

    def initiate_payment(self, order, **kwargs) -> dict:
        amount_cents = int(order.total_amount * 100)
        
        if self.is_placeholder_key():
            # Mock mode
            tx_id = f"mock_pi_{uuid.uuid4().hex[:16]}"
            logger.info(f"[Stripe Mock] Initiating payment for Order #{order.id}, amount={order.total_amount}")
            return {
                'transaction_id': tx_id,
                'status': 'pending',
                'payment_url': f"https://checkout.stripe.com/pay/{tx_id}",
                'client_secret': f"{tx_id}_secret_{uuid.uuid4().hex[:8]}",
                'raw_response': {'mock': True, 'amount': amount_cents, 'id': tx_id}
            }

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                metadata={'order_id': order.id},
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'
                }
            )
            return {
                'transaction_id': intent.id,
                'status': 'pending',
                'client_secret': intent.client_secret,
                'raw_response': intent.to_dict()
            }
        except Exception as e:
            logger.error(f"Stripe initiate_payment failed: {e}")
            raise ValueError(f"Stripe payment initiation error: {str(e)}")

    def execute_payment(self, payment, **kwargs) -> dict:
        # Stripe is typically confirmed client-side. 
        # But if confirming server-side, or simulating a test success:
        if self.is_placeholder_key() or payment.transaction_id.startswith('mock_pi_'):
            logger.info(f"[Stripe Mock] Executing/Confirming payment for Order #{payment.order.id}")
            return {
                'status': 'success',
                'raw_response': {'mock': True, 'status': 'succeeded', 'id': payment.transaction_id}
            }

        try:
            intent = stripe.PaymentIntent.confirm(
                payment.transaction_id,
                payment_method='pm_card_visa'
            )
            status_map = {
                'succeeded': 'success',
                'requires_payment_method': 'pending',
                'requires_confirmation': 'pending',
                'requires_action': 'pending',
                'processing': 'pending',
                'canceled': 'failed',
            }
            return {
                'status': status_map.get(intent.status, 'failed'),
                'raw_response': intent.to_dict()
            }
        except Exception as e:
            logger.error(f"Stripe execute_payment failed: {e}")
            return {
                'status': 'failed',
                'raw_response': {'error': str(e)}
            }

    def query_payment(self, transaction_id) -> dict:
        if self.is_placeholder_key() or transaction_id.startswith('mock_pi_'):
            return {
                'status': 'success',
                'raw_response': {'mock': True, 'status': 'succeeded', 'id': transaction_id}
            }

        try:
            intent = stripe.PaymentIntent.retrieve(transaction_id)
            status_map = {
                'succeeded': 'success',
                'requires_payment_method': 'pending',
                'requires_confirmation': 'pending',
                'requires_action': 'pending',
                'processing': 'pending',
                'canceled': 'failed',
            }
            return {
                'status': status_map.get(intent.status, 'failed'),
                'raw_response': intent.to_dict()
            }
        except Exception as e:
            logger.error(f"Stripe query_payment failed: {e}")
            return {
                'status': 'failed',
                'raw_response': {'error': str(e)}
            }


class BkashPaymentStrategy(BasePaymentStrategy):
    def is_placeholder_key(self):
        return not settings.BKASH_APP_KEY or "placeholder" in settings.BKASH_APP_KEY

    def _get_token(self) -> str:
        url = f"{settings.BKASH_BASE_URL}/checkout/token/grant"
        headers = {
            "Content-Type": "application/json",
            "username": settings.BKASH_USERNAME,
            "password": settings.BKASH_PASSWORD
        }
        body = {
            "app_key": settings.BKASH_APP_KEY,
            "app_secret": settings.BKASH_APP_SECRET
        }
        
        response = requests.post(url, json=body, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['id_token']

    def initiate_payment(self, order, **kwargs) -> dict:
        if self.is_placeholder_key():
            # Mock mode
            tx_id = f"mock_bkash_{uuid.uuid4().hex[:16]}"
            logger.info(f"[bKash Mock] Initiating payment for Order #{order.id}, amount={order.total_amount}")
            return {
                'transaction_id': tx_id,
                'status': 'pending',
                'payment_url': f"https://sandbox.bkash.com/checkout?paymentID={tx_id}",
                'raw_response': {'mock': True, 'amount': str(order.total_amount), 'paymentID': tx_id}
            }

        try:
            token = self._get_token()
            url = f"{settings.BKASH_BASE_URL}/checkout/create"
            headers = {
                "Content-Type": "application/json",
                "Authorization": token,
                "X-APP-Key": settings.BKASH_APP_KEY
            }
            body = {
                "mode": "0011",
                "payerReference": str(order.user.id),
                "callbackURL": kwargs.get('callback_url', "http://localhost:8000/api/payments/webhook/bkash/"),
                "amount": str(order.total_amount),
                "currency": "BDT",
                "intent": "sale",
                "merchantInvoiceNumber": f"INV{order.id}T{uuid.uuid4().hex[:6].upper()}"
            }
            
            response = requests.post(url, json=body, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Check for errors in statusCode or errorCode
            status_code = data.get('statusCode')
            if status_code and status_code != '0000':
                raise ValueError(f"bKash Error {status_code}: {data.get('statusMessage')}")
            if 'errorCode' in data:
                raise ValueError(f"bKash Error {data.get('errorCode')}: {data.get('errorMessage')}")
                
            return {
                'transaction_id': data['paymentID'],
                'status': 'pending',
                'payment_url': data['bkashURL'],
                'raw_response': data
            }
        except Exception as e:
            logger.error(f"bKash initiate_payment failed: {e}")
            raise ValueError(f"bKash payment initiation error: {str(e)}")

    def execute_payment(self, payment, **kwargs) -> dict:
        if self.is_placeholder_key() or payment.transaction_id.startswith('mock_bkash_'):
            logger.info(f"[bKash Mock] Executing payment for Order #{payment.order.id}")
            return {
                'status': 'success',
                'raw_response': {'mock': True, 'transactionStatus': 'Completed', 'paymentID': payment.transaction_id}
            }

        try:
            token = self._get_token()
            url = f"{settings.BKASH_BASE_URL}/checkout/execute"
            headers = {
                "Content-Type": "application/json",
                "Authorization": token,
                "X-APP-Key": settings.BKASH_APP_KEY
            }
            body = {
                "paymentID": payment.transaction_id
            }
            
            response = requests.post(url, json=body, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            status_code = data.get('statusCode')
            if (status_code and status_code != '0000') or 'errorCode' in data:
                return {
                    'status': 'failed',
                    'raw_response': data
                }
                
            tx_status = data.get('transactionStatus')
            status = 'success' if tx_status == 'Completed' else 'pending' if tx_status == 'Initiated' else 'failed'
            
            return {
                'status': status,
                'raw_response': data
            }
        except Exception as e:
            logger.error(f"bKash execute_payment failed: {e}")
            return {
                'status': 'failed',
                'raw_response': {'error': str(e)}
            }

    def query_payment(self, transaction_id) -> dict:
        if self.is_placeholder_key() or transaction_id.startswith('mock_bkash_'):
            return {
                'status': 'success',
                'raw_response': {'mock': True, 'transactionStatus': 'Completed', 'paymentID': transaction_id}
            }

        try:
            token = self._get_token()
            url = f"{settings.BKASH_BASE_URL}/checkout/payment/status"
            headers = {
                "Content-Type": "application/json",
                "Authorization": token,
                "X-APP-Key": settings.BKASH_APP_KEY
            }
            body = {
                "paymentID": transaction_id
            }
            
            response = requests.post(url, json=body, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            status_code = data.get('statusCode')
            if (status_code and status_code != '0000') or 'errorCode' in data:
                return {
                    'status': 'failed',
                    'raw_response': data
                }
                
            tx_status = data.get('transactionStatus')
            status = 'success' if tx_status == 'Completed' else 'pending' if tx_status == 'Initiated' else 'failed'
            
            return {
                'status': status,
                'raw_response': data
            }
        except Exception as e:
            logger.error(f"bKash query_payment failed: {e}")
            return {
                'status': 'failed',
                'raw_response': {'error': str(e)}
            }


class PaymentContext:
    """
    Context class that uses a selected BasePaymentStrategy to execute operations.
    """
    def __init__(self, provider: str):
        self.provider = provider.lower()
        if self.provider == 'stripe':
            self.strategy = StripePaymentStrategy()
        elif self.provider == 'bkash':
            self.strategy = BkashPaymentStrategy()
        else:
            raise ValueError(f"Unsupported payment provider: {provider}")

    def initiate(self, order, **kwargs) -> dict:
        return self.strategy.initiate_payment(order, **kwargs)

    def execute(self, payment, **kwargs) -> dict:
        return self.strategy.execute_payment(payment, **kwargs)

    def query(self, transaction_id) -> dict:
        return self.strategy.query_payment(transaction_id)
