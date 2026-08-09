from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


STANDARD_IMAGE_SIZE = (1504, 1024)
THUMBNAIL_SIZE = (376, 256)
THUMBNAIL_SUFFIX = f".thumb-{THUMBNAIL_SIZE[0]}x{THUMBNAIL_SIZE[1]}-v2.jpg"
THUMBNAIL_BACKGROUND = (5, 10, 18)


def thumbnail_path_for(source_path: str | Path) -> Path:
    source = Path(source_path)
    return source.with_name(f"{source.stem}{THUMBNAIL_SUFFIX}")


def ensure_thumbnail(source_path: str | Path, *, size: tuple[int, int] = THUMBNAIL_SIZE) -> str:
    source = Path(source_path)
    target = thumbnail_path_for(source)
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return str(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        frame = image.convert("RGBA")
        contained = ImageOps.contain(frame, size, method=Image.Resampling.LANCZOS)
        background = Image.new("RGBA", size, THUMBNAIL_BACKGROUND + (255,))
        offset = (
            max(0, (size[0] - contained.width) // 2),
            max(0, (size[1] - contained.height) // 2),
        )
        background.paste(contained, offset, contained)
        composited = background.convert("RGB")
        composited.save(target, format="JPEG", quality=82, optimize=True)
    return str(target)
