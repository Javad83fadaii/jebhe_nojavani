import io
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import CoinTransaction, Seller, User

from .admin import OrderAdmin
from .forms import ProductForm
from .models import Cart, CartItem, Category, Order, OrderItem, Product, Transaction, WalletChargeRequest


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


class CartInteractionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09121112222",
            password="StrongPass123!",
            first_name="مینا",
            last_name="خریدار",
        )
        self.seller_user = User.objects.create_user(
            phone_number="09123335555",
            password="StrongPass123!",
            first_name="سارا",
            last_name="فروشنده",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه سبد",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
        )
        self.category = Category.objects.create(name="محصولات سبد")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="محصول سبدی",
            description="توضیحات تست",
            price=120000,
            stock=4,
            discount_percent=25,
            discount_active=True,
        )
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.force_login(self.user)

    def test_update_cart_item_quantity_returns_updated_totals(self):
        response = self.client.post(
            reverse("bazar:cart-update-quantity", args=[self.cart_item.pk]),
            {"quantity": 3},
        )

        self.assertEqual(response.status_code, 200)
        self.cart_item.refresh_from_db()

        data = response.json()
        self.assertEqual(self.cart_item.quantity, 3)
        self.assertEqual(data["quantity"], 3)
        self.assertEqual(data["item_total"], self.product.final_price * 3)
        self.assertEqual(data["cart_total"], self.product.final_price * 3)
        self.assertEqual(data["cart_total_quantity"], 3)
        self.assertTrue(data["can_increment"])
        self.assertTrue(data["can_decrement"])

    def test_update_cart_item_quantity_rejects_more_than_stock(self):
        response = self.client.post(
            reverse("bazar:cart-update-quantity", args=[self.cart_item.pk]),
            {"quantity": 8},
        )

        self.assertEqual(response.status_code, 400)
        self.cart_item.refresh_from_db()

        data = response.json()
        self.assertEqual(self.cart_item.quantity, 1)
        self.assertEqual(data["quantity"], 1)
        self.assertEqual(data["stock"], 4)
        self.assertIn("موجودی", data["message"])

    def test_product_list_shows_cart_quick_link_and_quantity_badge(self):
        response = self.client.get(reverse("bazar:product-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("bazar:cart"))
        self.assertEqual(response.context["cart_total_quantity"], 1)
        self.assertTrue(response.context["cart_has_items"])

    def test_add_to_cart_invalid_quantity_does_not_raise_500(self):
        response = self.client.post(
            reverse("bazar:cart-add", args=[self.product.pk]),
            {"quantity": "abc"},
        )

        self.assertRedirects(response, reverse("bazar:cart"))
        self.cart_item.refresh_from_db()
        self.assertEqual(self.cart_item.quantity, 2)

    def test_add_to_cart_rejects_unsafe_next_redirect(self):
        response = self.client.post(
            reverse("bazar:cart-add", args=[self.product.pk]),
            {"quantity": 1, "next": "https://evil.example/phish"},
        )

        self.assertRedirects(response, reverse("bazar:cart"))

    def test_cart_view_invalid_item_id_does_not_raise_500(self):
        response = self.client.post(
            reverse("bazar:cart"),
            {"item_id": "abc", "quantity": 2},
        )

        self.assertRedirects(response, reverse("bazar:cart"))
        self.cart_item.refresh_from_db()
        self.assertEqual(self.cart_item.quantity, 1)

    def test_remove_from_cart_requires_post(self):
        get_response = self.client.get(reverse("bazar:cart-remove", args=[self.cart_item.pk]))

        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(CartItem.objects.filter(pk=self.cart_item.pk).exists())

        post_response = self.client.post(reverse("bazar:cart-remove", args=[self.cart_item.pk]))

        self.assertRedirects(post_response, reverse("bazar:cart"))
        self.assertFalse(CartItem.objects.filter(pk=self.cart_item.pk).exists())


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
        self.category, _ = Category.objects.get_or_create(name="دوره آموزشی")
        self.coin_product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="دوره سکه‌ای",
            description="توضیح کامل",
            price=50000,
            coin_price=50000,
            stock=4,
            discount_percent=10,
            discount_active=True,
            payment_method=Product.PaymentMethod.COIN,
        )
        self.money_product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="دوره نقدی",
            description="توضیح نقدی",
            price=30000,
            stock=5,
            payment_method=Product.PaymentMethod.MONEY,
        )
        self.flex_product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="محصول دو ارزی",
            description="برای تست تبدیل سکه",
            price=60000,
            coin_price=20000,
            stock=5,
            payment_method=Product.PaymentMethod.BOTH,
        )
        self.cart = Cart.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_pay_view_completes_order_with_only_coins(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.coin_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.COIN,
        )

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertRedirects(response, reverse("bazar:payment-result"))
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()
        self.user.refresh_from_db()
        self.coin_product.refresh_from_db()
        self.seller_user.refresh_from_db()
        self.seller.refresh_from_db()
        result_response = self.client.get(reverse("bazar:payment-result"))

        self.assertEqual(order.total_amount, 0)
        self.assertEqual(order.coins_used, 45000)
        self.assertEqual(order.wallet_used, 0)
        self.assertEqual(order.online_paid, 0)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self.user.challenge_coins, 15000)
        self.assertEqual(self.coin_product.stock, 3)
        self.assertEqual(self.cart.items.count(), 0)
        self.assertEqual(self.seller_user.wallet_balance, Decimal("38250"))
        self.assertEqual(self.seller.sales_count, 1)
        self.assertEqual(self.seller.total_revenue, Decimal("45000"))
        self.assertTrue(
            CoinTransaction.objects.filter(
                user=self.user,
                transaction_type=CoinTransaction.TransactionType.SPEND,
                amount=-45000,
            ).exists()
        )
        self.assertFalse(
            CoinTransaction.objects.filter(
                user=self.user,
                transaction_type=CoinTransaction.TransactionType.PENALTY,
                amount=-45000,
            ).exists()
        )
        self.assertEqual(
            Transaction.objects.filter(
                user=self.seller_user,
                transaction_type=Transaction.TransactionType.COMMISSION,
                amount=6750,
            ).count(),
            1,
        )
        self.assertEqual(
            Transaction.objects.filter(
                user=self.seller_user,
                transaction_type=Transaction.TransactionType.SETTLEMENT,
                amount=38250,
            ).count(),
            1,
        )
        self.assertContains(result_response, "پرداخت با سکه با موفقیت انجام شد")

    def test_pay_view_shows_shortage_when_coins_are_not_enough(self):
        self.user.challenge_coins = 10000
        self.user.save(update_fields=["challenge_coins"])

        CartItem.objects.create(
            cart=self.cart,
            product=self.coin_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.COIN,
        )

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertRedirects(response, reverse("bazar:payment-result"))
        result_response = self.client.get(reverse("bazar:payment-result"))
        self.assertContains(result_response, "موجودی سکه چالش شما برای این سفارش کافی نیست")
        self.assertContains(result_response, "۳۵,۰۰۰")
        self.assertEqual(Order.objects.count(), 0)

    def test_pay_view_completes_order_with_wallet_money(self):
        self.user.wallet_balance = Decimal("50000")
        self.user.save(update_fields=["wallet_balance"])

        CartItem.objects.create(
            cart=self.cart,
            product=self.money_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.MONEY,
        )

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertRedirects(response, reverse("bazar:payment-result"))
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()
        self.user.refresh_from_db()
        self.seller_user.refresh_from_db()
        self.seller.refresh_from_db()
        result_response = self.client.get(reverse("bazar:payment-result"))

        self.assertEqual(order.total_amount, 30000)
        self.assertEqual(order.wallet_used, 30000)
        self.assertEqual(order.coins_used, 0)
        self.assertEqual(self.user.wallet_balance, Decimal("20000"))
        self.assertEqual(self.seller_user.wallet_balance, Decimal("25500"))
        self.assertEqual(self.seller.sales_count, 1)
        self.assertEqual(self.seller.total_revenue, Decimal("30000"))
        self.assertContains(result_response, "پرداخت با کیف پول با موفقیت انجام شد")

    def test_pay_view_uses_coin_price_for_coin_settlement_and_commission(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.flex_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.COIN,
        )

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertRedirects(response, reverse("bazar:payment-result"))
        self.assertEqual(Order.objects.count(), 1)

        self.user.refresh_from_db()
        self.seller_user.refresh_from_db()
        self.seller.refresh_from_db()
        order_item = OrderItem.objects.get()

        self.assertEqual(order_item.paid_with, "coin")
        self.assertEqual(order_item.unit_price, 60000)
        self.assertEqual(order_item.unit_coins, 20000)
        self.assertEqual(order_item.seller_revenue_amount, 20000)
        self.assertEqual(order_item.seller_commission, 3000)
        self.assertEqual(order_item.seller_net_settlement, 17000)
        self.assertEqual(self.user.challenge_coins, 40000)
        self.assertEqual(self.seller_user.wallet_balance, Decimal("17000"))
        self.assertEqual(self.seller.sales_count, 1)
        self.assertEqual(self.seller.total_revenue, Decimal("20000"))
        self.assertEqual(
            Transaction.objects.filter(
                user=self.seller_user,
                transaction_type=Transaction.TransactionType.COMMISSION,
                amount=3000,
            ).count(),
            1,
        )
        self.assertEqual(
            Transaction.objects.filter(
                user=self.seller_user,
                transaction_type=Transaction.TransactionType.SETTLEMENT,
                amount=17000,
            ).count(),
            1,
        )

    def test_pay_view_shows_shortage_when_wallet_is_not_enough(self):
        self.user.wallet_balance = Decimal("10000")
        self.user.save(update_fields=["wallet_balance"])

        CartItem.objects.create(
            cart=self.cart,
            product=self.money_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.MONEY,
        )

        response = self.client.post(reverse("bazar:checkout-pay"))

        self.assertRedirects(response, reverse("bazar:payment-result"))
        result_response = self.client.get(reverse("bazar:payment-result"))
        self.assertContains(result_response, "موجودی کیف پول شما کافی نیست")
        self.assertContains(result_response, "۲۰,۰۰۰")
        self.assertEqual(Order.objects.count(), 0)

    def test_cancel_and_refund_restores_wallet_coins_stock_and_seller_totals(self):
        self.user.wallet_balance = Decimal("50000")
        self.user.save(update_fields=["wallet_balance"])
        CartItem.objects.create(
            cart=self.cart,
            product=self.coin_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.COIN,
        )
        CartItem.objects.create(
            cart=self.cart,
            product=self.money_product,
            quantity=1,
            selected_payment_method=CartItem.SelectedPaymentMethod.MONEY,
        )

        self.client.post(reverse("bazar:checkout-pay"))

        order = Order.objects.get()
        order.cancel_and_refund()

        order.refresh_from_db()
        self.user.refresh_from_db()
        self.seller_user.refresh_from_db()
        self.seller.refresh_from_db()
        self.coin_product.refresh_from_db()
        self.money_product.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.user.challenge_coins, 60000)
        self.assertEqual(self.user.wallet_balance, Decimal("50000"))
        self.assertEqual(self.seller_user.wallet_balance, Decimal("0"))
        self.assertEqual(self.seller.sales_count, 0)
        self.assertEqual(self.seller.total_revenue, Decimal("0"))
        self.assertEqual(self.coin_product.stock, 4)
        self.assertEqual(self.money_product.stock, 5)
        self.assertTrue(
            CoinTransaction.objects.filter(
                user=self.user,
                transaction_type=CoinTransaction.TransactionType.REFUND,
                amount=45000,
            ).exists()
        )
        self.assertTrue(
            Transaction.objects.filter(
                user=self.user,
                order=order,
                transaction_type=Transaction.TransactionType.REFUND,
                amount=30000,
            ).exists()
        )


class OrderAdminRefundTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.order_admin = OrderAdmin(Order, AdminSite())
        self.buyer = User.objects.create_user(
            phone_number="09127779990",
            password="StrongPass123!",
            first_name="خریدار",
            last_name="ادمین",
            wallet_balance=Decimal("0"),
        )
        self.seller_user = User.objects.create_user(
            phone_number="09127779991",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="ادمین",
            wallet_balance=Decimal("25500"),
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه تست ادمین",
            shop_address="تهران",
            platform_commission_percent=Decimal("15.00"),
            sales_count=1,
            total_revenue=Decimal("30000"),
        )
        self.category = Category.objects.create(name="تست ادمین بازار")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="محصول تست ادمین",
            description="برای تست لغو از ادمین",
            price=30000,
            stock=4,
            payment_method=Product.PaymentMethod.MONEY,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            total_amount=30000,
            wallet_used=30000,
            gateway_paid_amount=0,
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=30000,
            unit_coins=0,
            paid_with="money",
        )

    def test_model_cancel_and_refund_raises_when_seller_wallet_is_insufficient(self):
        self.seller_user.wallet_balance = Decimal("0")
        self.seller_user.save(update_fields=["wallet_balance"])

        with self.assertRaises(ValidationError):
            self.order.cancel_and_refund()

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_admin_save_model_catches_refund_validation_error(self):
        self.seller_user.wallet_balance = Decimal("0")
        self.seller_user.save(update_fields=["wallet_balance"])
        edited_order = Order.objects.get(pk=self.order.pk)
        edited_order.status = Order.Status.CANCELLED
        request = self.factory.post(f"/admin/jebhe_bazar/order/{self.order.pk}/change/")
        form = SimpleNamespace(changed_data=["status"])

        self.order_admin.save_model(request, edited_order, form, change=True)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIn("موجودی کیف پول فروشنده", request._bazar_order_admin_error_message)


class WalletChargeRequestTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number="09128889999",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="درخواست",
            challenge_coins=1000,
            wallet_balance=0,
        )
        self.client.force_login(self.user)

    def test_wallet_charge_view_creates_manual_request(self):
        response = self.client.post(reverse("bazar:wallet-charge"), {"amount": 25000})

        self.assertRedirects(response, reverse("bazar:wallet-charge"))
        self.assertEqual(WalletChargeRequest.objects.count(), 1)

        charge_request = WalletChargeRequest.objects.get()
        self.assertEqual(charge_request.user, self.user)
        self.assertEqual(charge_request.requested_amount, 25000)
        self.assertEqual(charge_request.requested_coins, 0)
        self.assertEqual(charge_request.status, WalletChargeRequest.Status.PENDING)

    def test_wallet_charge_view_invalid_amount_query_does_not_raise_500(self):
        response = self.client.get(f"{reverse('bazar:wallet-charge')}?amount=abc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["suggested_amount"], 0)

    def test_wallet_charge_view_rejects_unsafe_next_redirect(self):
        response = self.client.post(
            reverse("bazar:wallet-charge"),
            {"amount": 25000, "next": "https://evil.example/phish"},
        )

        self.assertRedirects(response, reverse("bazar:wallet-charge"))

    def test_completing_request_grants_wallet_balance_not_coins(self):
        charge_request = WalletChargeRequest.objects.create(
            user=self.user,
            requested_amount=15000,
            requested_coins=0,
        )

        charge_request.status = WalletChargeRequest.Status.COMPLETED
        charge_request.granted_amount = 15000
        charge_request.save()
        charge_request.save()

        self.user.refresh_from_db()
        charge_request.refresh_from_db()

        # Coins MUST NOT increase
        self.assertEqual(self.user.challenge_coins, 1000)
        # Wallet balance MUST be directly credited
        self.assertEqual(self.user.wallet_balance, Decimal("15000"))
        self.assertEqual(
            Transaction.objects.filter(transaction_type=Transaction.TransactionType.CHARGE).count(),
            1,
        )


class SellerProductManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller_user = User.objects.create_user(
            phone_number="09126667777",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="مدیر",
        )
        self.buyer = User.objects.create_user(
            phone_number="09126667778",
            password="StrongPass123!",
            first_name="خریدار",
            last_name="محصول",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه مدیریت",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
            verified=True,
        )
        self.category = Category.objects.create(name="مدیریت محصول")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="محصول فروخته شده",
            description="برای تست حذف",
            price=90000,
            stock=2,
            is_active=True,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            total_amount=self.product.price,
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=self.product.price,
            unit_coins=0,
            paid_with="money",
        )
        self.client.force_login(self.seller_user)

    def test_delete_sold_product_deactivates_it_instead_of_raising_500(self):
        response = self.client.post(
            reverse("bazar:seller-product-edit", args=[self.product.pk]),
            {"_delete": "1"},
        )

        self.assertRedirects(response, reverse("bazar:seller-product-list"))
        self.product.refresh_from_db()

        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertFalse(self.product.is_active)


class SellerAccountingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller_user = User.objects.create_user(
            phone_number="09126668888",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="حسابداری",
        )
        self.buyer = User.objects.create_user(
            phone_number="09126668889",
            password="StrongPass123!",
            first_name="خریدار",
            last_name="داشبورد",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه حسابداری",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
            verified=True,
        )
        self.category = Category.objects.create(name="گزارش فروش")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="محصول با نرخ سکه متفاوت",
            description="برای تست داشبورد",
            price=70000,
            coin_price=25000,
            stock=10,
            payment_method=Product.PaymentMethod.BOTH,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            total_amount=0,
            coins_used=25000,
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=70000,
            unit_coins=25000,
            paid_with="coin",
        )
        Transaction.objects.create(
            user=self.seller_user,
            order=self.order,
            amount=2500,
            transaction_type=Transaction.TransactionType.COMMISSION,
            description="کمیسیون تست",
        )
        Transaction.objects.create(
            user=self.seller_user,
            order=self.order,
            amount=22500,
            transaction_type=Transaction.TransactionType.SETTLEMENT,
            description="تسویه تست",
        )
        self.client.force_login(self.seller_user)

    def test_seller_dashboard_uses_coin_amount_for_coin_orders(self):
        response = self.client.get(reverse("bazar:seller-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_sales"], 1)
        self.assertEqual(response.context["total_revenue"], 25000)
        self.assertEqual(response.context["commission_paid"], 2500)
        self.assertEqual(response.context["settlement_paid"], 22500)

    def test_update_total_sales_aggregates_paid_order_items(self):
        self.seller.update_total_sales()
        self.seller.refresh_from_db()

        self.assertEqual(self.seller.sales_count, 1)
        self.assertEqual(self.seller.total_revenue, Decimal("25000"))


class OrderDisplayTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            phone_number="09127771111",
            password="StrongPass123!",
            first_name="خریدار",
            last_name="نمایش",
        )
        self.seller_user = User.objects.create_user(
            phone_number="09127772222",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="نمایش",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه نمایش",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
            verified=True,
        )
        self.category = Category.objects.create(name="دسته نمایش")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="محصول سکه‌ای",
            description="برای تست نمایش مبالغ",
            price=50000,
            coin_price=15000,
            stock=5,
            payment_method=Product.PaymentMethod.BOTH,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            total_amount=0,
            coins_used=30000,
            wallet_used=0,
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=50000,
            unit_coins=15000,
            paid_with="coin",
        )

    def test_order_history_shows_coin_item_totals_with_coin_label(self):
        self.client.force_login(self.buyer)

        response = self.client.get(reverse("bazar:order-history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "قیمت واحد: ۱۵,۰۰۰ سکه | جمع: ۳۰,۰۰۰ سکه")
        self.assertNotContains(response, "قیمت واحد: ۱۵,۰۰۰ تومان")

    def test_seller_order_list_shows_coin_item_totals_with_coin_label(self):
        self.client.force_login(self.seller_user)

        response = self.client.get(reverse("bazar:seller-order-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "قیمت واحد: ۱۵,۰۰۰ سکه | جمع: ۳۰,۰۰۰ سکه")
        self.assertNotContains(response, "قیمت واحد: ۱۵,۰۰۰ تومان")


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
        self.restaurant, _ = Category.objects.get_or_create(name="رستوران تست")
        self.fast_food, _ = Category.objects.get_or_create(name="فست فود تست", defaults={"parent": self.restaurant})
        self.shop, _ = Category.objects.get_or_create(name="فروشگاه تست")
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

    def test_price_filter_and_sort_use_same_rounding_as_product_final_price(self):
        rounded_up = Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="محصول گرد شده رو به بالا",
            description="تست گرد کردن",
            price=101,
            stock=3,
            discount_percent=50,
            discount_active=True,
        )
        Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="محصول ارزان‌تر",
            description="تست مقایسه",
            price=50,
            stock=3,
            discount_percent=0,
            discount_active=False,
        )

        response = self.client.get(
            reverse("bazar:product-list"),
            {"min_price": "51", "sort": "cheap"},
        )

        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual([product.title for product in products], [rounded_up.title])
        self.assertEqual(products[0].final_price, 51)

    def test_coin_only_products_use_coin_price_for_price_filter(self):
        Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="محصول فقط سکه‌ای",
            description="باید با قیمت سکه فیلتر شود",
            price=90000,
            coin_price=15000,
            stock=4,
            payment_method=Product.PaymentMethod.COIN,
        )
        money_product = Product.objects.create(
            seller=self.seller,
            category=self.shop,
            title="محصول نقدی",
            description="باید در نتیجه بماند",
            price=25000,
            stock=4,
            payment_method=Product.PaymentMethod.MONEY,
        )

        response = self.client.get(
            reverse("bazar:product-list"),
            {"min_price": "20000", "sort": "cheap"},
        )

        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        self.assertEqual([product.title for product in products], [money_product.title])


class BazarUploadValidationTests(TestCase):
    def setUp(self):
        self.seller_user = User.objects.create_user(
            phone_number="09127770002",
            password="StrongPass123!",
            first_name="فروشنده",
            last_name="آپلود",
        )
        self.seller = Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه آپلود",
            shop_address="تهران",
            platform_commission_percent=Decimal("10.00"),
            verified=True,
        )
        self.category = Category.objects.create(name="اعتبارسنجی تصویر")

    def _build_valid_gif(self, file_name: str = "sample.gif") -> SimpleUploadedFile:
        image_buffer = io.BytesIO()
        image = Image.new("RGB", (10, 10), color=(200, 50, 50))
        image.save(image_buffer, format="GIF")
        return SimpleUploadedFile(file_name, image_buffer.getvalue(), content_type="image/gif")

    def test_product_form_rejects_disallowed_but_valid_image_extension(self):
        form = ProductForm(
            data={
                "category": self.category.pk,
                "title": "محصول با تصویر نامجاز",
                "description": "توضیحات تست",
                "price": 10000,
                "coin_price": "",
                "payment_method": Product.PaymentMethod.MONEY,
                "stock": 3,
                "discount_percent": 0,
                "discount_active": False,
                "is_ticket": False,
                "is_active": True,
            },
            files={"image": self._build_valid_gif()},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("پسوند فایل مجاز نیست", form.errors["image"][0])
