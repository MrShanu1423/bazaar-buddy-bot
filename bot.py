import requests
from bs4 import BeautifulSoup
import time
import random
import json

BOT_TOKEN = "8608712234:AAEQIOKSBzTeDnIZeuVUg-3mobgbBIT_KVU"
CHAT_ID = "-1003706154836"
AFFILIATE_ID = "dattatrey07-21"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

URL = "https://www.amazon.in/gp/bestsellers/apparel/"

def send_media_group(products):
    media = []
    for i, (title, price, link, image_url) in enumerate(products, start=1):
        caption = (
            f"{'🥇' if i==1 else '🥈' if i==2 else '🥉'} <b>{title}</b>\n"
            f"💰 {price}\n"
            f"👉 <a href=\"{link}\">Buy Now</a>"
        )
        media.append({
            "type": "photo",
            "media": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        })

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
    data = {
        "chat_id": CHAT_ID,
        "media": json.dumps(media)
    }
    response = requests.post(url, data=data)
    return response

def send_header():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": "🔥 <b>TOP 3 HOT DEALS TODAY</b>\n⚡ Hurry! Deals may expire anytime!",
        "parse_mode": "HTML"
    }
    requests.post(url, data=data)

def scrape_products():
    page = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(page.text, "html.parser")

    items = soup.select(".zg-grid-general-faceout")
    products = []

    for item in items[:20]:
        try:
            img_tag = item.select_one("img")
            title = img_tag["alt"]
            image_url = img_tag.get("src") or img_tag.get("data-src", "")

            link = "https://www.amazon.in" + item.select_one("a")["href"]
            price_tag = item.select_one(".p13n-sc-price")
            price = price_tag.get_text(strip=True) if price_tag else "Check price"

            affiliate_link = link.split("?")[0] + f"?tag={AFFILIATE_ID}"

            if image_url and title:
                products.append((title, price, affiliate_link, image_url))
        except:
            continue

    return products

def run_bot():
    print("🚀 PRO BOT STARTED (with images)")

    while True:
        try:
            products = scrape_products()

            if len(products) >= 3:
                selected = random.sample(products, 3)
                send_header()
                time.sleep(1)
                response = send_media_group(selected)

                if response.status_code == 200:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Posted 3 products with images")
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Media group failed ({response.status_code}), trying text post")
                    # Fallback to text-only if images fail
                    message = "🔥 <b>TOP 3 HOT DEALS</b>\n\n"
                    for i, (title, price, link, _) in enumerate(selected, start=1):
                        message += f"{i}️⃣ <b>{title}</b>\n💰 {price}\n👉 <a href=\"{link}\">Buy Now</a>\n\n"
                    message += "⚡ Hurry! Deals may expire anytime!"
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Not enough products scraped ({len(products)} found)")

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Error: {e}")

        time.sleep(1200)  # 20 minutes

run_bot()
