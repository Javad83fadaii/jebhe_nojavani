from django.test import TestCase
from rest_framework.test import APIClient

from geography.models import City, Mosque, Province, School


class GeographyAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.province = Province.objects.create(name="تهران")
        self.city = City.objects.create(province=self.province, name="تهران")
        self.other_province = Province.objects.create(name="قم")
        self.other_city = City.objects.create(province=self.other_province, name="قم")
        location_value = {"type": "Point", "coordinates": [51.3890, 35.6892]}

        self.school = School.objects.create(
            name="مدرسه تهران",
            address="آدرس مدرسه",
            city="تهران",
            province="تهران",
            province_ref=self.province,
            city_ref=self.city,
            location=location_value,
        )
        self.mosque = Mosque.objects.create(
            name="مسجد تهران",
            address="آدرس مسجد",
            city="تهران",
            province="تهران",
            province_ref=self.province,
            city_ref=self.city,
            location=location_value,
        )
        School.objects.create(
            name="مدرسه قم",
            address="آدرس مدرسه قم",
            city="قم",
            province="قم",
            province_ref=self.other_province,
            city_ref=self.other_city,
            location=location_value,
        )
        Mosque.objects.create(
            name="مسجد قم",
            address="آدرس مسجد قم",
            city="قم",
            province="قم",
            province_ref=self.other_province,
            city_ref=self.other_city,
            location=location_value,
        )

    def test_city_list_supports_ids(self):
        res = self.client.get(f"/api/geography/cities/?province_id={self.province.pk}&with_ids=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [{"id": self.city.pk, "name": "تهران"}])

    def test_school_and_mosque_filters_support_ids(self):
        school_res = self.client.get(f"/api/geography/schools/?province_id={self.province.pk}&city_id={self.city.pk}")
        mosque_res = self.client.get(f"/api/geography/mosques/?province_id={self.province.pk}&city_id={self.city.pk}")

        self.assertEqual(school_res.status_code, 200)
        self.assertEqual(mosque_res.status_code, 200)
        self.assertEqual([item["id"] for item in school_res.data], [self.school.pk])
        self.assertEqual([item["id"] for item in mosque_res.data], [self.mosque.pk])
