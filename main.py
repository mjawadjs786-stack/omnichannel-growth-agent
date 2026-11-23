import os
import json
import base64
import imaplib
import smtplib
import email
import textwrap
import urllib.parse
from email.message import EmailMessage
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai

GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PIN_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
PIN_ENV = os.environ.get("PINTEREST_ENV", "production").lower().strip()

STATE_FILE = "active_product.json"
PENDING_FILE = "pending_pin.json"

BANNED = [
    "gambling", "casino", "betting", "riba", "interest loan", "usury",
    "alcohol", "wine", "beer", "adult", "nsfw", "nude", "bikini",
    "pirated", "crack", "hack", "scam", "crypto pump", "forex signals"
]

def ask_gemini(prompt: str) -> str:
    client = genai.Client(api_key=GEMINI_KEY)
    candidates = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    try:
        available = [m.name.replace("models/", "") for m in client.models.list() if "flash" in m.name.lower()]
        for m in available:
            if m not in candidates:
                candidates.insert(0, m)
    except Exception:
        pass
    last_err = None
    for model_name in candidates:
        try:
            res = client.models.generate_content(model=model_name, contents=prompt)
            return res.text.strip()
        except Exception as e:
            last_err = e
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

def is_halal_safe(text: str) -> bool:
    low = text.lower()
    if any(w in low for w in BANNED):
        return False
    verdict = ask_gemini(
        f"Is this 100% Halal, legal, ethical, and safe (no gambling, riba, alcohol, adult/immodest content, or scams)? Reply ONLY SAFE or BLOCKED.\n\n{text}"
    )
    return verdict.upper().startswith("SAFE")
def send_email(subject: str, body: str, attachments: list = None):
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments or []:
        if os.path.exists(path):
            with open(path, "rb") as f:
                msg.add_attachment(f.read(), maintype="image", subtype="png", filename=os.path.basename(path))
    with smtplib.SMTP_SSL("smtp" + ".gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(msg)
def check_latest_command(subject_filter: str):
    mail = imaplib.IMAP4_SSL("imap" + ".gmail.com")
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select('"[Gmail]/All Mail"')
    _, data = mail.search(None, f'(SUBJECT "{subject_filter}")')
    raw_ids = data.pop(0) if data else b""
    ids = raw_ids.split()
    if not ids:
        mail.logout()
        return None
    _, msg_data = mail.fetch(ids.pop(), "(RFC822)")
    first_part = msg_data.pop(0)
    raw = email.message_from_bytes(first_part[-1])
    body = ""
    if raw.is_multipart():
        for part in raw.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        body = raw.get_payload(decode=True).decode(errors="ignore")
    mail.logout()
    return body.strip()

def get_product():
    override = check_latest_command("PIN-NEW-PRODUCT")
    if override and is_halal_safe(override):
        prod = {"name": "Custom User Product", "details": override, "approved": True}
        with open(STATE_FILE, "w") as f:
            json.dump(prod, f)
        return prod

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            prod = json.load(f)
        if prod.get("approved"):
            return prod
        reply = check_latest_command("PIN-PRODUCT-PROPOSAL")
        if reply and "START PRODUCT" in reply.upper():
            prod["approved"] = True
            with open(STATE_FILE, "w") as f:
                json.dump(prod, f)
            return prod
        return None

    raw = ask_gemini(
        'Suggest 1 trending, high-demand, 100% Halal digital product (Notion template, AI prompt pack, study planner, or checklist) for Pinterest. Return JSON ONLY: {"name":"...","audience":"...","why":"...","link":"https://payhip.com"}'
    )
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    prop = json.loads(raw)
    prop["approved"] = False
    if not is_halal_safe(json.dumps(prop)):
        return None
    with open(STATE_FILE, "w") as f:
        json.dump(prop, f)
    send_email(
        "PIN-PRODUCT-PROPOSAL: Permission to Promote New Digital Product",
        f"Product: {prop.get('name')}\nAudience: {prop.get('audience')}\nWhy: {prop.get('why')}\n\nReply 'START PRODUCT' to approve, OR send a new email with subject 'PIN-NEW-PRODUCT' containing your own link & instructions."
    )
    return None

def make_pins(headline: str, subtext: str) -> list:
    from io import BytesIO
    client = genai.Client(api_key=GEMINI_KEY)
    styles = [
        "Luxury warm beige and gold aesthetic desk flatlay with iPad showing clean Notion habit tracker dashboard, soft sunlight shadows, editorial Pinterest photography, no text",
        "Sleek dark emerald and cream minimalist workspace with laptop displaying modern digital planner layout, warm ambient lamp light, high-end product mockup, no text",
        "Soft sage green and ivory aesthetic study table with tablet, open journal, and coffee cup, bright airy natural lighting, viral Pinterest aesthetic, no text"
    ]
    palettes = [
        {"card": (20, 18, 16, 225), "title": (255, 222, 115), "sub": (245, 240, 230), "btn": (218, 165, 32), "btn_txt": (15, 15, 15)},
        {"card": (12, 28, 24, 230), "title": (255, 255, 255), "sub": (200, 235, 220), "btn": (46, 204, 113), "btn_txt": (10, 20, 15)},
        {"card": (252, 249, 242, 238), "title": (28, 38, 32), "sub": (75, 85, 80), "btn": (34, 95, 68), "btn_txt": (255, 255, 255)}
    ]
    paths = []
    for i, st in enumerate(styles, start=1):
        out = f"pin_option_{i}.png"
        img = None
        try:
            res = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=f"Vertical 2:3 Pinterest aesthetic background photo: {headline}. {st}"
            )
            for part in res.candidates.pop(0).content.parts:
                if getattr(part, "inline_data", None):
                    img = Image.open(BytesIO(part.inline_data.data)).convert("RGB").resize((1000, 1500))
                    break
        except Exception:
            img = None

        if img is None:
            try:
                p = urllib.parse.quote(f"{headline}, {st}")
                base_img_url = "https://image" + ".pollinations.ai/prompt/"
                url = f"{base_img_url}{p}?width=1000&height=1500&model=flux&nologo=true&seed={i*77}"
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=45)
                if r.status_code == 200 and len(r.content) > 10000:
                    img = Image.open(BytesIO(r.content)).convert("RGB").resize((1000, 1500))
            except Exception:
                img = None

        if img is None:
            img = Image.new("RGB", (1000, 1500), color=(32, 42, 38))
            grad = ImageDraw.Draw(img)
            for y in range(1500):
                c = int(28 + (y / 1500) * 35)
                grad.line([(0, y), (1000, y)], fill=(c, c + 12, c + 8))

        pal = palettes.pop(0)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rounded_rectangle([(65, 760), (935, 1410)], radius=36, fill=pal["card"])

        try:
            f_tag = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
            f_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 58)
            f_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
            f_btn = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except Exception:
            f_tag = f_big = f_sub = f_btn = ImageFont.load_default(size=42)

        draw.text((115, 805), "DIGITAL TEMPLATE  •  INSTANT DOWNLOAD", fill=pal["btn"], font=f_tag)
        wrapped_title = "\n".join(textwrap.wrap(headline.upper(), width=21)[:3])
        draw.multiline_text((115, 860), wrapped_title, fill=pal["title"], font=f_big, spacing=14)
        wrapped_sub = "\n".join(textwrap.wrap(subtext, width=38)[:3])
        draw.multiline_text((115, 1115), wrapped_sub, fill=pal["sub"], font=f_sub, spacing=10)
        draw.rounded_rectangle([(115, 1280), (620, 1365)], radius=42, fill=pal["btn"])
        draw.text((160, 1303), "GET INSTANT ACCESS  →", fill=pal["btn_txt"], font=f_btn)

        img.save(out)
        paths.append(out)
    return paths
def publish_pin(image_path: str, title: str, desc: str, link: str, board_name: str):
    base = "https://pinterest.com" if PIN_ENV == "sandbox" else "https://pinterest.com"
    headers = {"Authorization": f"Bearer {PIN_TOKEN}", "Content-Type": "application/json"}
    r = requests.get(f"{base}/boards", headers=headers, timeout=20)
    board_id = None
    if r.status_code == 200:
        for b in r.json().get("items", []):
            if b.get("name", "").lower() == board_name.lower():
                board_id = b.get("id")
                break
    if not board_id:
        cr = requests.post(f"{base}/boards", headers=headers, json={"name": board_name, "privacy": "PUBLIC"}, timeout=20)
        board_id = cr.json().get("id")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": desc[:500],
        "link": link,
        "media_source": {"source_type": "image_base64", "content_type": "image/png", "data": b64}
    }
    return requests.post(f"{base}/pins", headers=headers, json=payload, timeout=30).json()
def publish_pin(image_path: str, title: str, desc: str, link: str, board_name: str):
    base = "https://api-sandbox" + "://" if PIN_ENV == "sandbox" else "https://api" + "://"
    headers = {"Authorization": f"Bearer {PIN_TOKEN}", "Content-Type": "application/json"}
    r = requests.get(f"{base}/boards", headers=headers, timeout=20)
    board_id = None
    if r.status_code == 200:
        for b in r.json().get("items", []):
            if b.get("name", "").lower() == board_name.lower():
                board_id = b.get("id")
                break
    if not board_id:
        cr = requests.post(f"{base}/boards", headers=headers, json={"name": board_name, "privacy": "PUBLIC"}, timeout=20)
        cr_json = cr.json()
        print("Board creation response:", cr_json)
        board_id = cr_json.get("id")
    if not board_id:
        raise RuntimeError(f"Could not get/create Pinterest board. API response: {r.text}")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": desc[:500],
        "link": link,
        "media_source": {"source_type": "image_base64", "content_type": "image/png", "data": b64}
    }
    res = requests.post(f"{base}/pins", headers=headers, json=payload, timeout=30)
    res_json = res.json()
    print("Pinterest API status:", res.status_code, res_json)
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Pinterest publish failed ({res.status_code}): {res_json}")
    return res_json

def main():
    print("Starting Autonomous Pinterest Growth & Sales Agent...")
    if not GEMINI_KEY or not GMAIL_USER or not GMAIL_PASS or not PIN_TOKEN:
        raise RuntimeError(f"Missing secret! GEMINI_KEY={bool(GEMINI_KEY)}, GMAIL_USER={bool(GMAIL_USER)}, GMAIL_PASS={bool(GMAIL_PASS)}, PIN_TOKEN={bool(PIN_TOKEN)}")
    product = get_product()
    if not product:
        print("Waiting for product approval via Gmail.")
        return

    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE) as f:
            draft = json.load(f)
        reply = check_latest_command("PIN-APPROVAL")
        if not reply:
            print("Waiting for APPROVE 1/2/3 reply in Gmail.")
            return
        clean_lines = []
        for line in reply.splitlines():
            if line.strip().startswith(">") or (line.strip().startswith("On ") and "wrote:" in line):
                break
            if line.strip():
                clean_lines.append(line.strip())
        up = " ".join(clean_lines).upper()
        print("Detected Gmail reply:", up)

        if "SKIP" in up or "CANCEL" in up:
            os.remove(PENDING_FILE)
            print("Draft skipped.")
            return
        if "REGENERATE" in up:
            os.remove(PENDING_FILE)
            print("Regenerating fresh Pin draft...")
        else:
            choice = 1
            for n in (1, 2, 3):
                if f"APPROVE {n}" in up:
                    choice = n
                    break
            if "APPROVE" in up:
                img = f"pin_option_{choice}.png"
                if not os.path.exists(img):
                    make_pins(draft["headline"], draft["subtext"])
                res = publish_pin(img, draft["title"], draft["description"], draft["link"], draft["board"])
                print("SUCCESS! Published Pin to Pinterest:", res)
                os.remove(PENDING_FILE)
                return

    raw = ask_gemini(
        f'Create a viral Pinterest Pin for this Halal digital product: {json.dumps(product)}. Return JSON ONLY: {{"board":"2-4 word board","headline":"4-6 word image headline","subtext":"5-7 word callout","title":"SEO title under 90 chars","description":"SEO description + hashtags under 450 chars","link":"{product.get("link", "https://payhip.com")}"}}'
    )
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    draft = json.loads(raw)
    if not is_halal_safe(json.dumps(draft)):
        print("Blocked by ethics check.")
        return
    imgs = make_pins(draft["headline"], draft["subtext"])
    with open(PENDING_FILE, "w") as f:
        json.dump(draft, f)
    send_email(
        "PIN-APPROVAL: Review Your 3 New Pinterest Pin Designs",
        f"Board: {draft['board']}\nTitle: {draft['title']}\nDescription: {draft['description']}\nLink: {draft['link']}\n\nReply 'APPROVE 1', 'APPROVE 2', or 'APPROVE 3' to publish, 'REGENERATE' for new designs, or 'SKIP' to discard.",
        imgs
    )
    print("Sent 3 Pin designs to Gmail for approval!")

if __name__ == "__main__": main()
