import os
import json
from google import genai
from skills.ethics_guard import is_halal_and_safe
from skills.gmail_controller import send_email, check_latest_command

STATE_FILE = "active_product.json"

def get_or_research_product() -> dict | None:
    # 1. Check if user sent a custom product link/instruction via Gmail
    user_override = check_latest_command("PIN-NEW-PRODUCT")
    if user_override:
        safe, reason = is_halal_and_safe(user_override)
        if safe:
            product = {"name": "Custom User Offer", "details": user_override, "approved": True}
            with open(STATE_FILE, "w") as f:
                json.dump(product, f)
            return product

    # 2. Check existing product state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            product = json.load(f)
        if product.get("approved"):
            return product
        # Check if user replied START PRODUCT to approve proposal
        reply = check_latest_command("PIN-PRODUCT-PROPOSAL")
        if reply and "START PRODUCT" in reply.upper():
            product["approved"] = True
            with open(STATE_FILE, "w") as f:
                json.dump(product, f)
            return product
        return None  # Still waiting for user permission

    # 3. Research a new high-demand Halal digital product via Gemini
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = """Identify 1 trending, high-demand, 100% Halal digital product idea (such as a Notion productivity template, AI study prompt pack, Islamic daily habit planner, or freelancer checklist) that sells well on Pinterest.
Return JSON ONLY: {"name": "...", "target_audience": "...", "why_in_demand": "...", "suggested_link": "https://payhip.com"}"""
    res = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
    raw = res.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    proposal = json.loads(raw)
    proposal["approved"] = False

    safe, reason = is_halal_and_safe(json.dumps(proposal))
    if not safe:
        return None

    with open(STATE_FILE, "w") as f:
        json.dump(proposal, f)

    send_email(
        subject="PIN-PRODUCT-PROPOSAL: Permission to Promote New Digital Product",
        body=f"""Assalamu Alaikum! Your agent discovered a high-demand digital product:

Product: {proposal['name']}
Audience: {proposal['target_audience']}
Demand Proof: {proposal['why_in_demand']}
Default Link: {proposal['suggested_link']}

Reply 'START PRODUCT' to approve, OR send a new email with subject 'PIN-NEW-PRODUCT' containing your own product link & instructions."""
    )
    return None
  
