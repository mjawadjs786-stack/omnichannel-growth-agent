import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont
import textwrap

STYLES = [
    "minimalist aesthetic flatlay desk workspace, warm lighting, clean composition, no text",
    "modern sleek dark-mode productivity dashboard mockup, high contrast, clean design, no text",
    "bright pastel aesthetic digital planner mockup on tablet, clean studio photo, no text"
]

def create_three_pin_options(headline: str, subtext: str) -> list[str]:
    paths = []
    for idx, style in enumerate(STYLES, start=1):
        prompt = urllib.parse.quote(f"{headline}, {style}")
        url = f"https://pollinations.ai{prompt}?width=1000&height=1500&nologo=true&seed={idx*42}"
        img_path = f"pin_option_{idx}.png"
        try:
            r = requests.get(url, timeout=30)
            with open(img_path, "wb") as f:
                f.write(r.content)
            img = Image.open(img_path).convert("RGB").resize((1000, 1500))
        except Exception:
            img = Image.new("RGB", (1000, 1500), color=(25, 30, 45))

        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle([(60, 120), (940, 560)], fill=(15, 15, 20, 210))
        font_big = ImageFont.load_default(size=58)
        font_sub = ImageFont.load_default(size=34)

        wrapped_title = "\n".join(textwrap.wrap(headline.upper(), width=22))
        draw.multiline_text((100, 155), wrapped_title, fill=(255, 230, 80), font=font_big, spacing=12)
        draw.text((100, 470), subtext[:42], fill=(255, 255, 255), font=font_sub)

        img.save(img_path)
        paths.append(img_path)
    return paths
