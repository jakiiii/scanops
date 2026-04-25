from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError


MAX_ISSUE_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_CONTENT_TYPES = IMAGE_CONTENT_TYPES | VIDEO_CONTENT_TYPES


def validate_issue_attachment(uploaded_file):
    if not uploaded_file:
        return

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Unsupported file type. Allowed formats: jpg, jpeg, png, webp, mp4, webm, mov."
        )

    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Unsupported file content type.")

    if uploaded_file.size > MAX_ISSUE_ATTACHMENT_SIZE:
        raise ValidationError("Attachment is too large. Maximum file size is 25MB.")

