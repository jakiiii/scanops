from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_IMAGE_UPLOAD_SIZE = 10 * 1024 * 1024


def validate_uploaded_image(file_obj):
    if not file_obj:
        return

    extension = Path(file_obj.name or "").suffix.lower().lstrip(".")
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Only JPG and PNG image files are allowed.")

    if getattr(file_obj, "size", 0) > MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError("Image files must be 10 MB or smaller.")

    if not hasattr(file_obj, "seek"):
        raise ValidationError("Uploaded file is not a valid image.")

    try:
        file_obj.seek(0)
        image = Image.open(file_obj)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Uploaded file is not a valid image.")
    finally:
        file_obj.seek(0)
