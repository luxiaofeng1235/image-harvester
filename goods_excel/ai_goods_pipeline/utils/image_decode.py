from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError


def probe_image_content(content: bytes) -> tuple[int, int, str] | None:
    if not content:
        return None
    try:
        with Image.open(BytesIO(content)) as image:
            image.load()
            width, height = image.size
            if width <= 0 or height <= 0:
                return None
            return width, height, str(image.format or "").lower()
    except (OSError, UnidentifiedImageError, ValueError):
        return None
