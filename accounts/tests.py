from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from geography.models import Mosque, School


class AccountsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        location_value = {"type": "Point", "coordinates": [51.3890, 35.6892]}
        self.school = School.objects.create(
            name="مدرسه نمونه",
            address="آدرس مدرسه",
            city="تهران",
            province="تهران",
            location=location_value,
        )
        self.mosque = Mosque.objects.create(
            name="مسجد نمونه",
            address="آدرس مسجد",
            city="تهران",
            province="تهران",
            location=location_value,
        )

    def test_user_registration_login_profile_and_update(self):
        register_payload = {
            "phone_number": "09123456789",
            "first_name": "علی",
            "last_name": "رضایی",
            "password": "StrongPass123!",
            "national_code": "0010350829",
            "birth_date": "2000-01-01",
            "gender": "male",
            "school": self.school.pk,
            "mosque": self.mosque.pk,
            "city": "تهران",
            "province": "تهران",
        }
        res = self.client.post("/api/accounts/register/", register_payload, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

        login_payload = {"phone_number": "09123456789", "password": "StrongPass123!"}
        res = self.client.post("/api/accounts/login/", login_payload, format="json")
        self.assertEqual(res.status_code, 200)
        access = res.data["access"]

        res = self.client.get("/api/accounts/profile/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["phone_number"], "09123456789")
        self.assertEqual(res.data["school"]["id"], self.school.pk)
        self.assertEqual(res.data["mosque"]["id"], self.mosque.pk)

        patch_payload = {"city": "قم", "province": "قم"}
        res = self.client.patch("/api/accounts/profile/me/", patch_payload, format="json", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["city"], "قم")
        self.assertEqual(res.data["province"], "قم")

    def test_seller_registration_requires_admin_verification(self):
        seller_register_payload = {
            "phone_number": "09111111111",
            "first_name": "حسین",
            "last_name": "محمدی",
            "password": "StrongPass123!",
            "seller_shop_name": "فروشگاه نمونه",
            "seller_shop_address": "آدرس فروشگاه",
            "city": "تهران",
            "province": "تهران",
        }
        res = self.client.post("/api/accounts/seller/register/", seller_register_payload, format="json")
        self.assertEqual(res.status_code, 201)

        seller_login_payload = {"phone_number": "09111111111", "password": "StrongPass123!"}
        res = self.client.post("/api/accounts/seller/login/", seller_login_payload, format="json")
        self.assertEqual(res.status_code, 403)

        seller = User.objects.get(phone_number="09111111111")
        seller.seller_verified = True
        seller.save(update_fields=["seller_verified"])

        res = self.client.post("/api/accounts/seller/login/", seller_login_payload, format="json")
        self.assertEqual(res.status_code, 200)
        access = res.data["access"]

        res = self.client.get("/api/accounts/seller/profile/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["seller_verified"])

        res = self.client.patch(
            "/api/accounts/seller/profile/me/",
            {"seller_shop_name": "فروشگاه جدید", "seller_shop_address": "آدرس جدید"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["seller_shop_name"], "فروشگاه جدید")
