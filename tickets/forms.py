from django import forms
from django.contrib.auth import get_user_model

from config.upload_security import validate_uploaded_file

from .models import Ticket
from .permissions import can_staff_ticket, can_manage_ticket, staff_ticket_users_queryset


class TicketCreateForm(forms.Form):
    subject = forms.CharField(
        label="موضوع",
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "موضوع تیکت را بنویسید",
            }
        ),
    )
    category = forms.ChoiceField(
        label="دسته‌بندی",
        choices=Ticket.Category.choices,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    priority = forms.ChoiceField(
        label="اولویت",
        choices=Ticket.Priority.choices,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    body = forms.CharField(
        label="متن پیام",
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "مشکل یا درخواست خود را کامل توضیح دهید",
            }
        ),
    )
    attachment = forms.FileField(
        label="پیوست",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )

    def clean_subject(self):
        subject = (self.cleaned_data.get("subject") or "").strip()
        if not subject:
            raise forms.ValidationError("موضوع تیکت نمی‌تواند خالی باشد.")
        if len(subject) > 200:
            raise forms.ValidationError("موضوع تیکت نمی‌تواند بیشتر از ۲۰۰ کاراکتر باشد.")
        return subject

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("متن پیام نمی‌تواند خالی باشد.")
        if len(body) > 5000:
            raise forms.ValidationError("متن پیام نمی‌تواند بیشتر از ۵۰۰۰ کاراکتر باشد.")
        return body

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            validate_uploaded_file(attachment, "ticket_attachment")
        return attachment


class TicketReplyForm(forms.Form):
    body = forms.CharField(
        label="پاسخ شما",
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "پاسخ خود را بنویسید",
            }
        ),
    )
    attachment = forms.FileField(
        label="پیوست",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("متن پیام نمی‌تواند خالی باشد.")
        if len(body) > 5000:
            raise forms.ValidationError("متن پیام نمی‌تواند بیشتر از ۵۰۰۰ کاراکتر باشد.")
        return body

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            validate_uploaded_file(attachment, "ticket_attachment")
        return attachment


class StaffTicketReplyForm(TicketReplyForm):
    is_internal_note = forms.BooleanField(
        label="یادداشت داخلی",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class StaffTicketAssignForm(forms.Form):
    assigned_to = forms.CharField(
        label="ارجاع به",
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.allowed_assignees = staff_ticket_users_queryset(get_user_model())
        self.fields["assigned_to"].widget.choices = [
            ("", "انتخاب پشتیبان"),
            *[
                (str(user.pk), user.get_full_name() or user.phone_number)
                for user in self.allowed_assignees
            ],
        ]

    def clean_assigned_to(self):
        assignee_id = (self.cleaned_data.get("assigned_to") or "").strip()
        if not assignee_id:
            raise forms.ValidationError("انتخاب پشتیبان الزامی است.")
        assignee = get_user_model().objects.filter(pk=assignee_id).first()
        if not can_staff_ticket(assignee):
            raise forms.ValidationError("کاربر انتخاب‌شده امکان دریافت تیکت را ندارد.")
        return assignee

    def clean(self):
        cleaned_data = super().clean()
        if self.actor is not None and not can_manage_ticket(self.actor):
            raise forms.ValidationError("شما اجازه ارجاع تیکت را ندارید.")
        return cleaned_data


class StaffTicketPriorityForm(forms.Form):
    priority = forms.ChoiceField(
        label="اولویت",
        choices=Ticket.Priority.choices,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor

    def clean(self):
        cleaned_data = super().clean()
        if self.actor is not None and not can_manage_ticket(self.actor):
            raise forms.ValidationError("شما اجازه تغییر اولویت تیکت را ندارید.")
        return cleaned_data
