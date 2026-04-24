from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError


def probe_image_header(content: bytes) -> tuple[int, int, str] | None:
    return _probe_image(content, load_image=False)


def probe_image_content(content: bytes) -> tuple[int, int, str] | None:
    return _probe_image(content, load_image=True)


def _probe_image(content: bytes, *, load_image: bool) -> tuple[int, int, str] | None:
    if not content:
        return None
    try:
        with Image.open(BytesIO(content)) as image:
            if load_image:
                image.load()
            width, height = image.size
            if width <= 0 or height <= 0:
                return None
            return width, height, str(image.format or "").lower()
    except (OSError, UnidentifiedImageError, ValueError):
        return None
