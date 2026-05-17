from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from geography.models import City, Mosque, Province, School
from geography.serializers import MosqueSerializer, SchoolSerializer


def _resolve_province_filter_data(province_name: str, province_id: str):
    province_obj = None
    if province_id:
        try:
            province_obj = Province.objects.filter(pk=int(province_id)).first()
        except (TypeError, ValueError):
            province_obj = None
    if province_obj is None and province_name:
        province_obj = Province.objects.filter(name__iexact=province_name).first()

    normalized_name = province_name
    if province_obj is not None:
        normalized_name = province_obj.name

    return province_obj, normalized_name


def _resolve_city_filter_data(city_name: str, city_id: str, province_obj: Province | None):
    city_obj = None
    if city_id:
        try:
            queryset = City.objects.select_related("province")
            if province_obj is not None:
                queryset = queryset.filter(province=province_obj)
            city_obj = queryset.filter(pk=int(city_id)).first()
        except (TypeError, ValueError):
            city_obj = None

    normalized_name = city_name
    if city_obj is not None:
        normalized_name = city_obj.name

    return city_obj, normalized_name


def _apply_place_filters(queryset, *, province_name: str, province_id: str, city_name: str, city_id: str):
    province_obj, normalized_province_name = _resolve_province_filter_data(province_name, province_id)
    city_obj, normalized_city_name = _resolve_city_filter_data(city_name, city_id, province_obj)

    if province_obj is not None:
        queryset = queryset.filter(
            Q(province_ref=province_obj) | Q(city_ref__province=province_obj) | Q(province__iexact=province_obj.name)
        )
    elif normalized_province_name:
        queryset = queryset.filter(Q(province__iexact=normalized_province_name) | Q(province_ref__name__iexact=normalized_province_name))

    if city_obj is not None:
        queryset = queryset.filter(Q(city_ref=city_obj) | Q(city__iexact=city_obj.name))
    elif normalized_city_name:
        queryset = queryset.filter(Q(city__iexact=normalized_city_name) | Q(city_ref__name__iexact=normalized_city_name))

    return queryset


class SchoolViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = School.objects.all().order_by("name")
    serializer_class = SchoolSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        province_id = (self.request.query_params.get("province_id") or "").strip()
        province = (self.request.query_params.get("province") or "").strip()
        city_id = (self.request.query_params.get("city_id") or "").strip()
        city = (self.request.query_params.get("city") or "").strip()
        return _apply_place_filters(
            queryset,
            province_name=province,
            province_id=province_id,
            city_name=city,
            city_id=city_id,
        )


class MosqueViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Mosque.objects.all().order_by("name")
    serializer_class = MosqueSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        province_id = (self.request.query_params.get("province_id") or "").strip()
        province = (self.request.query_params.get("province") or "").strip()
        city_id = (self.request.query_params.get("city_id") or "").strip()
        city = (self.request.query_params.get("city") or "").strip()
        return _apply_place_filters(
            queryset,
            province_name=province,
            province_id=province_id,
            city_name=city,
            city_id=city_id,
        )


class ProvinceListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        model_provinces = Province.objects.values_list("name", flat=True)
        school_provinces = School.objects.exclude(province__isnull=True).exclude(province="").values_list("province", flat=True)
        mosque_provinces = Mosque.objects.exclude(province__isnull=True).exclude(province="").values_list("province", flat=True)
        provinces = sorted({p.strip() for p in list(model_provinces) + list(school_provinces) + list(mosque_provinces) if str(p).strip()})
        return Response(provinces)


class CityListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        with_ids = str(request.query_params.get("with_ids") or "").lower() in ("1", "true", "yes")
        province_id = (request.query_params.get("province_id") or "").strip()
        province = (request.query_params.get("province") or "").strip()

        province_obj = None
        if province_id:
            try:
                province_obj = Province.objects.filter(pk=int(province_id)).first()
            except (TypeError, ValueError):
                province_obj = None
        if province_obj is None and province:
            province_obj = Province.objects.filter(name__iexact=province).first()

        if province_obj is None and not province:
            return Response([])

        model_cities = City.objects.none()
        if province_obj:
            if with_ids:
                model_cities = City.objects.filter(province=province_obj).values("id", "name")
            else:
                model_cities = City.objects.filter(province=province_obj).values_list("name", flat=True)

        school_cities = (
            School.objects.filter(
                Q(province__iexact=province) | Q(province_ref__name__iexact=province) if province else Q(province_ref=province_obj)
            )
            .exclude(city__isnull=True)
            .exclude(city="")
            .values_list("city", flat=True)
        )
        mosque_cities = (
            Mosque.objects.filter(
                Q(province__iexact=province) | Q(province_ref__name__iexact=province) if province else Q(province_ref=province_obj)
            )
            .exclude(city__isnull=True)
            .exclude(city="")
            .values_list("city", flat=True)
        )
        if with_ids:
            return Response(list(model_cities))

        cities = sorted({c.strip() for c in list(model_cities) + list(school_cities) + list(mosque_cities) if str(c).strip()})
        return Response(cities)
