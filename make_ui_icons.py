from pathlib import Path

from PIL import Image, ImageDraw


OUTPUT_DIR = Path(__file__).resolve().parent / "ui_icons"
SIZE = 80
OUTPUT_SIZE = 20


def render(name: str, draw_icon, color: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw_icon(ImageDraw.Draw(image), color)
    image.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS).save(
        OUTPUT_DIR / f"{name}.png"
    )


def target(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.ellipse((12, 12, 68, 68), outline=color, width=7)
    draw.line((40, 4, 40, 76), fill=color, width=7)
    draw.line((4, 40, 76, 40), fill=color, width=7)
    draw.ellipse((32, 32, 48, 48), fill=color)


def sliders(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.line((9, 18, 71, 18), fill=color, width=7)
    draw.line((9, 40, 71, 40), fill=color, width=7)
    draw.line((9, 62, 71, 62), fill=color, width=7)
    draw.ellipse((24, 8, 40, 28), fill=color)
    draw.ellipse((49, 30, 65, 50), fill=color)
    draw.ellipse((17, 52, 33, 72), fill=color)


def refresh(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.arc((10, 10, 70, 70), start=35, end=325, fill=color, width=8)
    draw.polygon(((61, 9), (74, 12), (68, 25)), fill=color)


def search(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.ellipse((10, 10, 52, 52), outline=color, width=8)
    draw.line((45, 45, 70, 70), fill=color, width=9)


def check(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.line((10, 42, 30, 62), fill=color, width=9, joint="curve")
    draw.line((30, 62, 70, 18), fill=color, width=9, joint="curve")


def play(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.polygon(((26, 12), (68, 40), (26, 68)), fill=color)


def stop(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle((14, 14, 66, 66), radius=9, fill=color)


def gift(draw: ImageDraw.ImageDraw, color: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle((10, 30, 70, 70), radius=5, outline=color, width=6)
    draw.line((10, 43, 70, 43), fill=color, width=6)
    draw.line((40, 30, 40, 70), fill=color, width=6)
    draw.arc((22, 8, 42, 34), start=180, end=355, fill=color, width=6)
    draw.arc((38, 8, 58, 34), start=185, end=360, fill=color, width=6)


OUTPUT_DIR.mkdir(exist_ok=True)
for icon_name, icon_drawer in (
    ("target", target),
    ("sliders", sliders),
    ("refresh", refresh),
    ("search", search),
    ("check", check),
    ("play", play),
    ("stop", stop),
    ("gift", gift),
):
    render(icon_name, icon_drawer, (15, 118, 110, 255))

for icon_name, icon_drawer in (("play_white", play), ("stop_white", stop)):
    render(icon_name, icon_drawer, (255, 255, 255, 255))
