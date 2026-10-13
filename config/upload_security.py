from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError


def _format_size_limit(limit_bytes: int) -> str:
    if limit_bytes % (1024 * 1024) == 0:
        return f"{limit_bytes // (1024 * 1024)} مگابایت"
    return f"{round(limit_bytes / (1024 * 1024), 1)} مگابایت"


def _get_extension(file_name: str) -> str:
    return Path(file_name or "").suffix.lower()


def _read_file_header(uploaded_file, size: int = 512) -> bytes:
    current_position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    try:
        uploaded_file.seek(0)
        return uploaded_file.read(size)
    finally:
        uploaded_file.seek(current_position)


def _sniff_image_type(uploaded_file) -> str | None:
    current_position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
            detected_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    finally:
        uploaded_file.seek(current_position)

    format_map = {
        "JPEG": "jpeg",
        "PNG": "png",
        "WEBP": "webp",
    }
    return format_map.get(detected_format)


def _sniff_video_type(uploaded_file) -> str | None:
    header = _read_file_header(uploaded_file, size=512)
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand == b"qt  ":
            return "mov"
        if brand in {
            b"isom",
            b"iso2",
            b"avc1",
            b"mp41",
            b"mp42",
            b"M4V ",
            b"MSNV",
        }:
            return "mp4"
    if header.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in header.lower():
        return "webm"
    return None


@dataclass(frozen=True)
class UploadPolicy:
    allowed_extensions_by_type: dict[str, set[str]]
    max_size_bytes: int
    kind: str

    @property
    def allowed_extensions(self) -> set[str]:
        extensions: set[str] = set()
        for values in self.allowed_extensions_by_type.values():
            extensions.update(values)
        return extensions


def _build_policies() -> dict[str, UploadPolicy]:
    return {
        "public_image": UploadPolicy(
            allowed_extensions_by_type={
                "jpeg": {".jpg", ".jpeg"},
                "png": {".png"},
                "webp": {".webp"},
            },
            max_size_bytes=int(getattr(settings, "PUBLIC_IMAGE_MAX_UPLOAD_BYTES", 5 * 1024 * 1024)),
            kind="image",
        ),
        "challenge_evidence_any": UploadPolicy(
            allowed_extensions_by_type={
                "jpeg": {".jpg", ".jpeg"},
                "png": {".png"},
                "webp": {".webp"},
                "mp4": {".mp4", ".m4v"},
                "mov": {".mov"},
                "webm": {".webm"},
            },
            max_size_bytes=int(getattr(settings, "CHALLENGE_EVIDENCE_VIDEO_MAX_UPLOAD_BYTES", 50 * 1024 * 1024)),
            kind="any",
        ),
        "challenge_evidence_image": UploadPolicy(
            allowed_extensions_by_type={
                "jpeg": {".jpg", ".jpeg"},
                "png": {".png"},
                "webp": {".webp"},
            },
            max_size_bytes=int(getattr(settings, "CHALLENGE_EVIDENCE_IMAGE_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)),
            kind="image",
        ),
        "challenge_evidence_video": UploadPolicy(
            allowed_extensions_by_type={
                "mp4": {".mp4", ".m4v"},
                "mov": {".mov"},
                "webm": {".webm"},
            },
            max_size_bytes=int(getattr(settings, "CHALLENGE_EVIDENCE_VIDEO_MAX_UPLOAD_BYTES", 50 * 1024 * 1024)),
            kind="video",
        ),
    }


def _detect_file_type(uploaded_file, *, policy: UploadPolicy) -> str | None:
    if policy.kind in {"image", "any"}:
        detected_image_type = _sniff_image_type(uploaded_file)
        if detected_image_type is not None:
            return detected_image_type
    if policy.kind in {"video", "any"}:
        detected_video_type = _sniff_video_type(uploaded_file)
        if detected_video_type is not None:
            return detected_video_type
    return None


def validate_uploaded_file(uploaded_file, policy_name: str) -> str:
    if not uploaded_file:
        raise ValidationError("فایل ارسالی نامعتبر است.")

    policies = _build_policies()
    policy = policies[policy_name]
    extension = _get_extension(getattr(uploaded_file, "name", ""))

    if extension not in policy.allowed_extensions:
        allowed_extensions = "، ".join(sorted(policy.allowed_extensions))
        raise ValidationError(f"پسوند فایل مجاز نیست. پسوندهای مجاز: {allowed_extensions}")

    file_size = int(getattr(uploaded_file, "size", 0) or 0)
    if file_size <= 0:
        raise ValidationError("فایل ارسالی خالی یا نامعتبر است.")
    if file_size > policy.max_size_bytes:
        raise ValidationError(f"حجم فایل بیش از حد مجاز است. حداکثر حجم: {_format_size_limit(policy.max_size_bytes)}")

    detected_type = _detect_file_type(uploaded_file, policy=policy)
    if detected_type is None:
        raise ValidationError("نوع واقعی فایل معتبر نیست.")

    if extension not in policy.allowed_extensions_by_type.get(detected_type, set()):
        raise ValidationError("پسوند فایل با محتوای واقعی آن هم‌خوانی ندارد.")

    return detected_type


@deconstructible
class UploadPolicyValidator:
    def __init__(self, policy_name: str):
        self.policy_name = policy_name

    def __call__(self, uploaded_file):
        validate_uploaded_file(uploaded_file, self.policy_name)


@deconstructible
class PrivateChallengeEvidenceStorage(FileSystemStorage):
    def __init__(self, location=None):
        super().__init__(location=location)

    @property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def url(self, name):
        base_url = reverse("challenge-evidence-download")
        return f"{base_url}?{urlencode({'name': name})}"


private_challenge_evidence_storage = PrivateChallengeEvidenceStorage()


def private_challenge_evidence_upload_to(instance, filename: str) -> str:
    extension = _get_extension(filename) or ".bin"
    return f"challenge_evidence/{uuid4().hex}{extension}"
