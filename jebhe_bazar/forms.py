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


class CartQuantityForm(StyledFormMixin, forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=100, label="تعداد")


class CoinApplyForm(StyledFormMixin, forms.Form):
    coins_to_use = forms.IntegerField(min_value=0, label="تعداد سکه")

    def __init__(self, *args, max_coins: int = 0, **kwargs):
        self.max_coins = max(0, int(max_coins))
        super().__init__(*args, **kwargs)
        self.fields["coins_to_use"].widget.attrs["max"] = self.max_coins
        self.fields["coins_to_use"].help_text = f"حداکثر {self.max_coins} سکه قابل استفاده است."

    def clean_coins_to_use(self):
        value = self.cleaned_data["coins_to_use"]
        if value > self.max_coins:
            raise forms.ValidationError("تعداد سکه وارد شده بیشتر از سقف مجاز است.")
        return value


class WalletChargeForm(StyledFormMixin, forms.Form):
    amount = forms.IntegerField(min_value=1, label="مبلغ شارژ (تومان)")

    def __init__(self, *args, suggested_amount: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        if suggested_amount and not self.is_bound:
            self.initial["amount"] = suggested_amount
