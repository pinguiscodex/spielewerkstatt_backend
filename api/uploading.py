from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import gzip
import mimetypes
import shutil
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import get_valid_filename
from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
DATA_FOLDER_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "txt", "zip", "rar", "mp3", "mp4", "avi"}
GAME_FILE_EXTENSIONS = {
    "exe", "msi", "bat", "cmd", "com", "scr", "pif", "vbs", "vbe", "js", "jse", "wsf", "wsc", "ps1", "msc",
    "appx", "appxbundle", "msix", "msixbundle", "dmg", "pkg", "app", "mpkg", "deb", "rpm", "tar.gz",
    "tar.bz2", "tar.xz", "appimage", "run", "bin", "sh", "bash", "zsh", "flatpak", "snap", "apk", "aab",
    "xapk", "apks", "apkdm", "ipa", "py", "pyz", "pyw", "pyc", "pyo", "jar", "war", "ear", "dll", "so",
    "dylib", "drv", "sys", "efi", "zip", "rar", "7z", "tar", "gz", "bz2", "xz", "lz", "lzma", "tlz",
    "txz", "tbz", "tbz2", "tgz", "z", "zst", "tzst", "lz4", "br",
}
MULTI_PART_EXTENSIONS = ("tar.gz", "tar.bz2", "tar.xz")


def get_extension(filename: str) -> str:
    lower_name = filename.lower()
    for extension in MULTI_PART_EXTENSIONS:
        if lower_name.endswith(f".{extension}"):
            return extension
    return lower_name.rsplit(".", 1)[-1] if "." in lower_name else ""


def normalize_relative_path(path: str | None) -> str:
    if not path:
        return ""
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith("media/"):
        normalized = normalized[len("media/") :]
    return normalized


def media_url(request, path: str | None) -> str | None:
    normalized = normalize_relative_path(path)
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://")):
        return normalized
    return request.build_absolute_uri(f"{settings.MEDIA_URL}{normalized}")


def resolve_existing_media_path(relative_path: str | None) -> Path | None:
    normalized = normalize_relative_path(relative_path)
    if not normalized:
        return None
    candidates = [
        settings.MEDIA_ROOT / normalized,
        settings.LEGACY_UPLOAD_ROOT / normalized,
        settings.LEGACY_UPLOAD_ROOT / "assets" / normalized,
    ]
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists():
            return candidate
    return None


def delete_media_path(relative_path: str | None) -> None:
    path = resolve_existing_media_path(relative_path)
    if not path:
        return
    media_root = settings.MEDIA_ROOT.resolve()
    try:
        path.relative_to(media_root)
    except ValueError:
        return
    path.unlink(missing_ok=True)


def delete_many(paths: Iterable[str | None]) -> None:
    for path in paths:
        delete_media_path(path)


def validate_image(upload: UploadedFile, required: bool = True) -> None:
    if not upload:
        if required:
            raise ValidationError("Image is required.")
        return
    if upload.size > settings.MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError("Image file size exceeds 5MB.")
    extension = get_extension(upload.name)
    if extension not in IMAGE_EXTENSIONS:
        raise ValidationError("Invalid image file type.")
    try:
        image = Image.open(upload)
        image.verify()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("Uploaded file is not a valid image.")
    finally:
        upload.seek(0)


def validate_game_file(upload: UploadedFile) -> None:
    if not upload:
        raise ValidationError("Game file is required.")
    if upload.size > settings.MAX_GAME_UPLOAD_SIZE:
        raise ValidationError("Game file exceeds the 500MB limit.")
    extension = get_extension(upload.name)
    if extension not in GAME_FILE_EXTENSIONS:
        raise ValidationError(f"File type .{extension or 'unknown'} is not allowed.")


def validate_data_file(upload: UploadedFile) -> None:
    if not upload:
        raise ValidationError("File is required.")
    if upload.size > settings.MAX_DATA_FOLDER_UPLOAD_SIZE:
        raise ValidationError("File size exceeds 50MB.")
    extension = get_extension(upload.name)
    if extension not in DATA_FOLDER_EXTENSIONS:
        raise ValidationError(f"File type .{extension or 'unknown'} is not allowed.")


def save_uploaded_file(upload: UploadedFile, subdir: str, prefix: str) -> str:
    extension = get_extension(upload.name)
    filename = get_valid_filename(upload.name.rsplit("/", 1)[-1])
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    unique_name = f"{prefix}_{stem}_{uuid.uuid4().hex[:12]}"
    if extension:
        unique_name = f"{unique_name}.{extension}"
    relative_path = normalize_relative_path(f"uploads/{subdir}/{unique_name}")
    destination = settings.MEDIA_ROOT / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb+") as target:
        for chunk in upload.chunks():
            target.write(chunk)
    return relative_path


def gzip_file(relative_path: str, compressed_prefix: str) -> str:
    source = settings.MEDIA_ROOT / normalize_relative_path(relative_path)
    compressed_relative = normalize_relative_path(f"uploads/games/{compressed_prefix}_{uuid.uuid4().hex[:12]}.gz")
    destination = settings.MEDIA_ROOT / compressed_relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, gzip.open(destination, "wb", compresslevel=9) as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
    source.unlink(missing_ok=True)
    return compressed_relative


def content_type_for(path: str | None) -> str:
    guessed, _ = mimetypes.guess_type(path or "")
    return guessed or "application/octet-stream"
