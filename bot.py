import requests
from bs4 import BeautifulSoup
import time
import random
import json

BOT_TOKEN = "8608712234:AAEQIOKSBzTeDnIZeuVUg-3mobgbBIT_KVU"
CHAT_ID = "-1003706154836"
AFFILIATE_ID = "dattatrey07-21"

FB_PAGE_ID = "1060781310451431"
FB_PAGE_TOKEN = "EAANdFOZCViOQBRS0F2wtd8AIqaSYsSxFYZBrlRUwwIjxq2uXhZB9QTnZB2nOq9VMzqQ3ZB4PQj5squ0aRqAEZCWpohspKldrF84NhltZCuSB5UZBXd2FYyVhJdqfQ6OLEJJiZBmteNx6ZA6ssVKisiWYkopAtDOzD5mP1TBBpLqjoQdZByCLeTif44btKg6XgUYQ5HBTf8c29bL"

IG_USER_ID = "17841454000638756"

# Pinterest credentials (fill these in after setup)
PINTEREST_ACCESS_TOKEN = ""   # e.g. "pina_..."
PINTEREST_BOARD_ID = ""       # e.g. "1234567890123456789"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CATEGORIES = [
    # Electronics & Tech
    "https://www.amazon.in/gp/bestsellers/electronics/",
    "https://www.amazon.in/gp/bestsellers/computers/",
    # Kitchen & Home
    "https://www.amazon.in/gp/bestsellers/kitchen/",
    "https://www.amazon.in/gp/bestsellers/home/",
    # Women's Fashion & Clothing
    "https://www.amazon.in/gp/bestsellers/apparel/1968024031/",
    "https://www.amazon.in/gp/bestsellers/apparel/1968051031/",
    # Men's Clothing & Fashion
    "https://www.amazon.in/gp/bestsellers/apparel/1968116031/",
    "https://www.amazon.in/gp/bestsellers/apparel/1968249031/",
    # Beauty & Cosmetics
    "https://www.amazon.in/gp/bestsellers/beauty/",
    "https://www.amazon.in/gp/bestsellers/beauty/2454168031/",
    "https://www.amazon.in/gp/bestsellers/beauty/2454169031/",
    # Health & Personal Care
    "https://www.amazon.in/gp/bestsellers/hpc/",
    "https://www.amazon.in/gp/bestsellers/hpc/4953617031/",
    # Shoes & Footwear
    "https://www.amazon.in/gp/bestsellers/shoes/",
    # Watches
    "https://www.amazon.in/gp/bestsellers/watches/",
    # Bags & Luggage
    "https://www.amazon.in/gp/bestsellers/luggage/",
    # Sports & Fitness
    "https://www.amazon.in/gp/bestsellers/sports/",
    # Toys & Baby
    "https://www.amazon.in/gp/bestsellers/toys/",
    "https://www.amazon.in/gp/bestsellers/baby/",
    # Books
    "https://www.amazon.in/gp/bestsellers/books/",
    # Grocery & Food
    "https://www.amazon.in/gp/bestsellers/grocery/",
    # Automotive
    "https://www.amazon.in/gp/bestsellers/automotive/",
    # Pet Supplies
    "https://www.amazon.in/gp/bestsellers/pet-supplies/",
    # Office & Stationery
    "https://www.amazon.in/gp/bestsellers/office-products/",
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
    """Facebook caption: only affiliate link at top, no prices, only % off."""
    lines = []
    lines.append(f"🛒 BUY NOW 👉 {affiliate_link}")
    lines.append("")
    lines.append(f"🔥 {title}")
    if discount:
        lines.append("")
        lines.append(f"💰 {discount} OFF — Limited Time Deal!")
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
    lines.append(f"🛒 <a href=\"{affiliate_link}\"><b>BUY NOW 👉 CLICK HERE</b></a>")
    lines.append("")
    lines.append(f"🔥 <b>{title}</b>")
    lines.append("")
    if original_price and discount:
        lines.append(f"💰 <b>At only {price} instead of {original_price} <i>({discount})</i></b>")
    else:
        lines.append(f"💰 <b>At only {price}</b>")
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
    lines.append("")
    lines.append(f"👉 <a href=\"{affiliate_link}\"><b>Order Here</b></a>")

    caption = "\n".join(lines)
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    # Use high-res image
    hi_res_url = upgrade_image_quality(image_url)
    img_bytes = download_high_res_image(image_url)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if img_bytes:
        # Upload bytes directly for guaranteed high quality delivery
        resp = requests.post(url,
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("product.jpg", img_bytes, "image/jpeg")})
    else:
        resp = requests.post(url, data={
            "chat_id": CHAT_ID,
            "photo": hi_res_url,
            "caption": caption,
            "parse_mode": "HTML"
        })
    return resp.status_code == 200


def get_fb_page_token():
    return FB_PAGE_TOKEN


def shorten_url(long_url):
    """Shorten URL via TinyURL (free, no API key needed). Falls back to original."""
    try:
        r = requests.get("https://tinyurl.com/api-create.php", params={"url": long_url}, timeout=8)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except:
        pass
    return long_url


def generate_hashtags(title):
    """Generate SEO-optimized hashtags from product title + general deal tags."""
    base_tags = [
        "#AmazonDeals", "#AmazonIndia", "#LootDeals", "#BestDeals", "#OnlineShopping",
        "#DiscountDeals", "#OfferZone", "#ShoppingDeals", "#DealsOfTheDay", "#BazaarBuddy",
        "#SaveMoney", "#IndiaShopping", "#AmazonOffers", "#BudgetBuy", "#SmartShopping"
    ]
    title_lower = title.lower()
    keyword_map = {
        # Electronics & Tech
        "oven": ["#Oven", "#MicrowaveOven", "#KitchenAppliance"],
        "microwave": ["#Microwave", "#MicrowaveOven", "#KitchenEssentials"],
        "induction": ["#InductionCooktop", "#InductionStove", "#KitchenAppliance"],
        "mixer": ["#MixerGrinder", "#KitchenAppliance", "#KitchenEssentials"],
        "phone": ["#Smartphone", "#MobilePhone", "#Tech", "#TechDeals"],
        "mobile": ["#Smartphone", "#MobilePhone", "#Tech", "#TechDeals"],
        "laptop": ["#Laptop", "#Computer", "#TechDeals", "#Tech"],
        "headphone": ["#Headphones", "#Audio", "#TechDeals", "#Music"],
        "earbud": ["#Earbuds", "#WirelessEarbuds", "#Audio", "#TechDeals"],
        "tv": ["#SmartTV", "#Television", "#HomeEntertainment", "#TV"],
        "fan": ["#Fan", "#HomeAppliance", "#SummerEssentials"],
        "cooler": ["#AirCooler", "#SummerCooling", "#HomeAppliance"],
        "ac ": ["#AirConditioner", "#AC", "#SummerCooling"],
        "refrigerator": ["#Refrigerator", "#Fridge", "#HomeAppliance"],
        "fridge": ["#Refrigerator", "#Fridge", "#HomeAppliance"],
        "washing machine": ["#WashingMachine", "#HomeAppliance"],
        "watch": ["#Watch", "#Watches", "#Wearables", "#Fashion"],
        "kitchen": ["#KitchenEssentials", "#KitchenAppliance", "#HomeKitchen"],
        "speaker": ["#Speaker", "#Audio", "#TechDeals", "#Music"],
        "camera": ["#Camera", "#Photography", "#Tech"],
        "tablet": ["#Tablet", "#Tech", "#TechDeals"],
        "vacuum": ["#VacuumCleaner", "#HomeAppliance", "#Cleaning"],
        # Women's Fashion & Clothing
        "women": ["#WomensFashion", "#WomensWear", "#WomensClothing", "#Fashion", "#OOTD"],
        "saree": ["#Saree", "#IndianWear", "#WomensFashion", "#EthnicWear", "#TraditionalWear"],
        "kurti": ["#Kurti", "#IndianWear", "#WomensFashion", "#EthnicWear"],
        "lehenga": ["#Lehenga", "#BridalWear", "#IndianFashion", "#EthnicWear"],
        "dupatta": ["#Dupatta", "#IndianWear", "#WomensFashion", "#EthnicWear"],
        "salwar": ["#SalwarSuit", "#EthnicWear", "#WomensFashion", "#IndianWear"],
        "dress": ["#Dress", "#WomensFashion", "#OOTD", "#WomensWear"],
        "top": ["#WomensTop", "#WomensFashion", "#CasualWear", "#OOTD"],
        "blouse": ["#Blouse", "#WomensFashion", "#IndianWear"],
        "legging": ["#Leggings", "#WomensWear", "#Athleisure"],
        "ethnic": ["#EthnicWear", "#IndianFashion", "#WomensFashion", "#Festive"],
        # Men's Fashion & Clothing
        "shirt": ["#MensFashion", "#MensWear", "#MensShirt", "#Style", "#OOTD"],
        "t-shirt": ["#Tshirt", "#MensFashion", "#CasualWear", "#MensWear"],
        "trouser": ["#Trousers", "#MensFashion", "#MensWear", "#Style"],
        "jeans": ["#Jeans", "#MensFashion", "#Denim", "#CasualWear"],
        "kurta": ["#Kurta", "#MensFashion", "#EthnicWear", "#IndianWear"],
        "suit": ["#Suit", "#MensFashion", "#FormalWear", "#MensWear"],
        "jacket": ["#Jacket", "#MensFashion", "#WinterWear", "#Style"],
        "hoodie": ["#Hoodie", "#CasualWear", "#MensFashion", "#Streetwear"],
        # Beauty & Cosmetics
        "lipstick": ["#Lipstick", "#Makeup", "#Beauty", "#BeautyDeals", "#Cosmetics"],
        "foundation": ["#Foundation", "#Makeup", "#Beauty", "#BeautyDeals"],
        "mascara": ["#Mascara", "#Makeup", "#Beauty", "#BeautyDeals"],
        "eyeliner": ["#Eyeliner", "#Makeup", "#Beauty", "#EyeMakeup"],
        "blush": ["#Blush", "#Makeup", "#Beauty", "#Cosmetics"],
        "kajal": ["#Kajal", "#Makeup", "#Beauty", "#EyeMakeup", "#IndianBeauty"],
        "compact": ["#Compact", "#Makeup", "#Beauty", "#Cosmetics"],
        "primer": ["#Primer", "#Makeup", "#Beauty", "#Skincare"],
        "concealer": ["#Concealer", "#Makeup", "#Beauty", "#Cosmetics"],
        "palette": ["#MakeuPalette", "#Makeup", "#Beauty", "#Cosmetics"],
        "nail": ["#NailPolish", "#NailArt", "#Beauty", "#Cosmetics"],
        "perfume": ["#Perfume", "#Fragrance", "#Beauty", "#Luxury"],
        "deodorant": ["#Deodorant", "#PersonalCare", "#Health", "#Grooming"],
        # Skincare
        "moisturizer": ["#Moisturizer", "#Skincare", "#Beauty", "#GlowingSkin"],
        "sunscreen": ["#Sunscreen", "#Skincare", "#SPF", "#SkinProtection"],
        "serum": ["#Serum", "#Skincare", "#AntiAging", "#GlowingSkin"],
        "face wash": ["#FaceWash", "#Skincare", "#Beauty", "#SkinCare"],
        "toner": ["#Toner", "#Skincare", "#Beauty", "#GlowingSkin"],
        "face mask": ["#FaceMask", "#Skincare", "#Beauty", "#SelfCare"],
        "cream": ["#Cream", "#Skincare", "#Beauty", "#SkinCare"],
        "scrub": ["#Scrub", "#Skincare", "#Beauty", "#SelfCare"],
        "cleanser": ["#Cleanser", "#Skincare", "#Beauty", "#SkinCare"],
        "sheet mask": ["#SheetMask", "#Skincare", "#Beauty", "#KoreanBeauty"],
        # Hair Care
        "shampoo": ["#Shampoo", "#HairCare", "#Beauty", "#HairGoals"],
        "conditioner": ["#Conditioner", "#HairCare", "#Beauty", "#HairGoals"],
        "hair oil": ["#HairOil", "#HairCare", "#Beauty", "#HairGrowth"],
        "hair serum": ["#HairSerum", "#HairCare", "#Beauty", "#HairGoals"],
        "hair color": ["#HairColor", "#HairDye", "#Beauty", "#HairGoals"],
        # Health & Wellness
        "protein": ["#Protein", "#ProteinSupplement", "#Fitness", "#Health", "#Gym"],
        "vitamin": ["#Vitamins", "#HealthSupplements", "#Health", "#Wellness"],
        "supplement": ["#Supplements", "#Health", "#Fitness", "#Wellness"],
        "omega": ["#Omega3", "#Health", "#Supplements", "#Wellness"],
        "ayurvedic": ["#Ayurvedic", "#NaturalHealth", "#Health", "#Wellness", "#Ayurveda"],
        "medicine": ["#Medicine", "#Health", "#Wellness"],
        "sanitizer": ["#Sanitizer", "#Hygiene", "#Health"],
        # Fitness
        "fitness": ["#Fitness", "#Health", "#Gym", "#Workout", "#FitIndia"],
        "yoga": ["#Yoga", "#Fitness", "#Health", "#Wellness", "#YogaLife"],
        "dumbbell": ["#Dumbbell", "#Gym", "#Fitness", "#Workout"],
        "resistance": ["#ResistanceBand", "#Fitness", "#HomeWorkout", "#Gym"],
        "treadmill": ["#Treadmill", "#Fitness", "#HomeGym", "#Workout"],
        # Shoes & Footwear
        "shoe": ["#Shoes", "#Footwear", "#Fashion", "#Style"],
        "sandal": ["#Sandals", "#Footwear", "#WomensFashion", "#Summer"],
        "slipper": ["#Slippers", "#Footwear", "#Casual", "#Comfort"],
        "sneaker": ["#Sneakers", "#Footwear", "#Fashion", "#Style"],
        "heel": ["#Heels", "#WomensFashion", "#Footwear", "#Style"],
        "boot": ["#Boots", "#Footwear", "#Fashion", "#Style"],
        # Bags & Accessories
        "bag": ["#Bags", "#Fashion", "#Handbags", "#Style"],
        "handbag": ["#Handbag", "#WomensFashion", "#Bags", "#Style"],
        "backpack": ["#Backpack", "#Bags", "#Travel", "#Style"],
        "wallet": ["#Wallet", "#Accessories", "#Fashion", "#MensFashion"],
        "luggage": ["#Luggage", "#Travel", "#Bags", "#TravelEssentials"],
        # Kids & Baby
        "toy": ["#Toys", "#KidsToys", "#Baby", "#Kids"],
        "baby": ["#Baby", "#BabyProducts", "#NewMom", "#Parenting"],
        "diaper": ["#Diapers", "#Baby", "#BabyEssentials", "#Parenting"],
        # Books
        "book": ["#Books", "#Reading", "#Bookstagram", "#BookLovers"],
        # Sports
        "cricket": ["#Cricket", "#Sports", "#CricketIndia", "#Fitness"],
        "badminton": ["#Badminton", "#Sports", "#Fitness"],
        "football": ["#Football", "#Sports", "#Fitness"],
        # Grooming
        "trimmer": ["#Trimmer", "#Grooming", "#MensGrooming", "#Style"],
        "shaver": ["#Shaver", "#Grooming", "#MensGrooming", "#Style"],
        "razor": ["#Razor", "#Grooming", "#PersonalCare"],
        # Home
        "bottle": ["#WaterBottle", "#Lifestyle", "#HomeEssentials"],
        "iron": ["#Iron", "#HomeAppliance", "#Laundry"],
        "pillow": ["#Pillow", "#HomeDecor", "#Bedding", "#ComfortHome"],
        "bedsheet": ["#Bedsheet", "#HomeDecor", "#Bedding", "#HomeEssentials"],
        "curtain": ["#Curtains", "#HomeDecor", "#InteriorDesign"],
        # Grocery & Food
        "coffee": ["#Coffee", "#CoffeeLover", "#Grocery", "#MorningVibes"],
        "tea": ["#Tea", "#ChaiLover", "#Grocery", "#IndiaVibes"],
        "chocolate": ["#Chocolate", "#Snacks", "#Grocery", "#Foodie"],
        "snack": ["#Snacks", "#Grocery", "#Foodie", "#MunchTime"],
        "protein bar": ["#ProteinBar", "#Fitness", "#Health", "#Snacks"],
        # Automotive
        "car": ["#CarAccessories", "#Automotive", "#CarCare", "#Driving"],
        "helmet": ["#Helmet", "#Safety", "#Bike", "#Automotive"],
        # Pet
        "pet": ["#PetLovers", "#PetCare", "#DogLovers", "#CatLovers"],
        "dog": ["#DogLovers", "#PetCare", "#Dogs", "#DogLife"],
        "cat": ["#CatLovers", "#PetCare", "#Cats", "#CatLife"],
    }
    extra_tags = []
    for kw, tags in keyword_map.items():
        if kw in title_lower:
            extra_tags.extend(tags)
    # Combine and de-duplicate, max 25 tags
    all_tags = list(dict.fromkeys(extra_tags + base_tags))[:25]
    return " ".join(all_tags)


def upgrade_image_quality(image_url):
    """Convert Amazon image URL to high-resolution version"""
    if not image_url:
        return image_url
    if "._" in image_url:
        base = image_url.split("._")[0]
        return base + "._SL2000_.jpg"
    return image_url


def download_high_res_image(image_url):
    """Try multiple resolutions to get the best quality image"""
    if not image_url:
        return None
    base = image_url.split("._")[0] if "._" in image_url else image_url
    for suffix in ["._SL2000_.jpg", "._SL1500_.jpg", "._SL1000_.jpg", ".jpg"]:
        try:
            test_url = base + suffix
            resp = requests.get(test_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 10000:
                return resp.content
        except:
            continue
    # Fallback to original URL
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.content
    except:
        pass
    return None


def post_to_instagram(title, discount, image_url, affiliate_link, rating, reviews):
    """Post to Instagram Business Account with hashtags + short link + BUY NOW."""
    page_token = get_fb_page_token()
    if not page_token:
        return False, "No page token"

    # Shorten the affiliate link
    short_link = shorten_url(affiliate_link)

    # Build SEO-optimized caption
    hashtags = generate_hashtags(title)
    lines = []
    lines.append("🛒 BUY NOW 👉 " + short_link)
    lines.append("")
    lines.append("🔥 " + title)
    if discount:
        lines.append("")
        lines.append("💰 " + discount + " OFF — Limited Time Deal! ⚡")
    if rating or reviews:
        rev_line = ""
        if reviews:
            rev_line += "⭐ " + reviews + " Reviews"
        if rating:
            rev_line += ": " + rating + "/5.0"
        lines.append("")
        lines.append(rev_line)
    lines.append("")
    lines.append("👆 Tap link in caption to grab this deal NOW!")
    lines.append("")
    lines.append(hashtags)
    caption = "\n".join(lines)
    if len(caption) > 2200:  # Instagram caption limit
        caption = caption[:2197] + "..."

    # Use a publicly accessible Amazon image URL (Instagram needs URL, not bytes)
    hi_res_url = upgrade_image_quality(image_url)

    try:
        # Step 1: Create media container
        create_resp = requests.post(
            f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
            data={
                "image_url": hi_res_url,
                "caption": caption,
                "access_token": page_token
            },
            timeout=30
        )
        if create_resp.status_code != 200:
            return False, f"IG create failed: {create_resp.text[:150]}"

        creation_id = create_resp.json().get("id")
        if not creation_id:
            return False, "No creation ID"

        # Wait briefly for IG to process the image
        time.sleep(3)

        # Step 2: Publish the media
        publish_resp = requests.post(
            f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": page_token},
            timeout=30
        )
        return publish_resp.status_code == 200, publish_resp.text
    except Exception as e:
        return False, str(e)


def post_to_facebook(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller):
    message = build_caption_plain(title, price, original_price, discount, affiliate_link, rating, reviews, seller)
    page_token = get_fb_page_token()
    if not page_token:
        return False, "Could not get page token"

    try:
        # Download high-res image
        img_bytes = download_high_res_image(image_url)
        if not img_bytes:
            return False, "Image download failed"

        # Step 1: Upload photo as unpublished to get photo ID
        photo_resp = requests.post(
            f"https://graph.facebook.com/{FB_PAGE_ID}/photos",
            data={"published": "false", "access_token": page_token},
            files={"source": ("product.jpg", img_bytes, "image/jpeg")}
        )
        photo_data = photo_resp.json()
        photo_id = photo_data.get("id")

        if not photo_id:
            return False, f"Photo upload failed: {photo_resp.text[:150]}"

        # Step 2: Post to page feed with attached photo + link (image becomes clickable to affiliate)
        feed_resp = requests.post(
            f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
            data={
                "message": message,
                "attached_media": json.dumps([{"media_fbid": photo_id}]),
                "link": affiliate_link,
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
                hi_res_image = upgrade_image_quality(image_url)
                products.append((title, price, affiliate_link, hi_res_image, base_link))
        except:
            continue

    return products


def generate_pinterest_description(title, price, discount, rating, reviews, affiliate_link, hashtags):
    """
    SEO-optimised Pinterest pin description targeting Indian shoppers.
    Pinterest indexes first ~150 chars heavily — lead with value keywords.
    """
    lines = []
    # Lead with deal hook
    if discount:
        lines.append(f"🔥 {discount} OFF | Best Price in India!")
    lines.append(f"🛒 {title}")
    if price:
        lines.append(f"💰 Only {price} on Amazon India")
    if rating and reviews:
        lines.append(f"⭐ {reviews} Reviews | {rating}/5 Rating")
    lines.append("")
    lines.append("✅ Fast Delivery across India | Amazon Prime Eligible")
    lines.append("💡 Great deal for Indian buyers — limited time offer!")
    lines.append("")
    lines.append(f"👉 BUY NOW: {affiliate_link}")
    lines.append("")
    # Indian-audience keywords + hashtags
    india_keywords = (
        "#AmazonIndia #IndiaShopping #BestDealsIndia #OnlineShoppingIndia "
        "#AmazonDeals #LootDeal #IndianShoppers #BudgetBuyIndia #DiscountIndia "
        "#SaveMoneyIndia #DealOfTheDay #AffiliateDeals #TopDealsIndia "
    )
    lines.append(india_keywords + hashtags)
    return "\n".join(lines)[:500]   # Pinterest description limit ~500 chars shown


def post_to_pinterest(title, price, discount, image_url, affiliate_link, rating, reviews, hashtags):
    """Post a pin to Pinterest with Indian-SEO-optimised description."""
    if not PINTEREST_ACCESS_TOKEN or not PINTEREST_BOARD_ID:
        return False, "Pinterest credentials not set"

    hi_res = upgrade_image_quality(image_url)
    description = generate_pinterest_description(
        title, price, discount, rating, reviews, affiliate_link, hashtags
    )
    # Pinterest pin title: first 100 chars of product name
    pin_title = title[:100]

    payload = {
        "board_id": PINTEREST_BOARD_ID,
        "title": pin_title,
        "description": description,
        "link": affiliate_link,
        "alt_text": f"{title[:500]} | Amazon India Deal",
        "media_source": {
            "source_type": "image_url",
            "url": hi_res,
        },
    }
    headers = {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        "https://api.pinterest.com/v5/pins",
        json=payload,
        headers=headers,
        timeout=20,
    )
    data = resp.json()
    ok = "id" in data
    if not ok:
        print(f"[Pinterest] Error: {data}")
    return ok, data.get("id", str(data))


def post_one_round():
    """Post a single product to all platforms. Returns dict with results."""
    result = {
        "title": "",
        "telegram": False,
        "facebook": False,
        "instagram": False,
        "pinterest": False,
        "error": None,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    try:
        products = scrape_products()
        if not products:
            result["error"] = "No products scraped"
            return result

        title, price, affiliate_link, image_url, base_link = random.choice(products)
        result["title"] = title
        rating, reviews, seller, original_price, discount = get_product_details(base_link)
        hashtags = generate_hashtags(title)

        # Telegram
        try:
            result["telegram"] = send_to_telegram(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller)
        except Exception:
            result["telegram"] = False

        time.sleep(2)
        # Facebook
        try:
            fb_ok, _ = post_to_facebook(title, price, original_price, discount, image_url, affiliate_link, rating, reviews, seller)
            result["facebook"] = fb_ok
        except Exception:
            result["facebook"] = False

        time.sleep(2)
        # Instagram
        try:
            ig_ok, _ = post_to_instagram(title, discount, image_url, affiliate_link, rating, reviews)
            result["instagram"] = ig_ok
        except Exception:
            result["instagram"] = False

        time.sleep(2)
        # Pinterest
        try:
            pt_ok, _ = post_to_pinterest(title, price, discount, image_url, affiliate_link, rating, reviews, hashtags)
            result["pinterest"] = pt_ok
        except Exception:
            result["pinterest"] = False

    except Exception as e:
        result["error"] = str(e)

    return result
