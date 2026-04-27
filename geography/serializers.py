from __future__ import annotations

from rest_framework import serializers

from geography.models import Mosque, School


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "address", "city", "province", "location", "phone", "principal_name"]


class MosqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mosque
        fields = ["id", "name", "address", "city", "province", "location", "phone", "imam_name"]
