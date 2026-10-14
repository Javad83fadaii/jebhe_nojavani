from __future__ import annotations

from django import forms

from .models import Product


class StyledFormMixin:
    def _apply_common_styles(self):
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} bazar-input".strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_styles()


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "title",
            "description",
            "price",
            "coin_price",
            "payment_method",
            "stock",
            "discount_percent",
            "discount_active",
            "is_ticket",
            "image",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get("payment_method")
        price = cleaned_data.get("price")
        coin_price = cleaned_data.get("coin_price")

        if payment_method == Product.PaymentMethod.COIN:
            if not coin_price and (price is None or price <= 0):
                self.add_error("coin_price", "برای محصولی که فقط با سکه قابل خرید است، قیمت به سکه الزامی است.")
        return cleaned_data


class CartQuantityForm(StyledFormMixin, forms.Form):
    quantity = forms.IntegerField(min_value=1, label="تعداد")


class WalletChargeRequestForm(StyledFormMixin, forms.Form):
    amount = forms.IntegerField(min_value=1, label="مبلغ درخواستی (تومان)")

    def __init__(self, *args, suggested_amount: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        if suggested_amount and not self.is_bound:
            self.initial["amount"] = suggested_amount
