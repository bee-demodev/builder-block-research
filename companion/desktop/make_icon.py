"""Write ``icon.ico`` (the window and exe icon): three candles on a dark rounded square.

    python -m companion.desktop.make_icon

Needs Pillow (``companion/requirements-build.txt``). The committed ``icon.ico`` is what the
app uses; run this only to change it.
"""

from __future__ import annotations

from pathlib import Path

SIZE = 256
BACKGROUND = (22, 26, 33, 255)
UP = (38, 166, 154, 255)
DOWN = (239, 83, 80, 255)
# (centre x, wick top, body top, body bottom, wick bottom, colour) on a 256 grid
CANDLES = (
    (68, 92, 116, 188, 210, DOWN),
    (128, 46, 70, 150, 176, UP),
    (188, 70, 88, 132, 160, UP),
)
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def draw():  # -> PIL.Image.Image
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=44, fill=BACKGROUND)
    for x, wick_top, body_top, body_bottom, wick_bottom, colour in CANDLES:
        pen.rectangle((x - 5, wick_top, x + 5, wick_bottom), fill=colour)
        pen.rectangle((x - 22, body_top, x + 22, body_bottom), fill=colour)
    return image


def main() -> None:
    target = Path(__file__).resolve().parent / "icon.ico"
    draw().save(target, sizes=SIZES)
    print(target)


if __name__ == "__main__":
    main()
