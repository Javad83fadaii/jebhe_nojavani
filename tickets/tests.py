from __future__ import annotations

from datetime import timedelta
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Seller
from .models import Ticket
from .services import (
    add_staff_reply,
    add_user_reply,
    assign_ticket,
    close_ticket,
    create_ticket,
    reopen_ticket,
)


class TicketServicesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user_model = get_user_model()
        self.reply_permission = Permission.objects.get(codename="reply_ticket")
        self.manage_permission = Permission.objects.get(codename="manage_ticket")
        self.user = self._create_user("09120000001")
        self.staff = self._create_user("09120000002", is_staff=True)
        self.staff.user_permissions.add(self.reply_permission)
        self.manager = self._create_user("09120000003", is_staff=True)
        self.manager.user_permissions.add(self.reply_permission, self.manage_permission)

    def _create_user(self, phone_number: str, **extra_fields):
        defaults = {
            "first_name": "کاربر",
            "last_name": phone_number[-2:],
            "password": "StrongPass123!",
        }
        defaults.update(extra_fields)
        password = defaults.pop("password")
        return self.user_model.objects.create_user(phone_number=phone_number, password=password, **defaults)

    def _create_ticket(self, user=None, **kwargs) -> Ticket:
        owner = user or self.user
        payload = {
            "subject": "موضوع تست",
            "category": Ticket.Category.GENERAL,
            "priority": Ticket.Priority.MEDIUM,
            "body": "متن اولیه تیکت",
        }
        payload.update(kwargs)
        return create_ticket(owner, **payload)

    def assertValidationMessage(self, callable_obj, expected_message: str):
        with self.assertRaises(ValidationError) as exc_info:
            callable_obj()
        self.assertEqual(exc_info.exception.messages[0], expected_message)

    def test_ticket_lifecycle_open_to_answered_to_waiting_staff_to_closed_to_reopen(self):
        ticket = self._create_ticket()
        self.assertEqual(ticket.status, Ticket.Status.OPEN)

        add_staff_reply(ticket.id, self.staff, "پاسخ پشتیبانی")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.ANSWERED)
        self.assertTrue(ticket.user_has_unread)
        self.assertEqual(ticket.assigned_to_id, self.staff.id)

        add_user_reply(ticket.id, self.user, "توضیح تکمیلی کاربر")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.WAITING_STAFF)
        self.assertFalse(ticket.last_reply_by_staff)

        close_ticket(ticket.id, self.user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.CLOSED)
        self.assertIsNotNone(ticket.closed_at)

        reopen_ticket(ticket.id, self.user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.WAITING_STAFF)
        self.assertIsNone(ticket.closed_at)

    def test_add_user_reply_rejects_closed_ticket(self):
        ticket = self._create_ticket()
        close_ticket(ticket.id, self.user)

        self.assertValidationMessage(
            lambda: add_user_reply(ticket.id, self.user, "پیام جدید"),
            "امکان پاسخ به تیکت بسته وجود ندارد.",
        )

    @override_settings(TICKET_MAX_OPEN_PER_USER=1)
    def test_create_ticket_respects_open_ticket_limit(self):
        self._create_ticket()

        self.assertValidationMessage(
            lambda: self._create_ticket(subject="موضوع دوم"),
            "سقف تیکت‌های باز همزمان شما تکمیل شده است.",
        )

    def test_regular_user_high_priority_is_downgraded_to_medium(self):
        ticket = self._create_ticket(priority=Ticket.Priority.HIGH)
        self.assertEqual(ticket.priority, Ticket.Priority.MEDIUM)

    def test_internal_note_does_not_change_status_or_unread_flag(self):
        ticket = self._create_ticket()
        original_status = ticket.status

        note = add_staff_reply(ticket.id, self.staff, "یادداشت داخلی", is_internal_note=True)
        ticket.refresh_from_db()

        self.assertTrue(note.is_internal_note)
        self.assertEqual(ticket.status, original_status)
        self.assertFalse(ticket.user_has_unread)
        self.assertIsNone(ticket.assigned_to_id)

    def test_staff_owner_reply_is_saved_as_user_message(self):
        staff_owner = self._create_user("09120000004", is_staff=True)
        staff_owner.user_permissions.add(self.reply_permission)
        ticket = self._create_ticket(user=staff_owner)

        message = add_staff_reply(ticket.id, staff_owner, "پیام پشتیبان مالک")
        ticket.refresh_from_db()

        self.assertFalse(message.is_staff_reply)
        self.assertFalse(message.is_internal_note)
        self.assertEqual(message.author_id, staff_owner.id)
        self.assertEqual(ticket.status, Ticket.Status.WAITING_STAFF)
        self.assertFalse(ticket.last_reply_by_staff)

    @override_settings(TICKET_REOPEN_DAYS=7)
    def test_reopen_after_deadline_is_rejected(self):
        ticket = self._create_ticket()
        close_ticket(ticket.id, self.user)
        Ticket.objects.filter(pk=ticket.pk).update(closed_at=timezone.now() - timedelta(days=8))

        self.assertValidationMessage(
            lambda: reopen_ticket(ticket.id, self.user),
            "مهلت بازگشایی این تیکت به پایان رسیده است.",
        )

    @override_settings(TICKET_MAX_MESSAGES_PER_HOUR=2, TICKET_MAX_OPEN_PER_USER=5)
    def test_message_rate_limit_is_enforced(self):
        ticket = self._create_ticket()
        add_user_reply(ticket.id, self.user, "پیام دوم")

        self.assertValidationMessage(
            lambda: add_user_reply(ticket.id, self.user, "پیام سوم"),
            "شما در هر ساعت حداکثر 2 پیام می‌توانید ارسال کنید.",
        )

    def test_add_staff_reply_rejects_closed_ticket(self):
        ticket = self._create_ticket()
        close_ticket(ticket.id, self.user)

        self.assertValidationMessage(
            lambda: add_staff_reply(ticket.id, self.staff, "پاسخ پس از بستن"),
            "امکان پاسخ به تیکت بسته وجود ندارد.",
        )


class TicketUserViewsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user_model = get_user_model()
        self.reply_permission = Permission.objects.get(codename="reply_ticket")
        self.user_a = self._create_user("09120000101", first_name="علی")
        self.user_b = self._create_user("09120000102", first_name="رضا")
        self.seller_user = self._create_user("09120000103", first_name="فروشنده")
        Seller.objects.create(
            user=self.seller_user,
            shop_name="فروشگاه تست",
            shop_address="آدرس تست",
            shop_phone_number="02112345678",
        )
        self.support = self._create_user("09120000104", first_name="پشتیبان", is_staff=True)
        self.support.user_permissions.add(self.reply_permission)
        self.client.force_login(self.user_a)

    def _create_user(self, phone_number: str, **extra_fields):
        defaults = {
            "first_name": "کاربر",
            "last_name": phone_number[-2:],
            "password": "StrongPass123!",
        }
        defaults.update(extra_fields)
        password = defaults.pop("password")
        return self.user_model.objects.create_user(phone_number=phone_number, password=password, **defaults)

    def _create_ticket(self, user, **kwargs):
        payload = {
            "subject": "موضوع نمایشی",
            "category": Ticket.Category.GENERAL,
            "priority": Ticket.Priority.MEDIUM,
            "body": "متن اولیه برای تست",
        }
        payload.update(kwargs)
        return create_ticket(user, **payload)

    def test_user_a_cannot_access_user_b_ticket(self):
        other_ticket = self._create_ticket(self.user_b, subject="تیکت محرمانه")

        list_response = self.client.get(reverse("tickets:list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertNotContains(list_response, "تیکت محرمانه")
        self.assertEqual(list(list_response.context["tickets"]), [])

        detail_response = self.client.get(reverse("tickets:detail", args=[other_ticket.pk]))
        self.assertEqual(detail_response.status_code, 404)

        reply_response = self.client.post(
            reverse("tickets:detail", args=[other_ticket.pk]),
            {"body": "پاسخ غیرمجاز"},
        )
        self.assertEqual(reply_response.status_code, 404)

        close_response = self.client.post(reverse("tickets:close", args=[other_ticket.pk]))
        self.assertEqual(close_response.status_code, 404)

    def test_guest_is_redirected_to_index(self):
        ticket = self._create_ticket(self.user_a)
        guest_client = Client()
        endpoints = [
            ("get", reverse("tickets:list")),
            ("get", reverse("tickets:create")),
            ("get", reverse("tickets:detail", args=[ticket.pk])),
            ("post", reverse("tickets:detail", args=[ticket.pk])),
            ("post", reverse("tickets:close", args=[ticket.pk])),
            ("post", reverse("tickets:reopen", args=[ticket.pk])),
        ]

        for method, url in endpoints:
            if method == "get":
                response = guest_client.get(url)
            else:
                response = guest_client.post(url, {"body": "تست"})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("index"))

    def test_internal_note_is_not_visible_in_user_detail_page(self):
        ticket = self._create_ticket(self.user_a)
        add_staff_reply(ticket.id, self.support, "پاسخ قابل مشاهده")
        add_staff_reply(ticket.id, self.support, "یادداشت داخلی مخفی", is_internal_note=True)

        response = self.client.get(reverse("tickets:detail", args=[ticket.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "یادداشت داخلی مخفی")
        self.assertTrue(all(not message.is_internal_note for message in response.context["ticket_messages"]))
        ticket.refresh_from_db()
        self.assertFalse(ticket.user_has_unread)

    def test_post_without_csrf_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user_a)

        response = csrf_client.post(
            reverse("tickets:create"),
            {
                "subject": "بدون csrf",
                "category": Ticket.Category.GENERAL,
                "priority": Ticket.Priority.MEDIUM,
                "body": "این درخواست باید رد شود.",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_seller_can_create_ticket(self):
        seller_client = Client()
        seller_client.force_login(self.seller_user)

        response = seller_client.post(
            reverse("tickets:create"),
            {
                "subject": "درخواست فروشنده",
                "category": Ticket.Category.BAZAR_ORDER,
                "priority": Ticket.Priority.MEDIUM,
                "body": "فروشنده باید بتواند تیکت ثبت کند.",
            },
        )

        created_ticket = Ticket.objects.get(subject="درخواست فروشنده")
        self.assertRedirects(response, reverse("tickets:detail", args=[created_ticket.pk]))
        self.assertEqual(created_ticket.user_id, self.seller_user.id)


class TicketStaffViewsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user_model = get_user_model()
        self.reply_permission = Permission.objects.get(codename="reply_ticket")
        self.manage_permission = Permission.objects.get(codename="manage_ticket")
        self.support_group = Group.objects.get(name="پشتیبان تیکت")

        self.user = self._create_user("09120000201", first_name="کاربر", last_name="عادی")
        self.normal_staff = self._create_user("09120000202", first_name="همکار", last_name="بدون‌دسترسی", is_staff=True)
        self.support = self._create_user("09120000203", first_name="پشتیبان", last_name="گروهی", is_staff=True)
        self.support.groups.add(self.support_group)
        self.manager = self._create_user("09120000204", first_name="مدیر", last_name="تیکت", is_staff=True)
        self.manager.user_permissions.add(self.reply_permission, self.manage_permission)
        self.other_support = self._create_user("09120000205", first_name="پشتیبان", last_name="دوم", is_staff=True)
        self.other_support.groups.add(self.support_group)
        self.non_support_user = self._create_user("09120000206", first_name="غیر", last_name="پشتیبان", is_staff=True)

    def _create_user(self, phone_number: str, **extra_fields):
        defaults = {
            "first_name": "کاربر",
            "last_name": phone_number[-2:],
            "password": "StrongPass123!",
        }
        defaults.update(extra_fields)
        password = defaults.pop("password")
        return self.user_model.objects.create_user(phone_number=phone_number, password=password, **defaults)

    def _create_ticket(self, user=None, **kwargs):
        owner = user or self.user
        payload = {
            "subject": "موضوع پنل پشتیبان",
            "category": Ticket.Category.GENERAL,
            "priority": Ticket.Priority.MEDIUM,
            "body": "متن اولیه",
        }
        payload.update(kwargs)
        return create_ticket(owner, **payload)

    def test_normal_user_gets_404_on_staff_dashboard(self):
        client = Client()
        client.force_login(self.user)

        response = client.get(reverse("tickets:staff-dashboard"))

        self.assertEqual(response.status_code, 404)

    def test_support_group_member_with_is_staff_has_access(self):
        ticket = self._create_ticket(subject="تیکت قابل مشاهده")
        client = Client()
        client.force_login(self.support)

        response = client.get(reverse("tickets:staff-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تیکت قابل مشاهده")
        self.assertIn(ticket, response.context["tickets"])

    def test_staff_reply_sets_answered_and_marks_user_unread(self):
        ticket = self._create_ticket()
        client = Client()
        client.force_login(self.support)

        response = client.post(
            reverse("tickets:staff-detail", args=[ticket.pk]),
            {
                "action": "reply",
                "body": "پاسخ پشتیبان",
            },
        )

        self.assertRedirects(response, reverse("tickets:staff-detail", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.ANSWERED)
        self.assertTrue(ticket.user_has_unread)

    def test_internal_note_is_not_visible_to_user(self):
        ticket = self._create_ticket()
        client = Client()
        client.force_login(self.support)
        client.post(
            reverse("tickets:staff-detail", args=[ticket.pk]),
            {
                "action": "reply",
                "body": "یادداشت داخلی محرمانه",
                "is_internal_note": "on",
            },
        )

        user_client = Client()
        user_client.force_login(self.user)
        response = user_client.get(reverse("tickets:detail", args=[ticket.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "یادداشت داخلی محرمانه")

    def test_assign_to_non_support_user_is_rejected(self):
        ticket = self._create_ticket()
        client = Client()
        client.force_login(self.manager)

        response = client.post(
            reverse("tickets:staff-detail", args=[ticket.pk]),
            {
                "action": "assign",
                "assigned_to": self.non_support_user.pk,
            },
            follow=True,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to_id, None)
        self.assertContains(response, "کاربر انتخاب‌شده امکان دریافت تیکت را ندارد.")

    def test_staff_dashboard_filters_work(self):
        my_waiting = self._create_ticket(
            user=self.manager,
            subject="گزارش فنی گوشی",
            category=Ticket.Category.TECHNICAL,
            priority=Ticket.Priority.HIGH,
        )
        assign_ticket(my_waiting.id, self.manager, self.support)
        add_user_reply(my_waiting.id, self.manager, "منتظر پاسخ پشتیبان هستم")

        other_ticket = self._create_ticket(
            subject="مساله بازار",
            category=Ticket.Category.BAZAR_ORDER,
            priority=Ticket.Priority.LOW,
        )
        assign_ticket(other_ticket.id, self.manager, self.other_support)

        unassigned_ticket = self._create_ticket(
            subject="بدون ارجاع",
            category=Ticket.Category.ACCOUNT,
            priority=Ticket.Priority.MEDIUM,
        )

        client = Client()
        client.force_login(self.support)

        response = client.get(
            reverse("tickets:staff-dashboard"),
            {
                "status": Ticket.Status.WAITING_STAFF,
                "category": Ticket.Category.TECHNICAL,
                "priority": Ticket.Priority.HIGH,
                "assignment": "me",
                "q": "گوشی",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["tickets"]), [my_waiting])
        self.assertNotIn(other_ticket, response.context["tickets"])
        self.assertNotIn(unassigned_ticket, response.context["tickets"])


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(),
)
class TicketAttachmentSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user_model = get_user_model()
        self.reply_permission = Permission.objects.get(codename="reply_ticket")
        self.user = self._create_user("09120000301", first_name="مالک")
        self.other_user = self._create_user("09120000302", first_name="دیگری")
        self.support = self._create_user("09120000303", first_name="پشتیبان", is_staff=True)
        self.support.user_permissions.add(self.reply_permission)

    def _create_user(self, phone_number: str, **extra_fields):
        defaults = {
            "first_name": "کاربر",
            "last_name": phone_number[-2:],
            "password": "StrongPass123!",
        }
        defaults.update(extra_fields)
        password = defaults.pop("password")
        return self.user_model.objects.create_user(phone_number=phone_number, password=password, **defaults)

    def _build_pdf(self, file_name: str = "ticket.pdf", *, valid: bool = True) -> SimpleUploadedFile:
        content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF" if valid else b"not-a-pdf"
        return SimpleUploadedFile(file_name, content, content_type="application/pdf")

    def _build_html_disguised_as_jpg(self) -> SimpleUploadedFile:
        return SimpleUploadedFile(
            "fake.jpg",
            b"<html><body>not-an-image</body></html>",
            content_type="image/jpeg",
        )

    def _create_ticket_with_attachment(self, attachment=None):
        return create_ticket(
            self.user,
            subject="تیکت دارای پیوست",
            category=Ticket.Category.GENERAL,
            priority=Ticket.Priority.MEDIUM,
            body="متن اولیه",
            attachment=attachment or self._build_pdf(),
        )

    def test_html_file_with_jpg_extension_is_rejected(self):
        with self.assertRaises(ValidationError) as exc_info:
            self._create_ticket_with_attachment(attachment=self._build_html_disguised_as_jpg())

        self.assertEqual(exc_info.exception.messages[0], "نوع واقعی فایل معتبر نیست.")
        self.assertEqual(Ticket.objects.count(), 0)

    def test_valid_pdf_attachment_is_accepted(self):
        ticket = self._create_ticket_with_attachment()
        message = ticket.messages.get()

        self.assertTrue(bool(message.attachment))
        self.assertTrue(message.attachment.name.startswith("ticket_attachments/"))
        self.assertTrue(message.attachment.name.endswith(".pdf"))

    def test_fake_pdf_without_header_is_rejected(self):
        with self.assertRaises(ValidationError) as exc_info:
            self._create_ticket_with_attachment(attachment=self._build_pdf(valid=False))

        self.assertEqual(exc_info.exception.messages[0], "نوع واقعی فایل معتبر نیست.")
        self.assertEqual(Ticket.objects.count(), 0)

    def test_attachment_download_by_other_user_returns_404(self):
        ticket = self._create_ticket_with_attachment()
        message = ticket.messages.get()
        client = Client()
        client.force_login(self.other_user)

        response = client.get(reverse("tickets:attachment-download", args=[message.pk]))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_download_attachment_with_security_headers(self):
        ticket = self._create_ticket_with_attachment()
        message = add_staff_reply(
            ticket.id,
            self.support,
            "یادداشت داخلی دارای فایل",
            is_internal_note=True,
            attachment=self._build_pdf("note.pdf"),
        )
        client = Client()
        client.force_login(self.support)

        response = client.get(reverse("tickets:attachment-download", args=[message.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_internal_note_attachment_is_hidden_from_ticket_owner(self):
        ticket = self._create_ticket_with_attachment()
        message = add_staff_reply(
            ticket.id,
            self.support,
            "یادداشت داخلی دارای فایل",
            is_internal_note=True,
            attachment=self._build_pdf("note.pdf"),
        )
        client = Client()
        client.force_login(self.user)

        response = client.get(reverse("tickets:attachment-download", args=[message.pk]))

        self.assertEqual(response.status_code, 404)
