from django.test import TestCase
from datetime import date
from rest_framework.test import APIClient

from accounts.models import User
from geography.models import City, Mosque, Province, School


class AccountsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        location_value = {"type": "Point", "coordinates": [51.3890, 35.6892]}
        self.province = Province.objects.create(name="تهران")
        self.city = City.objects.create(province=self.province, name="تهران")
        self.other_province = Province.objects.create(name="قم")
        self.other_city = City.objects.create(province=self.other_province, name="قم")
        self.school = School.objects.create(
            name="مدرسه نمونه",
            address="آدرس مدرسه",
            city="تهران",
            province="تهران",
            province_ref=self.province,
            city_ref=self.city,
            location=location_value,
        )
        self.other_school = School.objects.create(
            name="مدرسه قم",
            address="آدرس مدرسه قم",
            city="قم",
            province="قم",
            province_ref=self.other_province,
            city_ref=self.other_city,
            location=location_value,
        )
        self.mosque = Mosque.objects.create(
            name="مسجد نمونه",
            address="آدرس مسجد",
            city="تهران",
            province="تهران",
            province_ref=self.province,
            city_ref=self.city,
            location=location_value,
        )

    def test_user_registration_login_profile_and_update(self):
        register_payload = {
            "phone_number": "09123456789",
            "first_name": "علی",
            "last_name": "رضایی",
            "password": "StrongPass123!",
            "national_code": "0010350829",
            "birth_date": "2010-01-01",
            "grade_level": 9,
            "gender": "male",
            "school": self.school.pk,
            "mosque": self.mosque.pk,
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
        self.assertEqual(res.data["city"], "تهران")
        self.assertEqual(res.data["province"], "تهران")
        self.assertEqual(res.data["grade_level"], 9)

        patch_payload = {"school": self.other_school.pk, "mosque": None}
        res = self.client.patch("/api/accounts/profile/me/", patch_payload, format="json", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["city"], "قم")
        self.assertEqual(res.data["province"], "قم")
        self.assertEqual(res.data["school"]["id"], self.other_school.pk)
        self.assertIsNone(res.data["mosque"])

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
        seller.seller_profile.verified = True
        seller.seller_profile.save(update_fields=["verified", "updated_at"])

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

    def test_user_registration_rejects_mismatched_mosque_and_school(self):
        other_mosque = Mosque.objects.create(
            name="مسجد قم",
            address="آدرس مسجد قم",
            city="قم",
            province="قم",
            province_ref=self.other_province,
            city_ref=self.other_city,
            location={"type": "Point", "coordinates": [50.8764, 34.6416]},
        )

        register_payload = {
            "phone_number": "09300000000",
            "first_name": "رضا",
            "last_name": "احمدی",
            "password": "StrongPass123!",
            "school": self.school.pk,
            "mosque": other_mosque.pk,
        }
        res = self.client.post("/api/accounts/register/", register_payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("mosque", res.data)

    def test_user_registration_accepts_birth_date_with_slashes(self):
        register_payload = {
            "phone_number": "09125555555",
            "first_name": "مهدی",
            "last_name": "کریمی",
            "password": "StrongPass123!",
            "birth_date": "2010/01/15",
        }
        res = self.client.post("/api/accounts/register/", register_payload, format="json")
        self.assertEqual(res.status_code, 201)

        user = User.objects.get(phone_number="09125555555")
        self.assertEqual(user.birth_date, date(2010, 1, 15))

    def test_user_registration_accepts_birth_date_with_persian_digits(self):
        register_payload = {
            "phone_number": "09126666666",
            "first_name": "امیر",
            "last_name": "کاظمی",
            "password": "StrongPass123!",
            "birth_date": "۲۰۱۰/۰۱/۱۵",
        }
        res = self.client.post("/api/accounts/register/", register_payload, format="json")
        self.assertEqual(res.status_code, 201)

        user = User.objects.get(phone_number="09126666666")
        self.assertEqual(user.birth_date, date(2010, 1, 15))

    def test_user_registration_accepts_jalali_birth_date(self):
        register_payload = {
            "phone_number": "09127777777",
            "first_name": "سینا",
            "last_name": "عباسی",
            "password": "StrongPass123!",
            "birth_date": "1385/01/01",
            "grade_level": 1,
        }
        res = self.client.post("/api/accounts/register/", register_payload, format="json")
        self.assertEqual(res.status_code, 201)

        user = User.objects.get(phone_number="09127777777")
        self.assertEqual(user.birth_date, date(2006, 3, 21))
        self.assertEqual(user.grade_level, 1)

    def test_user_profile_update_accepts_jalali_birth_date(self):
        user = User.objects.create_user(
            phone_number="09128888888",
            password="StrongPass123!",
            first_name="محمد",
            last_name="جعفری",
        )
        self.client.force_authenticate(user=user)

        res = self.client.patch(
            "/api/accounts/profile/me/",
            {"birth_date": "1395/01/01", "grade_level": 12},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.birth_date, date(2016, 3, 20))
        self.assertEqual(user.grade_level, 12)

    def test_user_registration_defaults_grade_level_to_twelveth(self):
        register_payload = {
            "phone_number": "09129999999",
            "first_name": "نوید",
            "last_name": "مرادی",
            "password": "StrongPass123!",
            "birth_date": "2011-05-10",
        }
        res = self.client.post("/api/accounts/register/", register_payload, format="json")
        self.assertEqual(res.status_code, 201)

        user = User.objects.get(phone_number="09129999999")
        self.assertEqual(user.grade_level, User.GradeLevel.TWELFTH)

    def test_user_registration_rejects_birth_date_outside_allowed_range(self):
        too_old_payload = {
            "phone_number": "09120000001",
            "first_name": "قدیمی",
            "last_name": "نمونه",
            "password": "StrongPass123!",
            "birth_date": "1384/12/29",
        }
        res = self.client.post("/api/accounts/register/", too_old_payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("birth_date", res.data)
        self.assertTrue(res.data["birth_date"])
        self.assertIn("ثبت‌نام برای این سن مقدور نمی‌باشد", str(res.data["birth_date"][0]))

        too_new_payload = {
            "phone_number": "09120000002",
            "first_name": "جدید",
            "last_name": "نمونه",
            "password": "StrongPass123!",
            "birth_date": "1396/01/01",
        }
        res = self.client.post("/api/accounts/register/", too_new_payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("birth_date", res.data)
        self.assertTrue(res.data["birth_date"])
        self.assertIn("ثبت‌نام برای این سن مقدور نمی‌باشد", str(res.data["birth_date"][0]))
