"""
Daily Reel Bot — Creates a high-quality animated 30-second vertical product reel video
with background music, SEO-optimized captions, and posts to Instagram, Facebook,
Telegram, and YouTube Shorts.
"""
import requests
import subprocess
import os
import random
import tempfile
import textwrap
import time
import json
import math

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

import bot  # reuse credentials, scraping, helpers

# ─── YouTube credentials ──────────────────────────────────────────────────────
YOUTUBE_CHANNEL_ID    = "UCtsNT0iG_1nsFW9JGqwA_NQ"   # @BazaarBuddyLootDeals
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
if not YOUTUBE_REFRESH_TOKEN and os.path.exists("youtube_token.json"):
    try:
        with open("youtube_token.json") as _f:
            _tok = json.load(_f)
            YOUTUBE_REFRESH_TOKEN = _tok.get("refresh_token", "")
            if not YOUTUBE_CLIENT_ID:
                YOUTUBE_CLIENT_ID = _tok.get("client_id", "")
            if not YOUTUBE_CLIENT_SECRET:
                YOUTUBE_CLIENT_SECRET = _tok.get("client_secret", "")
    except Exception:
        pass
# ─────────────────────────────────────────────────────────────────────────────

W, H = 1080, 1920   # 9:16 vertical

# ─── Colour palette ──────────────────────────────────────────────────────────
C_BG_TOP    = (8,   5,  30)    # deep midnight
C_BG_BOT    = (20, 10,  55)    # dark violet
C_ACCENT    = (255, 60,  90)   # neon pink-red
C_GOLD      = (255, 200,  0)   # bright gold
C_CYAN      = (0,  210, 255)   # electric cyan
C_WHITE     = (255, 255, 255)
C_PANEL     = (18,  12,  50, 210)  # semi-transparent dark panel


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_font(size, bold=False, italic=False):
    candidates = []
    if bold and italic:
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        ]
    elif bold:
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_gradient_rect(draw, x0, y0, x1, y1, color_top, color_bot):
    """Vertical gradient filled rectangle."""
    for y in range(y0, y1):
        t = (y - y0) / max(y1 - y0, 1)
        r = int(color_top[0] + t * (color_bot[0] - color_top[0]))
        g = int(color_top[1] + t * (color_bot[1] - color_top[1]))
        b = int(color_top[2] + t * (color_bot[2] - color_top[2]))
        draw.line([(x0, y), (x1, y)], fill=(r, g, b))


def rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=3):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=outline, width=width)


def add_glow(img, color, blur_radius=18):
    """Create a coloured glow layer and composite onto img."""
    glow = Image.new("RGB", img.size, (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rectangle([0, 0, img.width, img.height], fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
    return Image.blend(img, glow, alpha=0.18)


def draw_stars(draw, count=60, seed=42):
    """Scatter small star dots across the canvas."""
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, W)
        y = rng.randint(0, H // 2)
        r = rng.choice([1, 1, 1, 2, 2, 3])
        brightness = rng.randint(140, 255)
        draw.ellipse([x - r, y - r, x + r, y + r],
                     fill=(brightness, brightness, brightness))


def draw_particles(draw, count=30, seed=7):
    """Glowing small dots — purple/cyan/gold."""
    rng = random.Random(seed)
    colours = [(255, 60, 90), (0, 210, 255), (255, 200, 0),
               (180, 0, 255), (60, 255, 180)]
    for _ in range(count):
        x = rng.randint(0, W)
        y = rng.randint(0, H)
        r = rng.randint(2, 8)
        c = rng.choice(colours)
        alpha = rng.randint(80, 200)
        overlay = Image.new("RGBA", (r * 4, r * 4), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([r, r, r * 3, r * 3], fill=(*c, alpha))
        # This is a workaround — we'll just draw directly
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)


def paste_product_image(canvas, image_url, box_y0, box_y1):
    """Download and paste product image with glow + rounded shadow."""
    try:
        resp = requests.get(image_url, headers=bot.HEADERS, timeout=15)
        import io
        prod = Image.open(io.BytesIO(resp.content)).convert("RGBA")

        max_w = W - 80
        max_h = box_y1 - box_y0 - 20
        prod.thumbnail((max_w, max_h), Image.LANCZOS)

        # White background for product
        bg = Image.new("RGBA", prod.size, (255, 255, 255, 255))
        bg.paste(prod, mask=prod if prod.mode == "RGBA" else None)
        prod = bg.convert("RGB")

        # Subtle glow border
        padded = Image.new("RGB", (prod.width + 20, prod.height + 20), (30, 15, 70))
        padded.paste(prod, (10, 10))

        px = (W - padded.width) // 2
        py = box_y0 + (box_y1 - box_y0 - padded.height) // 2
        canvas.paste(padded, (px, py))
        return True
    except Exception as e:
        print(f"[REEL] Product image error: {e}")
        return False


def draw_shimmer_badge(draw, cx, cy, text, bg_color, text_color, font):
    """Pill-shaped coloured badge."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 36, 18
    x0 = cx - tw // 2 - pad_x
    x1 = cx + tw // 2 + pad_x
    y0 = cy - th // 2 - pad_y
    y1 = cy + th // 2 + pad_y
    # Shadow
    draw.rounded_rectangle([x0 + 4, y0 + 4, x1 + 4, y1 + 4],
                            radius=40, fill=(0, 0, 0, 120))
    # Badge
    draw.rounded_rectangle([x0, y0, x1, y1], radius=40, fill=bg_color)
    draw.text((cx, cy), text, font=font, fill=text_color, anchor="mm")
    return y1


# ─── Frame builder ────────────────────────────────────────────────────────────

def build_frame(title, price, discount, image_url, short_link, scene=1):
    """
    scene 1 → product showcase (used for main still)
    Returns PIL Image (RGB, 1080×1920).
    """
    # ── Background gradient ────────────────────────────────────────────────
    img = Image.new("RGB", (W, H), C_BG_TOP)
    draw = ImageDraw.Draw(img)
    draw_gradient_rect(draw, 0, 0, W, H, C_BG_TOP, C_BG_BOT)

    # ── Stars & particles ─────────────────────────────────────────────────
    draw_stars(draw, count=80)
    draw_particles(draw, count=25)

    # ── Glowing diagonal accent lines ─────────────────────────────────────
    for i in range(0, W + H, 120):
        draw.line([(0, i), (i, 0)], fill=(60, 30, 120), width=1)

    # ── Top banner ────────────────────────────────────────────────────────
    draw_gradient_rect(draw, 0, 0, W, 130, (180, 0, 60), (220, 30, 90))
    f_banner = load_font(46, bold=True)
    draw.text((W // 2, 65), "🔥  BAZAAR BUDDY LOOT DEALS  🔥",
              font=f_banner, fill=C_WHITE, anchor="mm")

    # ── Decorative horizontal line ─────────────────────────────────────────
    draw.rectangle([0, 130, W, 136], fill=C_GOLD)

    # ── Product image area ────────────────────────────────────────────────
    IMG_TOP, IMG_BOT = 148, 1050
    # image background panel with rounded corners
    draw.rounded_rectangle([20, IMG_TOP, W - 20, IMG_BOT],
                            radius=24, fill=(255, 255, 255, 30))
    paste_product_image(img, image_url, IMG_TOP + 10, IMG_BOT - 10)
    draw = ImageDraw.Draw(img)   # re-init draw after pasting

    # ── Glowing border around image ──────────────────────────────────────
    for off, col, w in [(4, (255, 200, 0, 60), 3), (2, (255, 60, 90, 120), 2)]:
        draw.rounded_rectangle([20 - off, IMG_TOP - off, W - 20 + off, IMG_BOT + off],
                                radius=26, outline=col[:3], width=w)

    # ── Bottom info panel ─────────────────────────────────────────────────
    draw_gradient_rect(draw, 0, 1060, W, H, (14, 8, 45), (8, 4, 25))
    draw.rectangle([0, 1060, W, 1068], fill=C_CYAN)  # thin separator line

    y = 1090

    # Title
    f_title = load_font(40, bold=True)
    wrapped = textwrap.wrap(title[:160], width=26)
    for line in wrapped[:3]:
        draw.text((W // 2, y), line, font=f_title, fill=C_WHITE, anchor="mm")
        y += 55
    y += 10

    # Discount badge
    if discount:
        f_badge = load_font(50, bold=True)
        y = draw_shimmer_badge(draw, W // 2, y + 40,
                               f"🔥 {discount} OFF!", C_ACCENT, C_WHITE, f_badge) + 20

    # Price
    if price:
        f_price = load_font(58, bold=True)
        draw.text((W // 2, y + 10), f"💰 {price}", font=f_price, fill=C_GOLD, anchor="mm")
        y += 80

    # Affiliate short link in a cyan box
    f_link = load_font(36)
    link_y = max(y + 20, 1640)
    draw.rounded_rectangle([40, link_y - 30, W - 40, link_y + 50],
                            radius=16, fill=(0, 40, 80))
    draw.rounded_rectangle([40, link_y - 30, W - 40, link_y + 50],
                            radius=16, outline=C_CYAN, width=2)
    draw.text((W // 2, link_y + 10), f"🛒  {short_link}",
              font=f_link, fill=C_CYAN, anchor="mm")

    # CTA arrow button
    f_cta = load_font(46, bold=True)
    cta_y = link_y + 110
    draw_shimmer_badge(draw, W // 2, cta_y, "👆  TAP TO BUY NOW  👆",
                       C_GOLD, (10, 5, 30), f_cta)

    # Branding footer
    f_brand = load_font(32)
    draw.text((W // 2, 1880), "@BazaarBuddyLootDeals  |  Amazon India Deals",
              font=f_brand, fill=(180, 180, 220), anchor="mm")

    return img


# ─── Background music ─────────────────────────────────────────────────────────

MUSIC_URLS = [
    # Royalty-free upbeat tracks from Pixabay (Free License)
    "https://cdn.pixabay.com/download/audio/2023/10/26/audio_e2062a7f17.mp3",
    "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3",
    "https://cdn.pixabay.com/download/audio/2023/06/07/audio_0b7fae6ccd.mp3",
    "https://cdn.pixabay.com/download/audio/2022/08/23/audio_2dde668d05.mp3",
]

def download_music():
    """Try to download a royalty-free background track. Returns path or None."""
    music_path = tempfile.mktemp(suffix=".mp3")
    for url in MUSIC_URLS:
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 10000:
                with open(music_path, "wb") as f:
                    f.write(r.content)
                print(f"[REEL] Music downloaded ({len(r.content)//1024} KB)")
                return music_path
        except Exception as e:
            print(f"[REEL] Music download failed ({url[:50]}): {e}")
    return None


def generate_music_ffmpeg(duration=30):
    """Generate a pleasant upbeat synthetic background track using ffmpeg."""
    out_path = tempfile.mktemp(suffix=".mp3")
    # Layered sine waves: bass + melody + hi beat
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", (
            f"aevalsrc="
            f"'0.25*sin(2*PI*80*t)"          # bass
            f"+0.2*sin(2*PI*320*t)"           # mid
            f"+0.15*sin(2*PI*640*t)"          # high
            f"+0.1*sin(2*PI*1280*t*((int(t*4)%2)+1))"  # rhythm
            f"':s=44100:d={duration}"
        ),
        "-af", "afade=t=in:st=0:d=1,afade=t=out:st={fade_out}:d=2".format(
            fade_out=max(1, duration - 2)
        ),
        "-q:a", "4",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(out_path):
        print("[REEL] Synthetic music generated")
        return out_path
    print("[REEL] Music generation failed:", result.stderr.decode()[-200:])
    return None


# ─── Animated video creation ──────────────────────────────────────────────────

def create_reel_video(title, price, discount, image_url, short_link, duration=30):
    """
    Create a beautiful animated 9:16 vertical video:
    - Ken Burns (zoom-pan) effect on the product frame
    - Animated text overlays via ffmpeg drawtext
    - Background music mixed in
    Returns path to the MP4 file, or None on failure.
    """
    print("[REEL] Building frames...")

    # ── Build main poster frame ────────────────────────────────────────────
    frame_img = build_frame(title, price, discount, image_url, short_link)
    frame_path = tempfile.mktemp(suffix=".jpg")
    frame_img.save(frame_path, quality=97)

    # ── Get / generate background music ───────────────────────────────────
    music_path = download_music()
    if not music_path:
        music_path = generate_music_ffmpeg(duration)

    out_path = tempfile.mktemp(suffix=".mp4")

    # ── Build ffmpeg filter_complex for animation ─────────────────────────
    # zoompan: zoom from 1.0→1.12 over the duration (Ken Burns) then slight
    # horizontal drift for dynamism
    zoom_expr   = f"zoom='min(1.0+0.12*on/{duration*30},1.12)'"
    x_expr      = "x='iw/2-(iw/zoom/2)+sin(on/{fps}*0.4)*8'".format(fps=30)
    y_expr      = "y='ih/2-(ih/zoom/2)'"
    zoompan_str = (
        f"zoompan={zoom_expr}:{x_expr}:{y_expr}"
        f":d={duration * 30}:s={W}x{H}:fps=30"
    )

    title_safe   = title[:50].replace("'", "").replace(":", " ").replace("%", "pct")
    price_safe   = (price or "").replace("'", "")
    discount_safe = (discount or "").replace("'", "")

    # drawtext overlays that animate in (fade via alpha expression)
    # Text 1: "HOT DEAL ALERT" fades in at t=1
    dt1 = (
        "drawtext=text='🔥 HOT DEAL ALERT 🔥'"
        ":fontsize=54:fontcolor=white:x=(w-tw)/2:y=40"
        ":enable='gte(t,0)':alpha='if(lt(t,1),t,1)'"
        ":fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ":shadowcolor=black:shadowx=2:shadowy=2"
    )
    # Text 2: Price fades in at t=3
    if price_safe:
        dt2 = (
            f"drawtext=text='{price_safe}'"
            ":fontsize=70:fontcolor=#FFD700:x=(w-tw)/2:y=h-280"
            ":enable='gte(t,2)':alpha='if(lt(t,2),0,if(lt(t,4),(t-2)/2,1))'"
            ":fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            ":shadowcolor=black:shadowx=3:shadowy=3"
        )
    else:
        dt2 = "null"

    # Text 3: DISCOUNT badge pulses from t=5
    if discount_safe:
        dt3 = (
            f"drawtext=text='💰 {discount_safe} OFF — LIMITED TIME!'"
            ":fontsize=48:fontcolor=#FF3C5A:x=(w-tw)/2:y=h-200"
            ":enable='gte(t,4)':alpha='if(lt(t,4),0,if(lt(t,6),(t-4)/2,1))'"
            ":fontfile=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            ":shadowcolor=black:shadowx=2:shadowy=2"
        )
    else:
        dt3 = "null"

    # Build filter chain
    filters = [zoompan_str]
    if dt2 != "null":
        filters.append(dt2)
    if dt3 != "null":
        filters.append(dt3)
    filter_chain = ",".join(filters)

    # ── Assemble ffmpeg command ────────────────────────────────────────────
    if music_path and os.path.exists(music_path):
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-i", music_path,
            "-filter_complex",
                f"[0:v]{filter_chain}[vout];"
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{duration},afade=t=in:st=0:d=1,"
                f"afade=t=out:st={duration-2}:d=2,volume=0.6[aout]",
            "-map", "[vout]",
            "-map", "[aout]",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-r", "30",
            "-movflags", "+faststart",
            out_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-filter_complex", f"[0:v]{filter_chain}[vout]",
            "-map", "[vout]",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-movflags", "+faststart",
            out_path,
        ]

    print("[REEL] Rendering video (this takes ~30s)...")
    result = subprocess.run(cmd, capture_output=True)

    for p in [frame_path, music_path]:
        try:
            if p and os.path.exists(p):
                os.unlink(p)
        except Exception:
            pass

    if result.returncode != 0:
        print("[REEL] ffmpeg error:", result.stderr.decode()[-800:])
        return None

    size_kb = os.path.getsize(out_path) // 1024
    print(f"[REEL] ✅ Video created: {out_path}  ({size_kb} KB)")
    return out_path


# ─── SEO caption builder ─────────────────────────────────────────────────────

def build_seo_caption(title, price, discount, rating, reviews, short_link,
                       platform="instagram"):
    """Build a rich, SEO-optimised caption for each platform."""
    deal_line  = f"🔥 {discount} OFF — Limited Time!" if discount else "🔥 Hot Deal!"
    price_line = f"💰 Only {price} on Amazon India" if price else ""
    rating_line = f"⭐ {rating}/5 • {reviews} Reviews" if rating and reviews else ""

    hashtags = (
        "#Shorts #AmazonIndia #LootDeals #AmazonDeals #OnlineShopping "
        "#TechDeals #IndiaDeals #BestDeals #BuyNow #DealAlert "
        "#DiscountDeals #BazaarBuddy #AmazonSale #FlashSale "
        "#DealOfTheDay #SaleAlert #ShoppingDeals #GrabNow"
    )

    if platform == "telegram":
        return (
            f"🛒 <b>BUY NOW</b> 👉 <a href='{short_link}'>ORDER HERE ← CLICK</a>\n\n"
            f"🔥 <b>{title}</b>\n\n"
            f"{deal_line}\n"
            + (f"{price_line}\n" if price_line else "")
            + (f"{rating_line}\n" if rating_line else "")
            + f"\n✅ Amazon India Affiliate Deal\n"
            f"🔗 {short_link}"
        )

    if platform == "youtube":
        return (
            f"🛒 BUY NOW 👉 {short_link}\n\n"
            f"🔥 {title}\n\n"
            f"{deal_line}\n"
            + (f"{price_line}\n" if price_line else "")
            + (f"{rating_line}\n" if rating_line else "")
            + f"\n✅ Amazon India Affiliate Deal (tag: dattatrey07-21)\n"
            f"📌 Link in description!\n\n"
            f"─────────────────────\n"
            f"🔔 SUBSCRIBE for daily deals → @BazaarBuddyLootDeals\n"
            f"─────────────────────\n\n"
            + hashtags
        )

    # Instagram / Facebook
    return (
        f"🛒 BUY NOW 👉 {short_link}\n\n"
        f"🔥 {title}\n\n"
        f"{deal_line}\n"
        + (f"{price_line}\n" if price_line else "")
        + (f"{rating_line}\n" if rating_line else "")
        + f"\n👆 Tap link in caption/bio to order!\n\n"
        + hashtags
    )


def build_youtube_title(title, price, discount):
    """SEO-optimised YouTube title under 100 chars."""
    disc = f"{discount} OFF | " if discount else ""
    pr   = f" at {price}" if price else ""
    base = f"🔥 {disc}{title[:60]}{pr} | Amazon India Deal #Shorts"
    return base[:100]


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
    token   = bot.FB_PAGE_TOKEN
    ig_id   = bot.IG_USER_ID
    file_size = os.path.getsize(video_path)

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
    upload_url   = data.get("uri")
    if not upload_url:
        print("[REEL][IG] No upload URI")
        return False

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

    print("[REEL][IG] Waiting for Instagram processing...")
    for attempt in range(18):
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
        print("[REEL][IG] Timed out")
        return False

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
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[REEL][YT] Token refresh error: {e}")
        return None


def post_video_youtube(video_path, title, price, discount, affiliate_link, hashtags):
    access_token = get_youtube_access_token()
    if not access_token:
        print("[REEL][YT] No access token — skipping")
        return False

    short_link  = bot.shorten_url(affiliate_link)
    yt_title    = build_youtube_title(title, price, discount)
    yt_desc     = build_seo_caption(title, price, discount, None, None,
                                    short_link, platform="youtube")

    try:
        file_size = os.path.getsize(video_path)

        init_resp = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(file_size),
            },
            json={
                "snippet": {
                    "title": yt_title,
                    "description": yt_desc,
                    "tags": [
                        "AmazonDeals", "LootDeals", "AmazonIndia", "Shorts",
                        "IndiaShopping", "BazaarBuddy", "OnlineShopping",
                        "DealAlert", "FlashSale", "BestDeals",
                    ],
                    "categoryId": "26",
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
            print(f"[REEL][YT] Init failed: {init_resp.status_code}")
            return False

        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            print("[REEL][YT] No upload URL")
            return False

        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_resp = requests.put(
            upload_url,
            headers={"Content-Type": "video/mp4", "Content-Length": str(file_size)},
            data=video_bytes,
            timeout=180,
        )

        if upload_resp.status_code in (200, 201):
            video_id = upload_resp.json().get("id", "")
            print(f"[REEL][YT] ✅ https://youtube.com/shorts/{video_id}")
            return True
        else:
            print(f"[REEL][YT] Upload failed: {upload_resp.status_code}")
            return False

    except Exception as e:
        print(f"[REEL][YT] Exception: {e}")
        return False


# ─── Main ────────────────────────────────────────────────────────────────────

def post_daily_reel():
    print("[REEL] ===== Daily Reel Job Started =====")

    products = bot.scrape_products()
    if not products:
        print("[REEL] No products — aborting.")
        return

    title, price, affiliate_link, image_url, base_link = random.choice(products)
    rating, reviews, seller, original_price, discount = bot.get_product_details(base_link)
    short_link = bot.shorten_url(affiliate_link)
    hashtags   = bot.generate_hashtags(title)

    print(f"[REEL] Product: {title[:80]}")
    print(f"[REEL] Price: {price}  Discount: {discount}")

    tg_caption = build_seo_caption(title, price, discount, rating, reviews,
                                   affiliate_link, platform="telegram")
    ig_caption = build_seo_caption(title, price, discount, rating, reviews,
                                   short_link, platform="instagram")
    fb_desc    = ig_caption

    video_path = create_reel_video(title, price, discount, image_url, short_link)
    if not video_path:
        print("[REEL] Video creation failed — aborting.")
        return

    results = {}

    try:
        results["telegram"] = post_video_telegram(video_path, tg_caption)
    except Exception as e:
        print(f"[REEL][TG] Exception: {e}")
        results["telegram"] = False
    print(f"[REEL] Telegram: {'✅' if results['telegram'] else '❌'}")
    time.sleep(3)

    try:
        results["facebook"] = post_video_facebook(video_path, fb_desc)
    except Exception as e:
        print(f"[REEL][FB] Exception: {e}")
        results["facebook"] = False
    print(f"[REEL] Facebook: {'✅' if results['facebook'] else '❌'}")
    time.sleep(3)

    try:
        results["instagram"] = post_reel_instagram(video_path, ig_caption)
    except Exception as e:
        print(f"[REEL][IG] Exception: {e}")
        results["instagram"] = False
    print(f"[REEL] Instagram Reel: {'✅' if results['instagram'] else '❌'}")

    try:
        results["youtube"] = post_video_youtube(
            video_path, title, price, discount, affiliate_link, hashtags)
    except Exception as e:
        print(f"[REEL][YT] Exception: {e}")
        results["youtube"] = False
    print(f"[REEL] YouTube Shorts: {'✅' if results.get('youtube') else '❌'}")

    try:
        os.unlink(video_path)
    except Exception:
        pass

    print(
        f"[REEL] ===== Done: "
        f"TG={results['telegram']} "
        f"FB={results['facebook']} "
        f"IG={results['instagram']} "
        f"YT={results.get('youtube')} ====="
    )
    return results


if __name__ == "__main__":
    post_daily_reel()
