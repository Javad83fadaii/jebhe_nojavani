from __future__ import annotations

from django.db import models

try:
    from django.contrib.gis.db.models import PointField as GISPointField
except Exception:
    GISPointField = None


class Province(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class City(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ("province__name", "name")
        constraints = [
            models.UniqueConstraint(fields=["province", "name"], name="unique_city_per_province"),
        ]

    def __str__(self) -> str:
        return f"{self.province} - {self.name}"


class School(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=50)
    province = models.CharField(max_length=50)
    province_ref = models.ForeignKey(Province, null=True, blank=True, on_delete=models.SET_NULL, related_name="schools")
    city_ref = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name="schools")
    location = (GISPointField or models.JSONField)()
    phone = models.CharField(max_length=11, null=True, blank=True)
    principal_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.city_ref_id:
            self.city = self.city_ref.name
            self.province = self.city_ref.province.name
            self.province_ref = self.city_ref.province
        elif self.province_ref_id:
            self.province = self.province_ref.name
        super().save(*args, **kwargs)


class Mosque(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=50)
    province = models.CharField(max_length=50)
    province_ref = models.ForeignKey(Province, null=True, blank=True, on_delete=models.SET_NULL, related_name="mosques")
    city_ref = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name="mosques")
    location = (GISPointField or models.JSONField)()
    phone = models.CharField(max_length=11, null=True, blank=True)
    imam_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.city_ref_id:
            self.city = self.city_ref.name
            self.province = self.city_ref.province.name
            self.province_ref = self.city_ref.province
        elif self.province_ref_id:
            self.province = self.province_ref.name
        super().save(*args, **kwargs)
