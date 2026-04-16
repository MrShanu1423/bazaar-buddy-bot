import requests
from bs4 import BeautifulSoup
import time
import random
import json

BOT_TOKEN = "8608712234:AAEQIOKSBzTeDnIZeuVUg-3mobgbBIT_KVU"
CHAT_ID = "-1003706154836"
AFFILIATE_ID = "dattatrey07-21"

FB_PAGE_ID = "1060781310451431"
FB_USER_TOKEN = "EAANdFOZCViOQBRM1vtPoPvsRq77y9TG98yiGLpPxuedyhgbJm0W1M17lTvkRta6bLGRmc9SmVk0ebpLZB9FOiQLXLBlC3ZAcWCEAfIRWruUxmzPRXJwvJKoZADMz5QBa10oLE62QldLgnpgy4OzeNeb9qg4zHCfJk2rZCoYe9EPHxbbOiEpqK7nOiY2s7mds8hsNy8JBWMuqSsiiZCSH63k41exOUTUBjGLbeAvq2CwpF84syuatdpmgFkcyH966kQXbYDJ6QDuJZBOtUzUuDaO"

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

        rating = ""
        rating_tag = soup.select_one("span.a-icon-alt")
        if rating_tag:
            rating = rating_tag.get_text(strip=True).split(" ")[0]

        reviews = ""
        reviews_tag = soup.select_one("#acrCustomerReviewText")
        if reviews_tag:
            reviews = reviews_tag.get_text(strip=True).replace(" ratings", "").replace(" rating", "")

        seller = ""
        seller_tag = soup.select_one("#sellerProfileTriggerId") or soup.select_one("#merchant-info a")
        if seller_tag:
            seller = seller_tag.get_text(strip=True)

        original_price = ""
        mrp_tag = soup.select_one("span.a-price.a-text-price span.a-offscreen")
        if mrp_tag:
            original_price = mrp_tag.get_text(strip=True)

        discount = ""
        discount_tag = soup.select_one("span.savingsPercentage")
        if discount_tag:
            discount = discount_tag.get_text(strip=True)

        return rating, reviews, seller, original_price, discount
    except:
        return "", "", "", "", ""


def build_caption_plain(title, price, original_price, discount, affiliate_link, rating, reviews, seller):
    lines = []
    lines.append(f"🎧 {title}")
    lines.append("")
    if original_price and discount:
        lines.append(f"💰 At only {price} instead of {original_price} ({discount})")
    else:
        lines.append(f"💰 At only {price}")
    lines.append("")
    lines.append(f"🔗 Buy Now: {affiliate_link}")
    if rating or reviews:
        lines.append("")
        review_line = ""
        if reviews:
            review_line += f"⭐ {reviews} Reviews"
        if rating:
            review_line += f": {rating} / 5.0"
        lines.append(review_line)
    if seller:
        lines.append(f"🚚 Sold by {seller} and shipped by Amazon")
    return "\n".join(lines)


def send_to_telegram(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller):
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
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    resp = requests.post(url, data={
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    })
    return resp.status_code == 200


def get_fb_page_token():
    try:
        r = requests.get(f"https://graph.facebook.com/me/accounts?access_token={FB_USER_TOKEN}", timeout=10)
        pages = r.json().get("data", [])
        for page in pages:
            if page.get("id") == FB_PAGE_ID:
                return page.get("access_token", "")
        if pages:
            return pages[0].get("access_token", "")
    except:
        pass
    return ""


def post_to_facebook(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller):
    message = build_caption_plain(title, price, original_price, discount, affiliate_link, rating, reviews, seller)
    page_token = get_fb_page_token()
    if not page_token:
        return False, "Could not get page token"

    try:
        # Download image from Amazon
        img_resp = requests.get(image_url, headers=HEADERS, timeout=10)
        if img_resp.status_code != 200:
            return False, f"Image download failed: {img_resp.status_code}"

        # Step 1: Upload photo as unpublished to get photo ID
        photo_resp = requests.post(
            f"https://graph.facebook.com/{FB_PAGE_ID}/photos",
            data={"published": "false", "access_token": page_token},
            files={"source": ("product.jpg", img_resp.content, "image/jpeg")}
        )
        photo_data = photo_resp.json()
        photo_id = photo_data.get("id")

        if not photo_id:
            return False, f"Photo upload failed: {photo_resp.text[:150]}"

        # Step 2: Post to page feed with attached photo (shows in main timeline)
        feed_resp = requests.post(
            f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
            data={
                "message": message,
                "attached_media": json.dumps([{"media_fbid": photo_id}]),
                "access_token": page_token
            }
        )
        return feed_resp.status_code == 200, feed_resp.text
    except Exception as e:
        return False, str(e)


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

            base_link = link.split("?")[0]
            affiliate_link = base_link + f"?tag={AFFILIATE_ID}"

            if image_url and title:
                products.append((title, price, affiliate_link, image_url, base_link))
        except:
            continue

    return products


def run_bot():
    print("🚀 BOT STARTED — Telegram + Facebook | 1 post every 20 minutes")

    while True:
        try:
            products = scrape_products()

            if products:
                title, price, affiliate_link, image_url, base_link = random.choice(products)

                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fetching details: {title[:50]}")
                rating, reviews, seller, original_price, discount = get_product_details(base_link)

                # Post to Telegram
                tg_ok = send_to_telegram(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller)
                if tg_ok:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Telegram: Posted")
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Telegram: Failed")

                time.sleep(2)

                # Post to Facebook Page
                fb_ok, fb_resp = post_to_facebook(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller)
                if fb_ok:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Facebook: Posted")
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Facebook: Failed — {fb_resp[:120]}")

            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ No products scraped")

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Error: {e}")

        time.sleep(1200)  # 1 post every 20 minutes

run_bot()
