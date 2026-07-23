from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import CoinTransaction, Seller, User

from .models import Cart, CartItem, Category, Order, Product, Transaction, WalletChargeRequest
from .views import CHECKOUT_COINS_SESSION_KEY


class BazarModelTests(TestCase):
    def test_product_final_price_with_discount(self):
        buyer = User.objects.create_user(
            phone_number="09120000001",
            password="StrongPass123!",
            first_name="خریدار",
            last_name="تست",
        )
        seller_user = User.objects.create_user(
            phone_number="09120000002",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="تست",
        )
        seller = Seller.objects.create(
            user=seller_user,
            shop_name="فروشگاه تست",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
        )
        category = Category.objects.create(name="کتاب")
        product = Product.objects.create(
            seller=seller,
            category=category,
            title="کتاب تست",
            description="توضیحات",
            price=100000,
            stock=3,
            discount_percent=20,
            discount_active=True,
        )

        self.assertEqual(product.final_price, 80000)
        self.assertEqual(str(buyer), "خریدار تست")


class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09123334444",
            password="StrongPass123!",
            first_name="علی",
            last_name="خریدار",
            challenge_coins=60000,
        )
        self.seller_user = User.objects.create_user(
            phone_number="09125556666",
            password="StrongPass123!",
            first_name="رضا",
            last_name="فروشنده",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه آموزشی",
            shop_address="قم",
            platform_commission_percent=Decimal("15.00"),
        )
        self.category = Category.objects.create(name="دوره")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="دوره مهارتی",
            description="توضیح کامل",
            price=50000,
            stock=4,
            discount_percent=10,
            discount_active=True,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.force_login(self.user)

    def test_pay_view_completes_order_with_only_coins(self):
        session = self.client.session
        session[CHECKOUT_COINS_SESSION_KEY] = 45000
        session.save()

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()
        self.user.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(order.total_amount, 45000)
        self.assertEqual(order.coins_used, 45000)
        self.assertEqual(order.wallet_used, 0)
        self.assertEqual(order.online_paid, 0)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self.user.challenge_coins, 15000)
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.cart.items.count(), 0)
        self.assertEqual(Transaction.objects.filter(transaction_type=Transaction.TransactionType.PURCHASE).count(), 1)
        self.assertEqual(Transaction.objects.filter(transaction_type=Transaction.TransactionType.COMMISSION).count(), 1)

    def test_pay_view_shows_shortage_when_coins_are_not_enough(self):
        self.user.challenge_coins = 10000
        self.user.save(update_fields=["challenge_coins"])

        session = self.client.session
        session[CHECKOUT_COINS_SESSION_KEY] = 5000
        session.save()

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اعتبار سکه شما برای این سفارش کافی نیست")
        self.assertContains(response, "۴۰,۰۰۰")
        self.assertEqual(Order.objects.count(), 0)


class WalletChargeRequestTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09128889999",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="درخواست",
            challenge_coins=1000,
        )
        self.client.force_login(self.user)

    def test_wallet_charge_view_creates_manual_request(self):
        response = self.client.post(reverse("bazar:wallet-charge"), {"amount": 25000})

        self.assertRedirects(response, reverse("bazar:wallet-charge"))
        self.assertEqual(WalletChargeRequest.objects.count(), 1)

        charge_request = WalletChargeRequest.objects.get()
        self.assertEqual(charge_request.user, self.user)
        self.assertEqual(charge_request.requested_amount, 25000)
        self.assertEqual(charge_request.requested_coins, 25000)
        self.assertEqual(charge_request.status, WalletChargeRequest.Status.PENDING)

    def test_completing_request_grants_coins_once(self):
        charge_request = WalletChargeRequest.objects.create(
            user=self.user,
            requested_amount=15000,
            requested_coins=15000,
        )

        charge_request.status = WalletChargeRequest.Status.COMPLETED
        charge_request.granted_coins = 12000
        charge_request.save()
        charge_request.save()

        self.user.refresh_from_db()
        charge_request.refresh_from_db()

        self.assertEqual(self.user.challenge_coins, 13000)
        self.assertIsNotNone(charge_request.coins_granted_at)
        self.assertEqual(
            CoinTransaction.objects.filter(challenge=f"bazar-charge-request-{charge_request.pk}").count(),
            1,
        )


class ProductListFilteringTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09127770000",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="بازار",
        )
        self.seller_user = User.objects.create_user(
            phone_number="09127770001",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="بازار",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="مرکز خدمات",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
        )
        self.restaurant = Category.objects.create(name="رستوران")
        self.fast_food = Category.objects.create(name="فست فود", parent=self.restaurant)
        self.shop = Category.objects.create(name="فروشگاه")
        self.client.force_login(self.user)

    def test_top_category_filter_limits_results_to_selected_group(self):
        restaurant_product = Product.objects.create(
            seller=self.seller,
            category=self.fast_food,
            title="پیتزا ویژه",
            description="غذای گرم",
            price=120000,
            stock=5,
        )
        Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="دفتر برنامه ریزی",
            description="لوازم تحریر",
            price=50000,
            stock=8,
        )

        response = self.client.get(reverse("bazar:product-list"), {"top": self.restaurant.slug})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, restaurant_product.title)
        self.assertNotContains(response, "دفتر برنامه ریزی")
        self.assertEqual(response.context["selected_top_category"], self.restaurant)

    def test_discount_filter_and_cheap_sort_use_final_price(self):
        cheaper_discounted = Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="دفتر اقتصادی",
            description="محصول اول",
            price=100000,
            stock=4,
            discount_percent=50,
            discount_active=True,
        )
        expensive_discounted = Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="بسته کامل لوازم",
            description="محصول دوم",
            price=180000,
            stock=3,
            discount_percent=20,
            discount_active=True,
        )
        Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="محصول بدون تخفیف",
            description="محصول سوم",
            price=20000,
            stock=2,
            discount_percent=0,
            discount_active=False,
        )

        response = self.client.get(
            reverse("bazar:product-list"),
            {"discount": "1", "sort": "cheap"},
        )

        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual([product.title for product in products], [cheaper_discounted.title, expensive_discounted.title])
