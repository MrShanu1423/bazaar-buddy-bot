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

CATEGORIES = [
    "https://www.amazon.in/gp/bestsellers/electronics/",
    "https://www.amazon.in/gp/bestsellers/computers/",
    "https://www.amazon.in/gp/bestsellers/hpc/",
]

def get_product_details(product_url):
    try:
        resp = requests.get(product_url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Rating
        rating = ""
        rating_tag = soup.select_one("span.a-icon-alt")
        if rating_tag:
            rating = rating_tag.get_text(strip=True).split(" ")[0]

        # Review count
        reviews = ""
        reviews_tag = soup.select_one("#acrCustomerReviewText")
        if reviews_tag:
            reviews = reviews_tag.get_text(strip=True).replace(" ratings", "").replace(" rating", "")

        # Seller
        seller = ""
        seller_tag = soup.select_one("#sellerProfileTriggerId") or soup.select_one("#merchant-info a")
        if seller_tag:
            seller = seller_tag.get_text(strip=True)

        # Original MRP
        original_price = ""
        mrp_tag = soup.select_one("span.a-price.a-text-price span.a-offscreen")
        if mrp_tag:
            original_price = mrp_tag.get_text(strip=True)

        # Discount %
        discount = ""
        discount_tag = soup.select_one("span.savingsPercentage")
        if discount_tag:
            discount = discount_tag.get_text(strip=True)

        return rating, reviews, seller, original_price, discount
    except:
        return "", "", "", "", ""


def send_product_post(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller):
    lines = []

    lines.append(f"🎧 <b>{title}</b>")
    lines.append("")

    if original_price and discount:
        lines.append(f"💰 <b>At only {price} instead of {original_price} <i>({discount})</i></b>")
    else:
        lines.append(f"💰 <b>At only {price}</b>")

    lines.append("")
    lines.append(f"🔗 <a href=\"{affiliate_link}\">Buy Now</a>")

    if rating or reviews:
        lines.append("")
        review_line = ""
        if reviews:
            review_line += f"⭐ {reviews} Reviews"
        if rating:
            review_line += f": {rating} / 5.0"
        lines.append(review_line)

    if seller:
        lines.append(f"🚚 Sold by <i>{seller}</i> and shipped by Amazon")

    caption = "\n".join(lines)

    # Telegram caption max 1024 chars
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    return requests.post(url, data=data)


def scrape_products():
    url = random.choice(CATEGORIES)
    page = requests.get(url, headers=HEADERS, timeout=15)
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

            # Clean affiliate link
            base_link = link.split("?")[0]
            affiliate_link = base_link + f"?tag={AFFILIATE_ID}"

            if image_url and title:
                products.append((title, price, affiliate_link, image_url, base_link))
        except:
            continue

    return products


def send_header():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": "🔥 <b>TOP DEALS OF THE DAY</b>\n⚡ Hurry! Limited time offers!",
        "parse_mode": "HTML"
    })


def run_bot():
    print("🚀 PRO BOT STARTED — image + description mode")

    while True:
        try:
            products = scrape_products()

            if len(products) >= 3:
                selected = random.sample(products, 3)

                send_header()
                time.sleep(1)

                for title, price, affiliate_link, image_url, base_link in selected:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fetching details: {title[:50]}")
                    rating, reviews, seller, original_price, discount = get_product_details(base_link)

                    resp = send_product_post(
                        title, price, original_price, discount,
                        image_url, affiliate_link,
                        rating, reviews, seller
                    )

                    if resp.status_code == 200:
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Posted: {title[:50]}")
                    else:
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Error {resp.status_code}: {resp.text[:120]}")

                    time.sleep(2)

            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Not enough products scraped ({len(products)} found)")

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Error: {e}")

        time.sleep(1200)  # post every 20 minutes

run_bot()
