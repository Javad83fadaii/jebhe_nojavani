from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet

from geography.models import Mosque, School
from geography.serializers import MosqueSerializer, SchoolSerializer


class SchoolViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = School.objects.all().order_by("name")
    serializer_class = SchoolSerializer


class MosqueViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Mosque.objects.all().order_by("name")
    serializer_class = MosqueSerializer
