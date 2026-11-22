import os
import base64
import requests

def get_base_url() -> str:
    env = os.environ.get("PINTEREST_ENV", "production").lower()
    return "https://pinterest.com" if env == "sandbox" else "https://pinterest.com"

def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['PINTEREST_ACCESS_TOKEN']}",
        "Content-Type": "application/json"
    }

def get_or_create_board(board_name: str) -> str:
    base = get_base_url()
    r = requests.get(f"{base}/boards", headers=get_headers(), timeout=20)
    if r.status_code == 200:
        for b in r.json().get("items", []):
            if b.get("name", "").lower() == board_name.lower():
                return b["id"]
    create_r = requests.post(
        f"{base}/boards",
        headers=get_headers(),
        json={"name": board_name, "description": f"Curated tips & tools for {board_name}", "privacy": "PUBLIC"},
        timeout=20
    )
    return create_r.json()["id"]

def publish_pin(image_path: str, title: str, description: str, link: str, board_name: str) -> dict:
    board_id = get_or_create_board(board_name)
    with open(image_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "link": link,
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/png",
            "data": b64_img
        }
    }
    res = requests.post(f"{get_base_url()}/pins", headers=get_headers(), json=payload, timeout=30)
    return res.json()
