from django.test import Client, TestCase, override_settings
from datetime import date, timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from accounts.models import PasswordResetRequest, User
from accounts.services.smsir import SMSIRSendResult
from geography.models import City, Mosque, Province, School


@override_settings(SMS_BACKEND="dummy")
class AccountsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
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

        res = self.client.get("/api/accounts/profile/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["phone_number"], "09111111111")
        self.assertEqual(res.data["city"], "تهران")
        self.assertEqual(res.data["province"], "تهران")

        res = self.client.patch(
            "/api/accounts/profile/me/",
            {"city": "قم", "province": "قم"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["city"], "قم")
        self.assertEqual(res.data["province"], "قم")

    def test_seller_registration_rejects_duplicate_phone_number_with_persian_digits(self):
        User.objects.create_user(
            phone_number="09112223344",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="تکراری",
        )
        seller_register_payload = {
            "phone_number": "۰۹۱۱۲۲۲۳۳۴۴",
            "first_name": "حسین",
            "last_name": "محمدی",
            "password": "StrongPass123!",
            "seller_shop_name": "فروشگاه تکراری",
            "seller_shop_address": "آدرس فروشگاه",
        }

        res = self.client.post("/api/accounts/seller/register/", seller_register_payload, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("phone_number", res.data)
        self.assertEqual(res.data["phone_number"][0], "این شماره تلفن قبلاً ثبت شده است.")

    def test_seller_registration_accepts_phone_number_with_persian_digits(self):
        seller_register_payload = {
            "phone_number": "۰۹۱۳۳۳۳۳۳۳۳",
            "first_name": "حسین",
            "last_name": "محمدی",
            "password": "StrongPass123!",
            "seller_shop_name": "فروشگاه فارسی",
            "seller_shop_address": "آدرس فروشگاه",
        }

        res = self.client.post("/api/accounts/seller/register/", seller_register_payload, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertTrue(User.objects.filter(phone_number="09133333333").exists())

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

    @patch("accounts.views.randbelow", return_value=23456)
    def test_password_reset_flow_creates_hashed_request_and_updates_password(self, mocked_randbelow):
        user = User.objects.create_user(
            phone_number="09123334444",
            password="OldStrongPass123!",
            first_name="کاربر",
            last_name="نمونه",
        )

        res = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["phone_number"], user.phone_number)
        self.assertEqual(res.data["detail"], "اگر حسابی با این شماره وجود داشته باشد، کد بازیابی برای آن ارسال خواهد شد.")
        self.assertEqual(res.data["expires_in_seconds"], 300)

        reset_request = PasswordResetRequest.objects.filter(phone_number=user.phone_number).order_by("-requested_at").first()
        self.assertIsNotNone(reset_request)
        self.assertEqual(reset_request.attempts, 0)
        self.assertTrue(reset_request.code_hash)
        self.assertNotIn("code", [field.name for field in PasswordResetRequest._meta.fields])
        self.assertLessEqual(
            abs((reset_request.expires_at - reset_request.requested_at) - timedelta(minutes=5)),
            timedelta(seconds=5),
        )
        verification_code = "123456"
        new_password = "NewStrongPass123!"
        res = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "phone_number": user.phone_number,
                "code": verification_code,
                "new_password": new_password,
                "new_password_confirm": new_password,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

        res = self.client.post(
            "/api/accounts/login/",
            {"phone_number": user.phone_number, "password": new_password},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        mocked_randbelow.assert_called()

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

    @patch("accounts.views.send_password_reset_code", side_effect=RuntimeError("SMS.ir connection error: timeout"))
    def test_password_reset_request_stores_real_send_error(self, mocked_send):
        user = User.objects.create_user(
            phone_number="09124445555",
            password="StrongPass123!",
            first_name="خطا",
            last_name="نمونه",
        )

        res = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )
        self.assertEqual(res.status_code, 503)

        reset_request = PasswordResetRequest.objects.filter(phone_number=user.phone_number).order_by("-requested_at").first()
        self.assertIsNotNone(reset_request)
        self.assertEqual(reset_request.status, PasswordResetRequest.Status.FAILED)
        self.assertEqual(reset_request.send_error, "SMS.ir connection error: timeout")
        self.assertEqual(reset_request.resolved_send_error, "SMS.ir connection error: timeout")
        self.assertEqual(reset_request.send_status_label, "ارسال ناموفق")
        self.assertEqual(reset_request.expiration_status_label, "نامعتبر")
        self.assertEqual(reset_request.provider_response["error"], "SMS.ir connection error: timeout")
        mocked_send.assert_called_once()

    def test_password_reset_request_is_generic_for_unknown_phone(self):
        res = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": "09129998877"},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["detail"], "اگر حسابی با این شماره وجود داشته باشد، کد بازیابی برای آن ارسال خواهد شد.")
        self.assertFalse(PasswordResetRequest.objects.filter(phone_number="09129998877").exists())

    @patch("accounts.views.send_password_reset_code", side_effect=RuntimeError("SMS.ir connection error: timeout"))
    def test_failed_password_reset_delivery_does_not_block_retry(self, mocked_send):
        user = User.objects.create_user(
            phone_number="09127778899",
            password="StrongPass123!",
            first_name="ارسال",
            last_name="ناموفق",
        )

        first_response = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )
        second_response = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )

        self.assertEqual(first_response.status_code, 503)
        self.assertEqual(second_response.status_code, 503)
        self.assertEqual(
            PasswordResetRequest.objects.filter(phone_number=user.phone_number).count(),
            2,
        )
        mocked_send.assert_called()

    @patch("accounts.views.randbelow", return_value=23456)
    def test_password_reset_confirm_fails_request_after_five_invalid_attempts(self, mocked_randbelow):
        user = User.objects.create_user(
            phone_number="09123335555",
            password="StrongPass123!",
            first_name="تلاش",
            last_name="نمونه",
        )

        request_response = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)

        last_response = None
        for _ in range(5):
            last_response = self.client.post(
                "/api/accounts/password-reset/confirm/",
                {
                    "phone_number": user.phone_number,
                    "code": "000000",
                    "new_password": "AnotherStrongPass123!",
                    "new_password_confirm": "AnotherStrongPass123!",
                },
                format="json",
            )

        self.assertIsNotNone(last_response)
        self.assertEqual(last_response.status_code, 400)
        self.assertEqual(last_response.data["detail"], "تعداد تلاش‌های مجاز به پایان رسید. دوباره درخواست بازیابی ثبت کنید.")

        reset_request = PasswordResetRequest.objects.filter(phone_number=user.phone_number).order_by("-requested_at").first()
        self.assertIsNotNone(reset_request)
        self.assertEqual(reset_request.attempts, 5)
        self.assertEqual(reset_request.status, PasswordResetRequest.Status.FAILED)

        valid_after_failure = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "phone_number": user.phone_number,
                "code": "123456",
                "new_password": "AnotherStrongPass123!",
                "new_password_confirm": "AnotherStrongPass123!",
            },
            format="json",
        )
        self.assertEqual(valid_after_failure.status_code, 400)
        mocked_randbelow.assert_called_once()

    @patch("accounts.views.randbelow", return_value=23456)
    def test_password_reset_invalidates_previous_jwt_tokens(self, mocked_randbelow):
        user = User.objects.create_user(
            phone_number="09128889900",
            password="OldStrongPass123!",
            first_name="توکن",
            last_name="نمونه",
        )

        login_response = self.client.post(
            "/api/accounts/login/",
            {"phone_number": user.phone_number, "password": "OldStrongPass123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        old_access = login_response.data["access"]
        old_refresh = login_response.data["refresh"]

        request_response = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)

        confirm_response = self.client.post(
            "/api/accounts/password-reset/confirm/",
            {
                "phone_number": user.phone_number,
                "code": "123456",
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "NewStrongPass123!",
            },
            format="json",
        )
        self.assertEqual(confirm_response.status_code, 200)

        access_client = APIClient()
        access_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        old_access_response = access_client.get("/api/accounts/profile/me/")
        self.assertEqual(old_access_response.status_code, 401)

        refresh_client = APIClient()
        old_refresh_response = refresh_client.post(
            "/api/accounts/token/refresh/",
            {"refresh": old_refresh},
            format="json",
        )
        self.assertEqual(old_refresh_response.status_code, 401)
        mocked_randbelow.assert_called_once()

    def test_password_reset_request_is_throttled_by_phone_number(self):
        rest_framework_settings = dict(settings.REST_FRAMEWORK)
        throttle_rates = dict(rest_framework_settings.get("DEFAULT_THROTTLE_RATES", {}))
        throttle_rates["password_reset_request_phone"] = "1/hour"
        rest_framework_settings["DEFAULT_THROTTLE_RATES"] = throttle_rates

        with override_settings(REST_FRAMEWORK=rest_framework_settings):
            first_response = self.client.post(
                "/api/accounts/password-reset/request/",
                {"phone_number": "09120001122"},
                format="json",
            )
            second_response = self.client.post(
                "/api/accounts/password-reset/request/",
                {"phone_number": "۰۹۱۲۰۰۰۱۱۲۲"},
                format="json",
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    @override_settings(SMS_BACKEND="smsir", SMSIR_TEMPLATE_ID="321", SMSIR_LINE_NUMBER="300000")
    @patch(
        "accounts.services.sms.send_sms",
        return_value=SMSIRSendResult(ok=True, message_id="bulk-1", raw={"status": 1, "message": "bulk ok"}),
    )
    @patch("accounts.services.sms.send_verify_code", side_effect=RuntimeError("verify timeout"))
    def test_password_reset_request_falls_back_to_bulk_sms_when_verify_raises(
        self, mocked_verify, mocked_bulk_send
    ):
        user = User.objects.create_user(
            phone_number="09125554444",
            password="StrongPass123!",
            first_name="بازیابی",
            last_name="نمونه",
        )

        res = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        reset_request = PasswordResetRequest.objects.filter(phone_number=user.phone_number).order_by("-requested_at").first()
        self.assertIsNotNone(reset_request)
        self.assertEqual(reset_request.provider, "smsir")
        self.assertEqual(reset_request.provider_message_id, "bulk-1")
        self.assertEqual(reset_request.send_error, "")
        self.assertEqual(reset_request.provider_response["primary_channel"], "verify")
        self.assertEqual(reset_request.provider_response["primary_error"], "verify timeout")
        self.assertEqual(reset_request.provider_response["fallback_channel"], "bulk")
        self.assertEqual(reset_request.provider_response["fallback_result"]["status"], 1)
        mocked_verify.assert_called_once()
        mocked_bulk_send.assert_called_once()

    @override_settings(SMS_BACKEND="smsir", SMSIR_TEMPLATE_ID="321", SMSIR_LINE_NUMBER="300000")
    @patch(
        "accounts.services.sms.send_sms",
        return_value=SMSIRSendResult(ok=True, message_id="bulk-2", raw={"status": 1, "message": "bulk ok"}),
    )
    @patch(
        "accounts.services.sms.send_verify_code",
        return_value=SMSIRSendResult(ok=False, message_id=None, raw={"status": 0, "message": "template failed"}),
    )
    def test_password_reset_request_falls_back_to_bulk_sms_when_verify_is_unsuccessful(
        self, mocked_verify, mocked_bulk_send
    ):
        user = User.objects.create_user(
            phone_number="09126665555",
            password="StrongPass123!",
            first_name="کد",
            last_name="نمونه",
        )

        res = self.client.post(
            "/api/accounts/password-reset/request/",
            {"phone_number": user.phone_number},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        reset_request = PasswordResetRequest.objects.filter(phone_number=user.phone_number).order_by("-requested_at").first()
        self.assertIsNotNone(reset_request)
        self.assertEqual(reset_request.provider_message_id, "bulk-2")
        self.assertEqual(reset_request.provider_response["primary_result"]["status"], 0)
        self.assertEqual(reset_request.provider_response["fallback_result"]["status"], 1)
        mocked_verify.assert_called_once()
        mocked_bulk_send.assert_called_once()

    def test_convert_coins_api_and_approval_flow(self):
        user = User.objects.create_user(
            phone_number="09121112233",
            password="StrongPass123!",
            first_name="کاربر",
            last_name="تبدیل",
            challenge_coins=500,
            wallet_balance=1000,
        )
        self.client.force_authenticate(user=user)

        # 1. Check GET endpoint
        get_res = self.client.get("/api/accounts/profile/convert-coins/")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.data["challenge_coins"], 500)
        self.assertEqual(get_res.data["wallet_balance"], 1000)

        # 2. Try converting more than balance -> Should fail
        fail_res = self.client.post("/api/accounts/profile/convert-coins/", {"coin_amount": 600}, format="json")
        self.assertEqual(fail_res.status_code, 400)

        # 3. Try converting zero or negative -> Should fail
        zero_res = self.client.post("/api/accounts/profile/convert-coins/", {"coin_amount": 0}, format="json")
        self.assertEqual(zero_res.status_code, 400)

        # 4. Valid conversion request
        ok_res = self.client.post("/api/accounts/profile/convert-coins/", {"coin_amount": 200}, format="json")
        self.assertEqual(ok_res.status_code, 201)
        transfer_id = ok_res.data["transfer_id"]

        from accounts.models import CoinToWalletTransfer, CoinTransaction
        transfer = CoinToWalletTransfer.objects.get(pk=transfer_id)
        self.assertEqual(transfer.status, CoinToWalletTransfer.TransferStatus.PENDING)
        self.assertEqual(transfer.coin_amount, 200)

        # Before admin approval, user balance and coins remain as is
        user.refresh_from_db()
        self.assertEqual(user.challenge_coins, 500)
        self.assertEqual(user.wallet_balance, 1000)

        # Admin approves the transfer
        transfer.status = CoinToWalletTransfer.TransferStatus.APPROVED
        transfer.save()

        user.refresh_from_db()
        # Challenge coins deducted
        self.assertEqual(user.challenge_coins, 300)
        # Wallet balance directly credited in Tomans
        self.assertEqual(user.wallet_balance, 1200)
        self.assertTrue(
            CoinTransaction.objects.filter(
                user=user,
                transaction_type=CoinTransaction.TransactionType.WALLET_TRANSFER,
            ).exists()
        )

    def test_profile_patch_with_session_requires_csrf(self):
        user = User.objects.create_user(
            phone_number="09123330000",
            password="StrongPass123!",
            first_name="سشن",
            last_name="بدون csrf",
        )
        client = Client(enforce_csrf_checks=True)
        self.assertTrue(client.login(phone_number=user.phone_number, password="StrongPass123!"))

        response = client.patch(
            "/api/accounts/profile/me/",
            data='{"first_name":"جدید"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_profile_patch_with_session_and_csrf_succeeds(self):
        user = User.objects.create_user(
            phone_number="09124440000",
            password="StrongPass123!",
            first_name="سشن",
            last_name="با csrf",
        )
        client = Client(enforce_csrf_checks=True)
        self.assertTrue(client.login(phone_number=user.phone_number, password="StrongPass123!"))

        page_response = client.get("/profile/")
        self.assertEqual(page_response.status_code, 200)
        csrf_token = client.cookies["csrftoken"].value

        response = client.patch(
            "/api/accounts/profile/me/",
            data='{"first_name":"جدید"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "جدید")
