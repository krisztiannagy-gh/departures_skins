"""Turn any picture (PNG, JPG, SVG exported as PNG...) into bkk_picture.txt for
the BKK skin's static "Picture" mode.

Usage (on the Mac, from the departures_skins folder):
    uv run --with pillow python3 bkk/tools/picture_to_matrix.py my_picture.png
    uv run --with pillow python3 bkk/tools/picture_to_matrix.py my_picture.png --height 24 --invert

It writes bkk_picture.txt next to the input and prints a preview. Copy that
file to the root of the box's drive (hold the button while plugging it in).
Lit LEDs are drawn as '#', dark ones as '.'; you can also edit the file by hand.
"""
import argparse, os
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("--height", type=int, default=28, help="max height in LEDs (panel is 32 on X, 64 on 2X)")
ap.add_argument("--width", type=int, default=128, help="max width in LEDs")
ap.add_argument("--threshold", type=int, default=128, help="0-255: how dark a pixel must be to light an LED")
ap.add_argument("--invert", action="store_true", help="light the light parts instead of the dark parts")
a = ap.parse_args()

im = Image.open(a.image).convert("RGBA")
bg = Image.new("RGBA", im.size, (255, 255, 255, 255))      # transparent -> white (off)
im = Image.alpha_composite(bg, im).convert("L")
scale = min(a.height / im.height, a.width / im.width)
im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)

rows = []
for y in range(im.height):
    row = ""
    for x in range(im.width):
        v = im.getpixel((x, y))
        on = v > a.threshold if a.invert else v < a.threshold
        row += "#" if on else "."
    rows.append(row)
# drop empty margins
while rows and "#" not in rows[0]: rows.pop(0)
while rows and "#" not in rows[-1]: rows.pop()
if rows:
    left = min(r.index("#") for r in rows if "#" in r)
    right = max(len(r) - r[::-1].index("#") for r in rows if "#" in r)
    rows = [r[left:right] for r in rows]

out = os.path.join(os.path.dirname(os.path.abspath(a.image)), "bkk_picture.txt")
with open(out, "w") as f:
    f.write("\n".join(rows) + "\n")
print("\n".join(r.replace(".", " ") for r in rows))
print(f"\n{len(rows[0]) if rows else 0} x {len(rows)} LEDs -> {out}")
