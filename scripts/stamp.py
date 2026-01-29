import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.utils.config import deep_merge, load_and_merge_config


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            yield path


def _find_font(font_path: Optional[str]) -> Path:
    if font_path:
        p = Path(font_path).expanduser().resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Font not found: {p}")

    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return p
    raise FileNotFoundError("No usable font found. Please pass --font /path/to/font.ttf")


def _font_size(width: int, scale: float, min_px: int, max_px: int) -> int:
    size = int(width * scale)
    return max(min_px, min(size, max_px))


def _draw_text(
    base: Image.Image,
    text: str,
    position: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    align: str,
    fill: Tuple[int, int, int, int],
    stroke_fill: Tuple[int, int, int, int],
    stroke_width: int,
):
    draw = ImageDraw.Draw(base)
    draw.multiline_text(
        position,
        text,
        font=font,
        fill=fill,
        align=align,
        spacing=int(font.size * 0.2),
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _measure_text(text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=int(font.size * 0.2))
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _apply_stamp(
    img_path: Path,
    out_path: Path,
    left_text: str,
    right_text: str,
    font_path: Path,
    logo_path: Optional[Path],
    logo_scale: float,
    logo_max_h_ratio: float,
    scale: float,
    min_px: int,
    max_px: int,
    padding: int,
    opacity: float,
    stroke_width: int,
):
    with Image.open(img_path) as im:
        base = im.convert("RGBA")

    w, h = base.size
    font_size = _font_size(w, scale, min_px, max_px)
    font = ImageFont.truetype(str(font_path), font_size)

    left_text = left_text.replace("\\n", "\n") if left_text else ""
    right_text = right_text.replace("\\n", "\n") if right_text else ""

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    alpha = max(0, min(255, int(255 * opacity)))
    fill = (255, 255, 255, alpha)
    stroke_fill = (0, 0, 0, int(alpha * 0.8))

    logo_h = 0
    if logo_path:
        with Image.open(logo_path) as logo_img:
            logo = logo_img.convert("RGBA")
        target_w = int(w * logo_scale)
        target_w = max(24, target_w)
        ratio = logo.size[1] / logo.size[0] if logo.size[0] else 1
        target_h = int(target_w * ratio)
        max_h = int(h * logo_max_h_ratio)
        if target_h > max_h:
            target_h = max_h
            target_w = int(target_h / ratio) if ratio else target_w
        logo = logo.resize((target_w, target_h), Image.LANCZOS)
        overlay.alpha_composite(logo, (padding, padding))
        logo_h = target_h

    if left_text:
        left_y = padding + (logo_h + padding // 2 if logo_h else 0)
        _draw_text(
            overlay,
            left_text,
            (padding, left_y),
            font,
            align="left",
            fill=fill,
            stroke_fill=stroke_fill,
            stroke_width=stroke_width,
        )

    if right_text:
        text_w, text_h = _measure_text(right_text, font)
        x = max(padding, w - text_w - padding)
        y = max(padding, h - text_h - padding)
        _draw_text(
            overlay,
            right_text,
            (x, y),
            font,
            align="right",
            fill=fill,
            stroke_fill=stroke_fill,
            stroke_width=stroke_width,
        )

    stamped = Image.alpha_composite(base, overlay)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if im.mode in ("RGB", "L"):
        stamped = stamped.convert(im.mode)
    else:
        stamped = stamped.convert("RGB")

    stamped.save(out_path)


def _merge_cli(cfg: dict, args: argparse.Namespace) -> dict:
    cli = {}
    if args.in_dir:
        cli["stamp_input"] = args.in_dir
    if args.out:
        cli["stamp_output"] = args.out
    if args.date:
        cli["stamp_date"] = args.date
    if args.left_text is not None:
        cli["stamp_left_text"] = args.left_text
    if args.right_text is not None:
        cli["stamp_right_text"] = args.right_text
    if args.font:
        cli["stamp_font"] = args.font
    if args.logo:
        cli["stamp_logo"] = args.logo
    if args.logo_scale is not None:
        cli["stamp_logo_scale"] = args.logo_scale
    if args.logo_max_h is not None:
        cli["stamp_logo_max_h"] = args.logo_max_h
    if args.scale is not None:
        cli["stamp_scale"] = args.scale
    if args.opacity is not None:
        cli["stamp_opacity"] = args.opacity
    if args.padding is not None:
        cli["stamp_padding"] = args.padding
    if args.stroke_width is not None:
        cli["stamp_stroke_width"] = args.stroke_width
    if args.min_px is not None:
        cli["stamp_min_px"] = args.min_px
    if args.max_px is not None:
        cli["stamp_max_px"] = args.max_px
    return deep_merge(cfg, cli)


def main(argv: List[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    default_config = root / "config" / "default.yaml"

    parser = argparse.ArgumentParser(description="Batch watermark stamping")
    parser.add_argument("--config", default=str(default_config))
    parser.add_argument("--in", dest="in_dir", help="Input root (default: ./data)")
    parser.add_argument("--out", help="Output root (default: ./out)")
    parser.add_argument("--date", help="Date folder (YYYYMMDD). If omitted, process all dates")
    parser.add_argument("--left-text", help="Left-top text")
    parser.add_argument("--right-text", help="Right-bottom text")
    parser.add_argument("--font", help="TTF/TTC font path")
    parser.add_argument("--logo", help="Logo image path")
    parser.add_argument("--logo-scale", type=float, help="Logo width ratio (default: 0.12)")
    parser.add_argument("--logo-max-h", type=float, help="Logo max height ratio (default: 0.2)")
    parser.add_argument("--scale", type=float, help="Font size scale of width (default: 0.04)")
    parser.add_argument("--min-px", type=int, help="Min font size")
    parser.add_argument("--max-px", type=int, help="Max font size")
    parser.add_argument("--opacity", type=float, help="Text opacity 0..1 (default: 0.6)")
    parser.add_argument("--padding", type=int, help="Padding in px (default: 24)")
    parser.add_argument("--stroke-width", type=int, help="Stroke width (default: 2)")

    args = parser.parse_args(argv)

    cfg = load_and_merge_config(Path(args.config))
    cfg = _merge_cli(cfg, args)

    in_root = Path(cfg.get("stamp_input", "./data")).expanduser().resolve()
    out_root = Path(cfg.get("stamp_output", "./out")).expanduser().resolve()
    date = cfg.get("stamp_date")

    left_text = cfg.get("stamp_left_text", "")
    right_text = cfg.get("stamp_right_text", "")
    if not left_text and not right_text:
        raise ValueError("left_text and right_text are both empty; provide at least one")

    font_path = _find_font(cfg.get("stamp_font"))
    logo_path = cfg.get("stamp_logo")
    logo_path = Path(logo_path).expanduser().resolve() if logo_path else None
    if logo_path and not logo_path.exists():
        raise FileNotFoundError(f"Logo not found: {logo_path}")
    logo_scale = float(cfg.get("stamp_logo_scale", 0.12))
    logo_max_h_ratio = float(cfg.get("stamp_logo_max_h", 0.2))
    scale = float(cfg.get("stamp_scale", 0.04))
    opacity = float(cfg.get("stamp_opacity", 0.6))
    padding = int(cfg.get("stamp_padding", 24))
    stroke_width = int(cfg.get("stamp_stroke_width", 2))
    min_px = int(cfg.get("stamp_min_px", 18))
    max_px = int(cfg.get("stamp_max_px", 96))

    roots = []
    if date:
        roots = [in_root / date]
    else:
        roots = [p for p in in_root.iterdir() if p.is_dir()]

    total = 0
    for day_root in roots:
        if not day_root.exists():
            continue
        for img_path in _iter_images(day_root):
            rel = img_path.relative_to(in_root)
            out_path = out_root / rel
            _apply_stamp(
                img_path,
                out_path,
                left_text,
                right_text,
                font_path,
                logo_path,
                logo_scale,
                logo_max_h_ratio,
                scale,
                min_px,
                max_px,
                padding,
                opacity,
                stroke_width,
            )
            total += 1

    summary = {
        "input": str(in_root),
        "output": str(out_root),
        "date": date,
        "left_text": left_text,
        "right_text": right_text,
        "font": str(font_path),
        "logo": str(logo_path) if logo_path else None,
        "total": total,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
