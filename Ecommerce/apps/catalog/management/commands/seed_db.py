from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.catalog.models import Category, Product

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with an admin user, sample categories (with hierarchy), and products.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # 1. Create Admin User
        admin_email = 'admin@ecomricco.com'
        admin_username = 'admin'
        admin_password = 'adminpassword123'
        
        if not User.objects.filter(email=admin_email).exists():
            User.objects.create_superuser(
                email=admin_email,
                username=admin_username,
                password=admin_password,
                first_name='Ecom',
                last_name='Admin'
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser created: {admin_email} / {admin_password}"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser {admin_email} already exists."))

        # 2. Create Categories (with hierarchy)
        # Root categories
        electronics, _ = Category.objects.get_or_create(name='Electronics')
        apparel, _ = Category.objects.get_or_create(name='Apparel')
        home_kitchen, _ = Category.objects.get_or_create(name='Home & Kitchen')
        books, _ = Category.objects.get_or_create(name='Books')

        # Subcategories
        smartphones, _ = Category.objects.get_or_create(name='Smartphones', parent=electronics)
        laptops, _ = Category.objects.get_or_create(name='Laptops', parent=electronics)
        menswear, _ = Category.objects.get_or_create(name='Menswear', parent=apparel)
        womenswear, _ = Category.objects.get_or_create(name='Womenswear', parent=apparel)
        appliances, _ = Category.objects.get_or_create(name='Appliances', parent=home_kitchen)
        fiction, _ = Category.objects.get_or_create(name='Fiction', parent=books)

        #sub-subcategories
        gaming_laptops, _ = Category.objects.get_or_create(name='Gaming Laptops', parent=laptops)
        business_laptops, _ = Category.objects.get_or_create(name='Business Laptops', parent=laptops)

        self.stdout.write(self.style.SUCCESS("Categories and hierarchy created/updated."))

        # 3. Create Sample Products
        products_data = [
            {
                'sku': 'IPHONE15PRO',
                'name': 'iPhone 15 Pro',
                'description': 'Latest iPhone with Titanium build and A17 Pro chip.',
                'price': 999.99,
                'stock': 50,
                'status': 'active',
                'category': smartphones
            },
            {
                'sku': 'GALS24ULTRA',
                'name': 'Samsung Galaxy S24 Ultra',
                'description': 'AI-powered flagship smartphone with S Pen.',
                'price': 1199.99,
                'stock': 30,
                'status': 'active',
                'category': smartphones
            },
            {
                'sku': 'MBP16M3MAX',
                'name': 'MacBook Pro 16 M3 Max',
                'description': 'Ultimate developer laptop with 16-inch Liquid Retina XDR display.',
                'price': 3499.99,
                'stock': 10,
                'status': 'active',
                'category': laptops
            },

            {
                'sku': 'HpGamming',
                'name': 'HP Omen Gaming Laptop',
                'description': 'High-performance gaming laptop with powerful graphics.',
                'price': 1299.99,
                'stock': 10,
                'status': 'active',
                'category': gaming_laptops
            },
            {
                'sku': 'HpBusiness',
                'name': 'HP Omen Business Laptop',
                'description': 'Professional laptop with reliable performance.',
                'price': 1299.99,
                'stock': 10,
                'status': 'active',
                'category': business_laptops
            },


            {
                'sku': 'MBP16M3MAX23',
                'name': 'MacBook Pro 16 M5 Max 23',
                'description': 'Ultimate developer laptop with 16-inch Liquid Retina XDR display.',
                'price': 34155.99,
                'stock': 10,
                'status': 'active',
                'category': laptops
            },
            {
                'sku': 'DELLXPS15',
                'name': 'Dell XPS 15',
                'description': 'Premium Windows laptop with 4K OLED display.',
                'price': 1999.99,
                'stock': 15,
                'status': 'active',
                'category': laptops
            },
            {
                'sku': 'NIKERUNSHOE',
                'name': 'Nike Air Zoom Running Shoes',
                'description': 'Comfortable and lightweight performance running shoes.',
                'price': 120.00,
                'stock': 80,
                'status': 'active',
                'category': menswear
            },
            {
                'sku': 'LEVIS501JEAN',
                'name': 'Levis 501 Original Jeans',
                'description': 'Classic straight fit denim jeans.',
                'price': 69.99,
                'stock': 120,
                'status': 'active',
                'category': menswear
            },
            {
                'sku': 'ZARATRENCH',
                'name': 'Zara Trench Coat',
                'description': 'Classic double-breasted trench coat for women.',
                'price': 149.00,
                'stock': 40,
                'status': 'active',
                'category': womenswear
            },
            {
                'sku': 'SUMMERDRESS',
                'name': 'Floral Summer Dress',
                'description': 'Lightweight flowy floral print dress.',
                'price': 45.50,
                'stock': 60,
                'status': 'active',
                'category': womenswear
            },
            {
                'sku': 'COSORIAP',
                'name': 'Cosori Air Fryer Pro',
                'description': '5.8-quart smart air fryer with 11 presets.',
                'price': 119.99,
                'stock': 25,
                'status': 'active',
                'category': appliances
            },
            {
                'sku': 'KEURIGKMINI',
                'name': 'Keurig K-Mini Coffee Maker',
                'description': 'Single serve K-Cup pod coffee brewer.',
                'price': 79.99,
                'stock': 35,
                'status': 'active',
                'category': appliances
            },
            {
                'sku': 'THEHOBBIT',
                'name': 'The Hobbit',
                'description': 'Classic fantasy novel by J.R.R. Tolkien.',
                'price': 14.99,
                'stock': 100,
                'status': 'active',
                'category': fiction
            },
            {
                'sku': 'GREATGATSBY',
                'name': 'The Great Gatsby',
                'description': 'F. Scott Fitzgerald masterpiece novel.',
                'price': 9.99,
                'stock': 150,
                'status': 'active',
                'category': fiction
            },
            {
                'sku': 'INACTIVEPROD',
                'name': 'Discontinued Phone',
                'description': 'An old product that is no longer sold.',
                'price': 199.99,
                'stock': 0,
                'status': 'inactive',
                'category': smartphones
            }
        ]

        for p_info in products_data:
            prod, created = Product.objects.update_or_create(
                sku=p_info['sku'],
                defaults={
                    'name': p_info['name'],
                    'description': p_info['description'],
                    'price': p_info['price'],
                    'stock': p_info['stock'],
                    'status': p_info['status'],
                    'category': p_info['category']
                }
            )
            if created:
                self.stdout.write(f"Product created: {prod.name} ({prod.sku})")
            else:
                self.stdout.write(f"Product updated: {prod.name} ({prod.sku})")

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully."))
