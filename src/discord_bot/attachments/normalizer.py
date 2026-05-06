from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from discord_bot.domain.models import NormalizedAttachment

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
}


class AttachmentNormalizationError(ValueError):
    pass


def normalize_attachment(
    *, filename: str, content_type: str, data: bytes, max_size_bytes: int
) -> NormalizedAttachment:
    if len(data) > max_size_bytes:
        raise AttachmentNormalizationError("Attachment exceeds configured size limit")

    media = _resolve_media_type(content_type=content_type, filename=filename, data=data)
    if media not in ALLOWED_CONTENT_TYPES:
        raise AttachmentNormalizationError("Unsupported attachment type")

    if media == "image/webp":
        return NormalizedAttachment(
            filename=_to_jpeg_filename(filename),
            content_type="image/jpeg",
            data=_convert_webp_to_jpeg(data),
        )

    normalized_type = "image/jpeg" if media == "image/jpg" else media
    return NormalizedAttachment(
        filename=filename, content_type=normalized_type, data=data
    )


def _resolve_media_type(*, content_type: str, filename: str, data: bytes) -> str:
    media = _normalize_content_type(content_type)
    if media and media not in {"application/octet-stream", "binary/octet-stream"}:
        if media in ALLOWED_CONTENT_TYPES:
            return media

        sniffed = _sniff_media_type(data)
        if sniffed:
            return sniffed

        return media

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    inferred_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }
    inferred = inferred_types.get(extension)
    if inferred:
        return inferred

    sniffed = _sniff_media_type(data)
    if sniffed:
        return sniffed

    return media


def _normalize_content_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].lower().strip()


def _sniff_media_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"

    return None


def _to_jpeg_filename(filename: str) -> str:
    if "." not in filename:
        return f"{filename}.jpg"

    stem, _ = filename.rsplit(".", 1)
    return f"{stem}.jpg"


def _convert_webp_to_jpeg(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            rgb_image = _flatten_if_transparent(image)
            output = BytesIO()
            rgb_image.save(output, format="JPEG")
            return output.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise AttachmentNormalizationError("Unsupported attachment type") from exc


def _flatten_if_transparent(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        white_background = Image.new("RGB", rgba.size, (255, 255, 255))
        white_background.paste(rgba, mask=rgba.split()[3])
        return white_background

    return image.convert("RGB")
