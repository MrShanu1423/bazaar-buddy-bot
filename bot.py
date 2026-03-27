import requests
from bs4 import BeautifulSoup
import time
import random

BOT_TOKEN = "8608712234:AAEQIOKSBzTeDnIZeuVUg-3mobgbBIT_KVU"
CHAT_ID = "-1003706154836"
AFFILIATE_ID = "dattatrey07-21"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

URL = "https://www.amazon.in/gp/bestsellers/apparel/"

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    requests.post(url, data=data)

def scrape_products():
    page = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(page.text, "html.parser")

    items = soup.select(".zg-grid-general-faceout")
    products = []

    for item in items[:15]:
        try:
            title = item.select_one("img")["alt"]
            link = "https://amazon.in" + item.select_one("a")["href"]
            price_tag = item.select_one(".p13n-sc-price")
            price = price_tag.get_text(strip=True) if price_tag else "Check price"

            affiliate_link = link + f"?tag={AFFILIATE_ID}"

            products.append((title, price, affiliate_link))
        except:
            continue

    return products

def run_bot():
    print("🚀 PRO BOT STARTED")

    while True:
        products = scrape_products()

        if len(products) >= 3:
            selected = random.sample(products, 3)

            message = "🔥 <b>TOP 3 HOT DEALS</b>\n\n"

            for i, (title, price, link) in enumerate(selected, start=1):
                message += f"""
{i}️⃣ <b>{title}</b>
💰 {price}
👉 <a href="{link}">Buy Now</a>

"""

            message += "⚡ Hurry! Deals may expire anytime!"

            send_message(message)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Posted 3 products")

        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Not enough products scraped")

        time.sleep(1200)  # 20 minutes

run_bot()
