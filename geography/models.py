from __future__ import annotations

from django.db import models

try:
    from django.contrib.gis.db.models import PointField as GISPointField
except Exception:
    GISPointField = None


class School(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=50)
    province = models.CharField(max_length=50)
    location = (GISPointField or models.JSONField)()
    phone = models.CharField(max_length=11, null=True, blank=True)
    principal_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Mosque(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=50)
    province = models.CharField(max_length=50)
    location = (GISPointField or models.JSONField)()
    phone = models.CharField(max_length=11, null=True, blank=True)
    imam_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return self.name
