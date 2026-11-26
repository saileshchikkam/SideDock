"""Generate a deterministic high-contrast OCR fixture for Windows CI only."""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "build" / "ocr-smoke-fixture.png"


def main():
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    bold = fonts / "arialbd.ttf"
    if not bold.is_file():
        raise FileNotFoundError(f"Windows Arial bold font not available: {bold}")
    image = Image.new("RGB", (1200, 300), color="white")
    painter = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(bold), 100)
    painter.text((120, 74), "SIDE DOCK", font=font, fill="black")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    image.save(DESTINATION, format="PNG")
    print("Generated OCR fixture:", DESTINATION, "bytes:", DESTINATION.stat().st_size)
    return DESTINATION


if __name__ == "__main__":
    main()
