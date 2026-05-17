from django import forms
from django.contrib import admin

from geography.models import City, Mosque, Province, School


class SchoolAdminForm(forms.ModelForm):
    class Meta:
        model = School
        fields = (
            "province_ref",
            "city_ref",
            "name",
            "address",
            "location",
            "phone",
            "principal_name",
        )

    class Media:
        js = ("js/geography_admin_chained.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province_ref"].queryset = Province.objects.all().order_by("name")
        self.fields["city_ref"].queryset = City.objects.none()
        self.fields["province_ref"].required = True
        self.fields["city_ref"].required = True

        if self.instance and getattr(self.instance, "city_ref_id", None) and not getattr(self.instance, "province_ref_id", None):
            self.instance.province_ref = self.instance.city_ref.province

        if "province_ref" in self.data:
            try:
                province_id = int(self.data.get("province_ref") or 0)
            except (TypeError, ValueError):
                province_id = 0
            if province_id:
                self.fields["city_ref"].queryset = City.objects.filter(province_id=province_id).order_by("name")
        elif self.instance and getattr(self.instance, "province_ref_id", None):
            self.fields["city_ref"].queryset = City.objects.filter(province=self.instance.province_ref).order_by("name")

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get("province_ref")
        city = cleaned.get("city_ref")
        if province and city and city.province_id != province.id:
            self.add_error("city_ref", "شهر انتخاب شده با استان انتخاب شده همخوانی ندارد.")
        return cleaned


class MosqueAdminForm(forms.ModelForm):
    class Meta:
        model = Mosque
        fields = (
            "province_ref",
            "city_ref",
            "name",
            "address",
            "location",
            "phone",
            "imam_name",
        )

    class Media:
        js = ("js/geography_admin_chained.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province_ref"].queryset = Province.objects.all().order_by("name")
        self.fields["city_ref"].queryset = City.objects.none()
        self.fields["province_ref"].required = True
        self.fields["city_ref"].required = True

        if self.instance and getattr(self.instance, "city_ref_id", None) and not getattr(self.instance, "province_ref_id", None):
            self.instance.province_ref = self.instance.city_ref.province

        if "province_ref" in self.data:
            try:
                province_id = int(self.data.get("province_ref") or 0)
            except (TypeError, ValueError):
                province_id = 0
            if province_id:
                self.fields["city_ref"].queryset = City.objects.filter(province_id=province_id).order_by("name")
        elif self.instance and getattr(self.instance, "province_ref_id", None):
            self.fields["city_ref"].queryset = City.objects.filter(province=self.instance.province_ref).order_by("name")

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get("province_ref")
        city = cleaned.get("city_ref")
        if province and city and city.province_id != province.id:
            self.add_error("city_ref", "شهر انتخاب شده با استان انتخاب شده همخوانی ندارد.")
        return cleaned


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province")
    list_filter = ("province",)
    search_fields = ("name", "province__name")


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    form = SchoolAdminForm
    list_display = ("name", "province_ref", "city_ref", "phone")
    list_filter = ("province_ref", "city_ref")
    search_fields = ("name", "city", "province", "phone", "principal_name")


@admin.register(Mosque)
class MosqueAdmin(admin.ModelAdmin):
    form = MosqueAdminForm
    list_display = ("name", "province_ref", "city_ref", "phone")
    list_filter = ("province_ref", "city_ref")
    search_fields = ("name", "city", "province", "phone", "imam_name")
