from django.urls import path, re_path

from . import views

app_name = "bazar"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product-list"),
    re_path(r"^category/(?P<slug>[-\w]+)/$", views.ProductListView.as_view(), name="category-products"),
    re_path(r"^product/(?P<slug>[-\w]+)/$", views.ProductDetailView.as_view(), name="product-detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/item/<int:item_id>/quantity/", views.update_cart_item_quantity, name="cart-update-quantity"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="cart-add"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="cart-remove"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("checkout/apply-coins/", views.apply_coins_view, name="checkout-apply-coins"),
    path("checkout/pay/", views.pay_view, name="checkout-pay"),
    path("wallet/charge/", views.wallet_charge_view, name="wallet-charge"),
    path("orders/", views.OrderHistoryView.as_view(), name="order-history"),
    path("seller/dashboard/", views.SellerDashboardView.as_view(), name="seller-dashboard"),
    path("seller/products/", views.SellerProductListView.as_view(), name="seller-product-list"),
    path("seller/products/add/", views.SellerProductCreateView.as_view(), name="seller-product-add"),
    path("seller/products/edit/<int:pk>/", views.SellerProductUpdateView.as_view(), name="seller-product-edit"),
    path("seller/orders/", views.SellerOrderListView.as_view(), name="seller-order-list"),
]
