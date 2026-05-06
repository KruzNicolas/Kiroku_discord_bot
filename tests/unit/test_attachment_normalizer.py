from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from discord_bot.attachments.normalizer import (
    AttachmentNormalizationError,
    normalize_attachment,
)


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_type"),
    [
        ("photo.jpg", "application/octet-stream", "image/jpeg"),
        ("photo.png", "", "image/png"),
    ],
)
def test_normalize_attachment_infers_type_from_filename_when_generic_or_missing(
    filename: str, content_type: str, expected_type: str
) -> None:
    normalized = normalize_attachment(
        filename=filename,
        content_type=content_type,
        data=b"binary-image-data",
        max_size_bytes=1024,
    )

    assert normalized.filename == filename
    assert normalized.content_type == expected_type
    assert normalized.data == b"binary-image-data"


def test_normalize_attachment_accepts_png_content_type_with_parameters() -> None:
    png_data = b"\x89PNG\r\n\x1a\n" + b"payload"

    normalized = normalize_attachment(
        filename="photo.png",
        content_type="image/png; charset=binary",
        data=png_data,
        max_size_bytes=1024,
    )

    assert normalized.filename == "photo.png"
    assert normalized.content_type == "image/png"
    assert normalized.data == png_data


def test_normalize_attachment_sniffs_png_when_content_type_unknown() -> None:
    png_data = b"\x89PNG\r\n\x1a\n" + b"payload"

    normalized = normalize_attachment(
        filename="upload.bin",
        content_type="application/octet-stream",
        data=png_data,
        max_size_bytes=1024,
    )

    assert normalized.filename == "upload.bin"
    assert normalized.content_type == "image/png"
    assert normalized.data == png_data


def test_normalize_attachment_accepts_webp_content_type_and_converts_to_jpeg() -> None:
    webp_data = _webp_bytes(mode="RGB")

    normalized = normalize_attachment(
        filename="receipt.webp",
        content_type="image/webp",
        data=webp_data,
        max_size_bytes=1024 * 1024,
    )

    assert normalized.filename == "receipt.jpg"
    assert normalized.content_type == "image/jpeg"
    assert normalized.data.startswith(b"\xff\xd8\xff")


def test_normalize_attachment_infers_webp_from_extension_when_content_type_generic() -> (
    None
):
    webp_data = _webp_bytes(mode="RGB")

    normalized = normalize_attachment(
        filename="receipt.webp",
        content_type="application/octet-stream",
        data=webp_data,
        max_size_bytes=1024 * 1024,
    )

    assert normalized.filename == "receipt.jpg"
    assert normalized.content_type == "image/jpeg"
    assert normalized.data.startswith(b"\xff\xd8\xff")


def test_normalize_attachment_sniffs_webp_signature_when_filename_and_type_unknown() -> (
    None
):
    webp_data = _webp_bytes(mode="RGB")

    normalized = normalize_attachment(
        filename="upload.bin",
        content_type="binary/octet-stream",
        data=webp_data,
        max_size_bytes=1024 * 1024,
    )

    assert normalized.filename == "upload.jpg"
    assert normalized.content_type == "image/jpeg"
    assert normalized.data.startswith(b"\xff\xd8\xff")


def test_normalize_attachment_flattens_transparent_webp_to_jpeg_with_no_alpha() -> None:
    webp_data = _webp_bytes(mode="RGBA")

    normalized = normalize_attachment(
        filename="transparent.webp",
        content_type="image/webp",
        data=webp_data,
        max_size_bytes=1024 * 1024,
    )

    with Image.open(BytesIO(normalized.data)) as converted:
        converted.load()
        assert converted.mode == "RGB"
        pixel = converted.getpixel((0, 0))

    assert all(channel >= 240 for channel in pixel)


def test_normalize_attachment_rejects_truly_unsupported_payload() -> None:
    with pytest.raises(
        AttachmentNormalizationError, match="Unsupported attachment type"
    ):
        normalize_attachment(
            filename="payload.bin",
            content_type="application/octet-stream",
            data=b"not-an-image",
            max_size_bytes=1024,
        )


@pytest.mark.parametrize(
    ("filename", "content_type", "data"),
    [
        (
            "photo.heic",
            "application/octet-stream",
            b"binary-image-data",
        ),
        (
            "photo.heif",
            "application/octet-stream",
            b"binary-image-data",
        ),
        (
            "upload.bin",
            "image/heic",
            b"\x00\x00\x00\x18ftypheic" + b"payload",
        ),
        (
            "upload.bin",
            "image/heif",
            b"\x00\x00\x00\x18ftypheif" + b"payload",
        ),
    ],
)
def test_normalize_attachment_rejects_heic_and_heif(
    filename: str, content_type: str, data: bytes
) -> None:
    with pytest.raises(
        AttachmentNormalizationError, match="Unsupported attachment type"
    ):
        normalize_attachment(
            filename=filename,
            content_type=content_type,
            data=data,
            max_size_bytes=1024,
        )


def _webp_bytes(*, mode: str) -> bytes:
    image = (
        Image.new("RGB", (4, 4), color=(220, 10, 10))
        if mode == "RGB"
        else Image.new("RGBA", (4, 4), color=(0, 0, 0, 0))
    )

    output = BytesIO()
    image.save(output, format="WEBP")
    return output.getvalue()
