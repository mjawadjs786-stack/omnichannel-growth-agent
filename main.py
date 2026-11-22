import os
import json
from google import genai
from skills.ethics_guard import is_halal_and_safe
from skills.product_hunter import get_or_research_product
from skills.gmail_controller import send_email, check_latest_command
from skills.infographic_designer import create_three_pin_options
from skills.pinterest_publisher import publish_pin

PENDING_FILE = "pending_pin.json"

def run_agent():
    product = get_or_research_product()
    if not product:
        print("Waiting for user approval on product proposal email (PIN-PRODUCT-PROPOSAL).")
        return

    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE) as f:
            draft = json.load(f)
        reply = check_latest_command("PIN-APPROVAL")
        if not reply:
            print("Still waiting for APPROVE 1/2/3 reply in Gmail.")
            return
        upper = reply.upper()
        if "REJECT" in upper:
            os.remove(PENDING_FILE)
            print("Draft rejected and cleared.")
            return
        if "REGENERATE" in upper:
            os.remove(PENDING_FILE)
            print("Regenerating fresh Pin draft...")
        else:
            choice = 1
            for n in (1, 2, 3):
                if f"APPROVE {n}" in upper:
                    choice = n
                    break
            if "APPROVE" in upper:
                img_path = f"pin_option_{choice}.png"
                if not os.path.exists(img_path):
                    create_three_pin_options(draft["headline"], draft["subtext"])
                res = publish_pin(
                    image_path=img_path,
                    title=draft["title"],
                    description=draft["description"],
                    link=draft["link"],
                    board_name=draft["board"]
                )
                print("Published to Pinterest:", res)
                os.remove(PENDING_FILE)
                return

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = f"""Create a viral, SEO-optimized Pinterest Pin concept promoting this Halal digital product:
{json.dumps(product)}

Return JSON ONLY:
{{
  "board": "2-4 word SEO Pinterest Board Name",
  "headline": "Short 4-6 word bold image headline",
  "subtext": "Short 5-7 word callout",
  "title": "Click-worthy Pinterest Pin title under 90 chars",
  "description": "Keyword-rich Pinterest SEO description with call to action and hashtags under 450 chars",
  "link": "Destination URL from product details or https://payhip.com"
}}"""
    res = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
    raw = res.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    draft = json.loads(raw)

    safe, reason = is_halal_and_safe(json.dumps(draft))
    if not safe:
        print("Draft blocked by ethics_guard:", reason)
        return

    images = create_three_pin_options(draft["headline"], draft["subtext"])
    with open(PENDING_FILE, "w") as f:
        json.dump(draft, f)

    send_email(
        subject="PIN-APPROVAL: Review Your 3 New Pinterest Pin Designs",
        body=f"""Your agent generated a new Pinterest Pin ready for approval:

Board: {draft['board']}
Title: {draft['title']}
Description: {draft['description']}
Sales Link: {draft['link']}

Reply to this email with:
- 'APPROVE 1', 'APPROVE 2', or 'APPROVE 3' to publish immediately
- 'REGENERATE' for a new design
- 'REJECT' to skip""",
        attachments=images
    )
    print("Sent PIN-APPROVAL email with 3 Pin options!")

if __name__ == "__main__":
    run_agent()
    
