from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    PROJECT_ROOT
    / "Andriod Version"
    / "frontend"
    / "android"
    / "app"
    / "src"
    / "main"
    / "res"
    / "mipmap-xxxhdpi"
    / "ic_launcher.png"
)
TARGET = PROJECT_ROOT / "packaging" / "hp-simulator.ico"


def main() -> None:
    if TARGET.is_file() and TARGET.stat().st_size > 0:
        return

    if SOURCE.is_file():
        with Image.open(SOURCE) as image:
            icon = image.convert("RGBA")
    else:
        icon = Image.new("RGBA", (256, 256), "#1c1a2e")
        draw = ImageDraw.Draw(icon)
        draw.rounded_rectangle((16, 16, 240, 240), radius=36, fill="#2f2b4a")
        draw.rectangle((62, 62, 194, 194), outline="#d8b56a", width=12)
        draw.line((128, 62, 128, 194), fill="#d8b56a", width=12)
        draw.line((62, 128, 194, 128), fill="#d8b56a", width=12)

    icon.save(
        TARGET,
        format="ICO",
        sizes=[
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )


if __name__ == "__main__":
    main()
