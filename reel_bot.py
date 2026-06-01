"""
Daily Reel Bot — Creates a 15-second vertical product reel video
and posts to Instagram Reels, Facebook Video, Telegram, and YouTube Shorts.
"""
import requests
import subprocess
import os
import random
import tempfile
import textwrap
import time
import json

from PIL import Image, ImageDraw, ImageFont

import bot  # reuse credentials, scraping, helpers

# ─── YouTube credentials ──────────────────────────────────────────────────────
YOUTUBE_CLIENT_ID     = "83449014921-3r36jfqu9s0hv82409361aet6gh59i32.apps.googleusercontent.com"
YOUTUBE_CLIENT_SECRET = "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"
# Refresh token — set via env var YOUTUBE_REFRESH_TOKEN (GitHub Secret) or youtube_token.json
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
if not YOUTUBE_REFRESH_TOKEN and os.path.exists("youtube_token.json"):
    try:
        with open("youtube_token.json") as _f:
            YOUTUBE_REFRESH_TOKEN = json.load(_f).get("refresh_token", "")
    except Exception:
        pass
# ─────────────────────────────────────────────────────────────────────────────


# ─── Video creation ──────────────────────────────────────────────────────────

def load_font(size, bold=False):
    paths = [
        f'/usr/share/fonts/truetype/liberation/LiberationSans-{"Bold" if bold else "Regular"}.ttf',
        f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf',
        f'/usr/share/fonts/truetype/freefont/FreeSans{"Bold" if bold else ""}.ttf',
        f'/usr/share/fonts/truetype/ubuntu/Ubuntu-{"B" if bold else "R"}.ttf',
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def create_reel_frame(title, price, discount, image_url, short_link):
    """
    Create a 1080×1920 poster image (9:16 vertical for Reels).
    Returns path to saved JPEG.
    """
    W, H = 1080, 1920
    BG = (12, 12, 35)          # dark navy
    RED = (210, 30, 30)
    GOLD = (255, 200, 0)
    BLUE = (0, 191, 255)
    PINK = (255, 100, 180)

    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # ── Top banner ────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, 140], fill=RED)
    f_banner = load_font(62, bold=True)
    draw.text((W // 2, 70), "🛒  BUY NOW — LINK IN CAPTION / BIO  🛒",
              font=f_banner, fill="white", anchor="mm")

    # ── Product image (centre, fills most of the height) ─────────────────
    img_top, img_bot = 155, 1290
    try:
        resp = requests.get(image_url, headers=bot.HEADERS, timeout=15)
        prod = Image.open(__import__("io").BytesIO(resp.content)).convert("RGB")
        max_w, max_h = W - 40, img_bot - img_top - 10
        prod.thumbnail((max_w, max_h), Image.LANCZOS)
        px = (W - prod.width) // 2
        py = img_top + (img_bot - img_top - prod.height) // 2
        canvas.paste(prod, (px, py))
    except Exception as e:
        print(f"[REEL] Image load error: {e}")

    # ── Bottom info panel ─────────────────────────────────────────────────
    draw.rectangle([0, 1300, W, H], fill=(18, 18, 55))

    f_title = load_font(38)
    f_price = load_font(52, bold=True)
    f_link  = load_font(36)
    f_brand = load_font(34)

    # Title (word-wrap, max 3 lines)
    wrapped = textwrap.wrap(title[:130], width=30)
    y = 1325
    for line in wrapped[:3]:
        draw.text((W // 2, y), line, font=f_title, fill="white", anchor="mm")
        y += 52

    # Discount + price
    y = max(y + 20, 1490)
    if discount:
        draw.text((W // 2, y), f"💰  {discount} OFF  —  Limited Time Deal! ⚡",
                  font=f_price, fill=GOLD, anchor="mm")
        y += 65
    if price:
        draw.text((W // 2, y), f"Price: {price}", font=f_price, fill="white", anchor="mm")
        y += 65

    # Affiliate short link
    draw.text((W // 2, max(y + 10, 1670)), short_link, font=f_link, fill=BLUE, anchor="mm")

    # CTA
    draw.text((W // 2, 1760), "👆  Tap the link to grab this deal NOW!",
              font=f_price, fill=GOLD, anchor="mm")

    # Branding
    draw.text((W // 2, 1860), "@bazaarbuddylootdeals", font=f_brand, fill=PINK, anchor="mm")

    # Save frame
    path = tempfile.mktemp(suffix=".jpg")
    canvas.save(path, quality=95)
    return path


def create_reel_video(title, price, discount, image_url, short_link, duration=15):
    """
    Render a JPEG poster and encode it to a 15-second MP4 with ffmpeg.
    Returns path to the MP4 file, or None on failure.
    """
    frame_path = create_reel_frame(title, price, discount, image_url, short_link)
    out_path = tempfile.mktemp(suffix=".mp4")

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", frame_path,
        "-t", str(duration),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-movflags", "+faststart",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    try:
        os.unlink(frame_path)
    except Exception:
        pass

    if result.returncode != 0:
        print("[REEL] ffmpeg error:", result.stderr.decode()[-500:])
        return None

    size_kb = os.path.getsize(out_path) // 1024
    print(f"[REEL] Video created: {out_path}  ({size_kb} KB)")
    return out_path


# ─── Platform posting ─────────────────────────────────────────────────────────

def post_video_telegram(video_path, caption):
    url = f"https://api.telegram.org/bot{bot.BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": bot.CHAT_ID, "caption": caption,
                  "parse_mode": "HTML", "supports_streaming": True},
            files={"video": ("reel.mp4", f, "video/mp4")},
            timeout=120,
        )
    ok = resp.status_code == 200
    if not ok:
        print("[REEL][TG] Error:", resp.text[:300])
    return ok


def post_video_facebook(video_path, description):
    url = f"https://graph.facebook.com/v21.0/{bot.FB_PAGE_ID}/videos"
    with open(video_path, "rb") as f:
        resp = requests.post(
            url,
            data={"access_token": bot.FB_PAGE_TOKEN, "description": description},
            files={"source": ("reel.mp4", f, "video/mp4")},
            timeout=180,
        )
    data = resp.json()
    ok = "id" in data
    if not ok:
        print("[REEL][FB] Error:", data)
    return ok


def post_reel_instagram(video_path, caption):
    """
    Upload a Reel to Instagram using the resumable upload API.
    """
    token = bot.FB_PAGE_TOKEN
    ig_id = bot.IG_USER_ID
    file_size = os.path.getsize(video_path)

    # Step 1 — create container & get upload URI
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media",
        params={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=30,
    )
    data = r.json()
    if "id" not in data:
        print("[REEL][IG] Container error:", data)
        return False

    container_id = data["id"]
    upload_url = data.get("uri")
    if not upload_url:
        print("[REEL][IG] No upload URI returned")
        return False

    # Step 2 — upload video bytes
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    up = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(file_size),
        },
        data=video_bytes,
        timeout=180,
    )
    if up.status_code not in (200, 201):
        print("[REEL][IG] Upload error:", up.text[:300])
        return False

    # Step 3 — wait for processing
    print("[REEL][IG] Waiting for Instagram to process video...")
    for attempt in range(18):          # up to 3 minutes
        time.sleep(10)
        st = requests.get(
            f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=20,
        ).json()
        status = st.get("status_code", "")
        print(f"[REEL][IG] Status ({attempt+1}/18): {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            print("[REEL][IG] Processing error:", st)
            return False
    else:
        print("[REEL][IG] Timed out waiting for processing")
        return False

    # Step 4 — publish
    pub = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    ok = "id" in pub.json()
    if not ok:
        print("[REEL][IG] Publish error:", pub.json())
    return ok


def get_youtube_access_token():
    """Exchange refresh token for a fresh access token."""
    if not YOUTUBE_REFRESH_TOKEN:
        return None
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "refresh_token": YOUTUBE_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        data = resp.json()
        return data.get("access_token")
    except Exception as e:
        print(f"[REEL][YT] Token refresh error: {e}")
        return None


def post_video_youtube(video_path, title, price, discount, affiliate_link, hashtags):
    """Upload a short video to YouTube as a Short (#Shorts)."""
    access_token = get_youtube_access_token()
    if not access_token:
        print("[REEL][YT] No access token — skipping YouTube upload")
        return False

    short_link = bot.shorten_url(affiliate_link)
    yt_title = f"{'🔥 ' + discount + ' OFF | ' if discount else ''}{title[:80]} #Shorts"[:100]
    yt_description = (
        f"🛒 BUY NOW 👉 {short_link}\n\n"
        f"🔥 {title}\n"
        + (f"💰 {discount} OFF — Limited Time Deal! ⚡\n" if discount else "")
        + (f"🏷️ Price: {price} on Amazon India\n" if price else "")
        + f"\n✅ Amazon India Affiliate Deal (tag: dattatrey07-21)\n\n"
        f"#Shorts #AmazonDeals #LootDeals #AmazonIndia #IndiaShopping "
        f"#BazaarBuddy #DiscountDeals #OnlineShopping\n"
        + hashtags[:200]
    )

    try:
        file_size = os.path.getsize(video_path)

        # Step 1 — Initiate resumable upload
        init_resp = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(file_size),
            },
            json={
                "snippet": {
                    "title": yt_title,
                    "description": yt_description,
                    "tags": ["AmazonDeals", "LootDeals", "AmazonIndia", "Shorts",
                             "IndiaShopping", "BazaarBuddy", "OnlineShopping"],
                    "categoryId": "26",  # How-to & Style
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            },
            timeout=30,
        )

        if init_resp.status_code not in (200, 201):
            print(f"[REEL][YT] Init failed: {init_resp.status_code} {init_resp.text[:200]}")
            return False

        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            print("[REEL][YT] No upload URL returned")
            return False

        # Step 2 — Upload video bytes
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_resp = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
            },
            data=video_bytes,
            timeout=180,
        )

        if upload_resp.status_code in (200, 201):
            video_id = upload_resp.json().get("id", "")
            print(f"[REEL][YT] ✅ Uploaded! https://youtube.com/shorts/{video_id}")
            return True
        else:
            print(f"[REEL][YT] Upload failed: {upload_resp.status_code} {upload_resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[REEL][YT] Exception: {e}")
        return False


# ─── Main ────────────────────────────────────────────────────────────────────

def post_daily_reel():
    print("[REEL] ===== Daily Reel Job Started =====")

    # Scrape products and pick one
    products = bot.scrape_products()
    if not products:
        print("[REEL] No products scraped — aborting.")
        return

    title, price, affiliate_link, image_url, base_link = random.choice(products)
    rating, reviews, seller, original_price, discount = bot.get_product_details(base_link)
    short_link = bot.shorten_url(affiliate_link)
    hashtags = bot.generate_hashtags(title)

    print(f"[REEL] Product: {title[:90]}")
    print(f"[REEL] Price: {price}  Discount: {discount}")

    # Build captions
    tg_caption = (
        f"🛒 <b>BUY NOW</b> 👉 <a href='{affiliate_link}'>ORDER HERE ← CLICK</a>\n\n"
        f"🔥 {title}\n"
    )
    if discount:
        tg_caption += f"\n💰 {discount} OFF — Limited Time Deal! ⚡\n"
    if price:
        tg_caption += f"💵 At only {price}\n"
    if rating and reviews:
        tg_caption += f"⭐ {reviews} Reviews: {rating}/5.0\n"

    ig_caption = (
        f"🛒 BUY NOW 👉 {short_link}\n\n"
        f"🔥 {title}\n"
    )
    if discount:
        ig_caption += f"\n💰 {discount} OFF — Limited Time! ⚡\n"
    if price:
        ig_caption += f"💵 Price: {price}\n"
    ig_caption += f"\n👆 Tap link in caption to grab this deal!\n\n{hashtags}"

    fb_description = ig_caption

    # Create video
    video_path = create_reel_video(title, price, discount, image_url, short_link)
    if not video_path:
        print("[REEL] Video creation failed — aborting.")
        return

    results = {}

    # Telegram
    try:
        results["telegram"] = post_video_telegram(video_path, tg_caption)
    except Exception as e:
        print(f"[REEL][TG] Exception: {e}")
        results["telegram"] = False
    print(f"[REEL] Telegram: {'✅' if results['telegram'] else '❌'}")
    time.sleep(3)

    # Facebook
    try:
        results["facebook"] = post_video_facebook(video_path, fb_description)
    except Exception as e:
        print(f"[REEL][FB] Exception: {e}")
        results["facebook"] = False
    print(f"[REEL] Facebook: {'✅' if results['facebook'] else '❌'}")
    time.sleep(3)

    # Instagram Reel
    try:
        results["instagram"] = post_reel_instagram(video_path, ig_caption)
    except Exception as e:
        print(f"[REEL][IG] Exception: {e}")
        results["instagram"] = False
    print(f"[REEL] Instagram Reel: {'✅' if results['instagram'] else '❌'}")

    # YouTube Shorts
    try:
        results["youtube"] = post_video_youtube(video_path, title, price, discount, affiliate_link, hashtags)
    except Exception as e:
        print(f"[REEL][YT] Exception: {e}")
        results["youtube"] = False
    print(f"[REEL] YouTube Shorts: {'✅' if results.get('youtube') else '❌'}")

    # Cleanup
    try:
        os.unlink(video_path)
    except Exception:
        pass

    print(f"[REEL] ===== Done: TG={results['telegram']} FB={results['facebook']} IG={results['instagram']} YT={results.get('youtube')} =====")
    return results


if __name__ == "__main__":
    post_daily_reel()
