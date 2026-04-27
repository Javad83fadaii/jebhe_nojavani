from django.contrib import admin

from geography.models import Mosque, School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "province", "phone")
    list_filter = ("province", "city")
    search_fields = ("name", "city", "province", "phone", "principal_name")


@admin.register(Mosque)
class MosqueAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "province", "phone")
    list_filter = ("province", "city")
    search_fields = ("name", "city", "province", "phone", "imam_name")
