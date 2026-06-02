"""
Daily Reel Bot — Creates a high-quality 3D-animated 30-second vertical product reel
with background music, SEO-optimised captions, and posts to Instagram, Facebook,
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

import bot

# ─── YouTube credentials ──────────────────────────────────────────────────────
YOUTUBE_CHANNEL_ID    = "UCtsNT0iG_1nsFW9JGqwA_NQ"
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

W, H = 1080, 1920   # 9:16 vertical

# ─── Palette ─────────────────────────────────────────────────────────────────
C_BG1   = (6,   4,  22)     # deep space black
C_BG2   = (18,  8,  52)     # dark violet
C_NEON  = (255, 40, 100)    # hot neon pink
C_GOLD  = (255, 195,  0)    # bright gold
C_CYAN  = (0,  220, 255)    # electric cyan
C_PURPLE= (160, 40, 255)    # vivid purple
C_WHITE = (255, 255, 255)
C_LIME  = (80,  255, 120)   # neon green


# ─── Font loader ─────────────────────────────────────────────────────────────
def load_font(size, bold=False):
    paths = (
        ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSans.ttf"]
    )
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ─── Drawing helpers ──────────────────────────────────────────────────────────
def gradient_bg(draw, w, h, top, bot):
    for y in range(h):
        t = y / h
        r = int(top[0] + t * (bot[0] - top[0]))
        g = int(top[1] + t * (bot[1] - top[1]))
        b = int(top[2] + t * (bot[2] - top[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_grid_lines(draw, w, h, color=(40, 20, 90), spacing=90):
    """Perspective-style grid lines for 3D floor effect."""
    # Horizontal lines (converge toward top)
    for i in range(10):
        y = h // 2 + i * spacing
        if y < h:
            draw.line([(0, y), (w, y)], fill=color, width=1)
    # Vertical lines (converge to vanishing point at top-center)
    vp_x = w // 2
    vp_y = h // 3
    for x in range(0, w + 1, spacing):
        draw.line([(vp_x, vp_y), (x, h)], fill=color, width=1)


def draw_hexagons(draw, seed=42):
    """Scattered glowing hex shapes for tech/3D feel."""
    rng = random.Random(seed)
    colors = [C_NEON, C_CYAN, C_PURPLE, C_GOLD, C_LIME]
    for _ in range(12):
        cx = rng.randint(0, W)
        cy = rng.randint(0, H // 2)
        r  = rng.randint(18, 55)
        col = rng.choice(colors)
        pts = [(cx + r * math.cos(math.radians(60 * i - 30)),
                cy + r * math.sin(math.radians(60 * i - 30))) for i in range(6)]
        draw.polygon(pts, outline=col)


def draw_stars(draw, count=100, seed=1):
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, W)
        y = rng.randint(0, H * 2 // 3)
        r = rng.choice([1, 1, 2, 2, 3])
        b = rng.randint(160, 255)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, b))


def neon_text(draw, xy, text, font, fill, glow_color=None, anchor="mm"):
    """Text with a subtle outer glow shadow for neon feel."""
    gc = glow_color or fill
    x, y = xy
    for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2),(0,-3),(0,3),(-3,0),(3,0)]:
        draw.text((x+dx, y+dy), text, font=font, fill=(*gc[:3], 80), anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def pill_badge(draw, cx, cy, text, font, bg, fg):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 40, 20
    x0, y0 = cx - tw//2 - px, cy - th//2 - py
    x1, y1 = cx + tw//2 + px, cy + th//2 + py
    # Shadow
    draw.rounded_rectangle([x0+4, y0+4, x1+4, y1+4], radius=50, fill=(0,0,0))
    # Background
    draw.rounded_rectangle([x0, y0, x1, y1], radius=50, fill=bg)
    # Highlight stripe
    draw.rounded_rectangle([x0+2, y0+2, x1-2, y0+18], radius=50, fill=(*C_WHITE, 40))
    draw.text((cx, cy), text, font=font, fill=fg, anchor="mm")
    return y1


def glowing_border(draw, x0, y0, x1, y1, color, radius=20):
    """Multiple outline passes to fake a glow."""
    for off, alpha in [(8, 30), (5, 60), (3, 100), (1, 200)]:
        c = (*color, alpha)
        # PIL doesn't support alpha in rounded_rectangle outline directly,
        # so we approximate with fading color
        faded = tuple(max(0, int(v * alpha / 255)) for v in color[:3])
        draw.rounded_rectangle([x0-off, y0-off, x1+off, y1+off],
                                radius=radius+off, outline=faded, width=2)


def paste_product_3d(canvas, image_url, box_y0, box_y1):
    """Product image with glowing border + subtle reflection below."""
    try:
        import io
        resp = requests.get(image_url, headers=bot.HEADERS, timeout=15)
        prod = Image.open(io.BytesIO(resp.content)).convert("RGBA")

        max_w = W - 100
        max_h = box_y1 - box_y0 - 30
        prod.thumbnail((max_w, max_h), Image.LANCZOS)

        # White card behind product
        card_pad = 18
        card = Image.new("RGB", (prod.width + card_pad*2, prod.height + card_pad*2),
                          (255, 255, 255))
        if prod.mode == "RGBA":
            card.paste(prod, (card_pad, card_pad), mask=prod)
        else:
            card.paste(prod, (card_pad, card_pad))

        # Reflection (flipped, faded)
        ref_h = card.height // 3
        ref = card.crop((0, card.height - ref_h, card.width, card.height))
        ref = ref.transpose(Image.FLIP_TOP_BOTTOM)
        ref = ref.filter(ImageFilter.GaussianBlur(3))
        enhancer = ImageEnhance.Brightness(ref)
        ref = enhancer.enhance(0.25)
        alpha = Image.new("L", ref.size)
        for i in range(ref_h):
            val = int(60 * (1 - i / ref_h))
            alpha.paste(val, (0, i, ref.width, i+1))
        ref.putalpha(alpha)

        cx = (W - card.width) // 2
        cy = box_y0 + (box_y1 - box_y0 - card.height) // 2

        # Paste reflection below
        ref_pos = (cx, cy + card.height + 4)
        if ref_pos[1] + ref.height < H:
            canvas.paste(ref, ref_pos, mask=ref)

        canvas.paste(card, (cx, cy))

        # Glowing border drawn on canvas draw
        d = ImageDraw.Draw(canvas)
        glowing_border(d, cx, cy, cx + card.width, cy + card.height,
                        C_CYAN, radius=14)

        return True
    except Exception as e:
        print(f"[REEL] Product image error: {e}")
        return False


# ─── Main frame builder ───────────────────────────────────────────────────────
def build_frame(title, price, discount, image_url, short_link):
    img  = Image.new("RGB", (W, H), C_BG1)
    draw = ImageDraw.Draw(img)

    # ── Background ────────────────────────────────────────────────────────
    gradient_bg(draw, W, H, C_BG1, C_BG2)
    draw_grid_lines(draw, W, H, color=(30, 15, 65), spacing=80)
    draw_stars(draw, count=120)
    draw_hexagons(draw)

    # ── Glowing corner accents ────────────────────────────────────────────
    for corner_pts in [[(0,0),(180,0),(0,180)], [(W,0),(W-180,0),(W,180)],
                        [(0,H),(180,H),(0,H-180)], [(W,H),(W-180,H),(W,H-180)]]:
        draw.polygon(corner_pts, fill=(80, 0, 180, 30))

    # ── Top banner (gradient neon) ────────────────────────────────────────
    gradient_bg(draw, W, 148, (160, 0, 80), (100, 0, 200))
    f_banner = load_font(50, bold=True)
    neon_text(draw, (W//2, 74), "🔥  BAZAAR BUDDY LOOT DEALS  🔥",
              f_banner, C_WHITE, C_NEON)
    draw.rectangle([0, 148, W, 154], fill=C_GOLD)

    # ── Product image ─────────────────────────────────────────────────────
    IMG_TOP, IMG_BOT = 162, 1000
    paste_product_3d(img, image_url, IMG_TOP, IMG_BOT)
    draw = ImageDraw.Draw(img)  # refresh after paste

    # ── Category badge (top-right of image) ───────────────────────────────
    f_small = load_font(28, bold=True)
    pill_badge(draw, W - 90, IMG_TOP + 40, "✨ DEAL", f_small, C_GOLD, (10,5,20))

    # ── Bottom info panel ─────────────────────────────────────────────────
    gradient_bg(draw, W, H - 1010, (14, 8, 45), (6, 4, 22))
    # Separator line with cyan glow
    for off, col in [(0, C_CYAN), (1, (0,150,180)), (2, (0,80,120))]:
        draw.rectangle([0, 1010+off, W, 1013+off], fill=col)

    y = 1030

    # Title
    f_title = load_font(42, bold=True)
    wrapped = textwrap.wrap(title[:150], width=24)
    for line in wrapped[:3]:
        neon_text(draw, (W//2, y + 24), line, f_title, C_WHITE, C_CYAN)
        y += 58
    y += 14

    # Discount badge
    if discount:
        f_disc = load_font(52, bold=True)
        y = pill_badge(draw, W//2, y + 46, f"🔥 {discount} OFF  —  HOT DEAL!", f_disc,
                        C_NEON, C_WHITE) + 22

    # Price
    if price:
        f_price = load_font(62, bold=True)
        neon_text(draw, (W//2, y + 20), f"💰 {price}", f_price, C_GOLD, C_GOLD)
        y += 82

    # Affiliate short link box
    f_link = load_font(35)
    link_y = max(y + 18, 1620)
    draw.rounded_rectangle([36, link_y - 28, W - 36, link_y + 52],
                            radius=18, fill=(0, 30, 70))
    draw.rounded_rectangle([36, link_y - 28, W - 36, link_y + 52],
                            radius=18, outline=C_CYAN, width=2)
    neon_text(draw, (W//2, link_y + 12), f"🛒 {short_link}",
              f_link, C_CYAN, C_CYAN)

    # CTA button
    f_cta = load_font(48, bold=True)
    cta_y = link_y + 110
    pill_badge(draw, W//2, cta_y, "👆  TAP LINK TO BUY NOW  👆", f_cta, C_GOLD, (8,4,20))

    # Branding
    f_brand = load_font(30)
    neon_text(draw, (W//2, 1875), "@BazaarBuddyLootDeals  •  Amazon India Deals",
              f_brand, (180, 140, 255), C_PURPLE)

    return img


# ─── Background music ─────────────────────────────────────────────────────────
MUSIC_URLS = [
    "https://cdn.pixabay.com/download/audio/2023/10/26/audio_e2062a7f17.mp3",
    "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3",
    "https://cdn.pixabay.com/download/audio/2023/06/07/audio_0b7fae6ccd.mp3",
    "https://cdn.pixabay.com/download/audio/2022/08/23/audio_2dde668d05.mp3",
]

def download_music():
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
            print(f"[REEL] Music URL failed: {e}")
    return None


def generate_music_ffmpeg(duration=30):
    """Upbeat synthetic background track using layered sine oscillators."""
    out = tempfile.mktemp(suffix=".mp3")
    expr = (
        "0.22*sin(2*PI*80*t)"
        "+0.18*sin(2*PI*160*t)"
        "+0.15*sin(2*PI*320*(1+0.02*sin(2*PI*2*t))*t)"
        "+0.10*sin(2*PI*640*t)"
        "+0.08*sin(2*PI*1280*t*((floor(t*4)%2)+1))"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':s=44100:d={duration}",
        "-af", (f"afade=t=in:st=0:d=1.5,"
                f"afade=t=out:st={max(1,duration-2)}:d=2,"
                f"highpass=f=60,lowpass=f=8000"),
        "-q:a", "4", out,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        print("[REEL] Synthetic music generated")
        return out
    return None


# ─── Animated video creation ──────────────────────────────────────────────────
def create_reel_video(title, price, discount, image_url, short_link, duration=30):
    """
    Beautiful 3D-animated vertical short:
    - Ken Burns zoom-pan on the product poster
    - Neon text overlays fade/slide in at key timestamps
    - Background music (downloaded or synthesised)
    """
    print("[REEL] Building poster frame...")
    frame_img  = build_frame(title, price, discount, image_url, short_link)
    frame_path = tempfile.mktemp(suffix=".jpg")
    frame_img.save(frame_path, quality=97)
    print("[REEL] Frame saved. Downloading music...")

    music_path = download_music()
    if not music_path:
        music_path = generate_music_ffmpeg(duration)

    out_path = tempfile.mktemp(suffix=".mp4")

    # Ken Burns: slow zoom in from 1.0 to 1.10, gentle drift
    fps   = 30
    total = duration * fps
    zoom_filter = (
        f"zoompan=z='min(1.0+0.10*on/{total},1.10)'"
        f":x='iw/2-(iw/zoom/2)+sin(on/{fps}*0.3)*12'"
        f":y='ih/2-(ih/zoom/2)'"
        f":d={total}:s={W}x{H}:fps={fps}"
    )

    # Defensive text sanitisation (no quotes / special chars in drawtext)
    def safe(s): return s[:60].replace("'","").replace(":","").replace("\\","")

    price_s    = safe(price or "")
    disc_s     = safe(discount or "")
    short_s    = safe(short_link or "")
    fontfile   = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    if not os.path.exists(fontfile):
        fontfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    fade_in  = "alpha='if(lt(t,{s}),0,if(lt(t,{e}),(t-{s})/({e}-{s}),1))'"

    # Text 1 — DEAL ALERT, fades in t=0→1.5
    t1 = ("drawtext=text='🔥 HOT DEAL ALERT 🔥'"
          ":fontsize=58:fontcolor=0xFFFFFF"
          ":x=(w-tw)/2:y=45"
          f":enable='gte(t,0)':{fade_in.format(s=0,e=1.5)}"
          ":shadowcolor=0xFF2864:shadowx=3:shadowy=3"
          f":fontfile={fontfile}")

    # Text 2 — Price, fades in t=2→4
    texts = [t1]
    if price_s:
        t2 = (f"drawtext=text='{price_s}'"
              ":fontsize=72:fontcolor=0xFFD700"
              ":x=(w-tw)/2:y=h-290"
              f":enable='gte(t,2)':{fade_in.format(s=2,e=4)}"
              ":shadowcolor=0x000000:shadowx=4:shadowy=4"
              f":fontfile={fontfile}")
        texts.append(t2)

    # Text 3 — Discount, fades in t=4→6
    if disc_s:
        t3 = (f"drawtext=text='{disc_s} OFF - LIMITED TIME'"
              ":fontsize=50:fontcolor=0xFF2864"
              ":x=(w-tw)/2:y=h-210"
              f":enable='gte(t,4)':{fade_in.format(s=4,e=6)}"
              ":shadowcolor=0x000000:shadowx=2:shadowy=2"
              f":fontfile={fontfile}")
        texts.append(t3)

    # Text 4 — CTA link, fades in t=7→9
    if short_s:
        t4 = (f"drawtext=text='BUY NOW {short_s}'"
              ":fontsize=38:fontcolor=0x00DCFF"
              ":x=(w-tw)/2:y=h-135"
              f":enable='gte(t,7)':{fade_in.format(s=7,e=9)}"
              ":shadowcolor=0x000000:shadowx=2:shadowy=2"
              f":fontfile={fontfile}")
        texts.append(t4)

    vf = zoom_filter + "," + ",".join(texts)

    if music_path and os.path.exists(music_path):
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-i", music_path,
            "-filter_complex",
                f"[0:v]{vf}[vout];"
                f"[1:a]aloop=loop=-1:size=2e+09,"
                f"atrim=0:{duration},"
                f"afade=t=in:st=0:d=1.5,"
                f"afade=t=out:st={max(1,duration-2)}:d=2,"
                f"volume=0.55[aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-r", str(fps),
            "-movflags", "+faststart",
            out_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-filter_complex", f"[0:v]{vf}[vout]",
            "-map", "[vout]",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-movflags", "+faststart",
            out_path,
        ]

    print("[REEL] Rendering animated video (~30s)...")
    result = subprocess.run(cmd, capture_output=True)
    for p in [frame_path, music_path]:
        try:
            if p and os.path.exists(p): os.unlink(p)
        except Exception:
            pass

    if result.returncode != 0:
        print("[REEL] ffmpeg error:", result.stderr.decode()[-800:])
        return None

    size_kb = os.path.getsize(out_path) // 1024
    print(f"[REEL] ✅ Video ready: {out_path}  ({size_kb} KB)")
    return out_path


# ─── SEO caption builder ─────────────────────────────────────────────────────
def build_seo_caption(title, price, discount, rating, reviews, link, platform="instagram"):
    deal  = f"🔥 {discount} OFF — Limited Time!" if discount else "🔥 Hot Deal!"
    p_ln  = f"💰 Only {price} on Amazon India" if price else ""
    r_ln  = f"⭐ {rating}/5 • {reviews} Reviews" if rating and reviews else ""
    tags  = (
        "#Shorts #AmazonIndia #LootDeals #AmazonDeals #OnlineShopping "
        "#TechDeals #IndiaDeals #BestDeals #BuyNow #DealAlert "
        "#DiscountDeals #BazaarBuddy #AmazonSale #FlashSale "
        "#DealOfTheDay #SaleAlert #ShoppingDeals #GrabNow"
    )
    if platform == "telegram":
        return (
            f"🛒 <b>BUY NOW</b> 👉 <a href='{link}'>ORDER HERE ← CLICK</a>\n\n"
            f"🔥 <b>{title}</b>\n\n{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + f"\n✅ Amazon India Affiliate Deal\n🔗 {link}"
        )
    if platform == "youtube":
        return (
            f"🛒 BUY NOW 👉 {link}\n\n"
            f"🔥 {title}\n\n{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + f"\n✅ Amazon India Affiliate Deal (tag: dattatrey07-21)\n"
            f"📌 Tap the link above to buy!\n\n"
            f"─────────────────────\n"
            f"🔔 SUBSCRIBE → @BazaarBuddyLootDeals for daily deals!\n"
            f"─────────────────────\n\n"
            + tags
        )
    # Instagram / Facebook — link not clickable in caption, but visible
    return (
        f"🛒 BUY NOW 👉 {link}\n\n"
        f"🔥 {title}\n\n{deal}\n"
        + (f"{p_ln}\n" if p_ln else "")
        + (f"{r_ln}\n" if r_ln else "")
        + f"\n👆 Link in caption / bio to order!\n\n"
        + tags
    )


def build_youtube_title(title, price, discount):
    disc = f"{discount} OFF | " if discount else ""
    pr   = f" at {price}" if price else ""
    return f"🔥 {disc}{title[:60]}{pr} | Amazon India Deal #Shorts"[:100]


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
    token, ig_id = bot.FB_PAGE_TOKEN, bot.IG_USER_ID
    file_size = os.path.getsize(video_path)

    r = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media",
        params={"media_type":"REELS","upload_type":"resumable",
                "caption":caption,"share_to_feed":"true","access_token":token},
        timeout=30,
    )
    data = r.json()
    if "id" not in data:
        print("[REEL][IG] Container error:", data); return False
    container_id = data["id"]
    upload_url   = data.get("uri")
    if not upload_url:
        print("[REEL][IG] No URI"); return False

    with open(video_path, "rb") as f:
        video_bytes = f.read()
    up = requests.post(upload_url,
        headers={"Authorization":f"OAuth {token}","offset":"0","file_size":str(file_size)},
        data=video_bytes, timeout=180)
    if up.status_code not in (200,201):
        print("[REEL][IG] Upload error:", up.text[:300]); return False

    print("[REEL][IG] Waiting for processing...")
    for i in range(18):
        time.sleep(10)
        st = requests.get(f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields":"status_code","access_token":token},timeout=20).json()
        status = st.get("status_code","")
        print(f"[REEL][IG] {i+1}/18: {status}")
        if status == "FINISHED": break
        if status == "ERROR": print("[REEL][IG] Error:", st); return False
    else:
        print("[REEL][IG] Timeout"); return False

    pub = requests.post(f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
        params={"creation_id":container_id,"access_token":token},timeout=30)
    ok = "id" in pub.json()
    if not ok: print("[REEL][IG] Publish error:", pub.json())
    return ok


def get_youtube_access_token():
    if not YOUTUBE_REFRESH_TOKEN: return None
    try:
        resp = requests.post("https://oauth2.googleapis.com/token",
            data={"client_id":YOUTUBE_CLIENT_ID,"client_secret":YOUTUBE_CLIENT_SECRET,
                  "refresh_token":YOUTUBE_REFRESH_TOKEN,"grant_type":"refresh_token"},
            timeout=15)
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[REEL][YT] Token error: {e}"); return None


def post_video_youtube(video_path, title, price, discount, affiliate_link, hashtags):
    access_token = get_youtube_access_token()
    if not access_token:
        print("[REEL][YT] No access token"); return False

    # Always use the clean affiliate link (no viglink)
    clean_link = bot.clean_affiliate_url(affiliate_link)
    short_link = bot.shorten_url(clean_link)
    yt_title   = build_youtube_title(title, price, discount)
    yt_desc    = build_seo_caption(title, price, discount, None, None,
                                    short_link, platform="youtube")
    try:
        file_size = os.path.getsize(video_path)
        init = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status",
            headers={"Authorization":f"Bearer {access_token}",
                     "Content-Type":"application/json",
                     "X-Upload-Content-Type":"video/mp4",
                     "X-Upload-Content-Length":str(file_size)},
            json={"snippet":{"title":yt_title,"description":yt_desc,
                              "tags":["AmazonDeals","LootDeals","AmazonIndia",
                                      "Shorts","IndiaShopping","BazaarBuddy",
                                      "OnlineShopping","DealAlert","FlashSale"],
                              "categoryId":"26","defaultLanguage":"en"},
                  "status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}},
            timeout=30)
        if init.status_code not in (200,201):
            print(f"[REEL][YT] Init failed {init.status_code}"); return False
        upload_url = init.headers.get("Location")
        if not upload_url:
            print("[REEL][YT] No upload URL"); return False
        with open(video_path,"rb") as f:
            video_bytes = f.read()
        up = requests.put(upload_url,
            headers={"Content-Type":"video/mp4","Content-Length":str(file_size)},
            data=video_bytes, timeout=180)
        if up.status_code in (200,201):
            vid_id = up.json().get("id","")
            print(f"[REEL][YT] ✅ https://youtube.com/shorts/{vid_id}")
            return True
        print(f"[REEL][YT] Upload failed {up.status_code}"); return False
    except Exception as e:
        print(f"[REEL][YT] Exception: {e}"); return False


# ─── Main ─────────────────────────────────────────────────────────────────────
def post_daily_reel():
    print("[REEL] ===== Daily Reel Job Started =====")

    products = bot.scrape_products()
    if not products:
        print("[REEL] No products — aborting."); return

    title, price, affiliate_link, image_url, base_link = random.choice(products)

    # Ensure clean affiliate link (no viglink wrappers)
    affiliate_link = bot.clean_affiliate_url(affiliate_link)

    rating, reviews, seller, original_price, discount = bot.get_product_details(base_link)
    short_link = bot.shorten_url(affiliate_link)
    hashtags   = bot.generate_hashtags(title)

    print(f"[REEL] Product : {title[:80]}")
    print(f"[REEL] Link    : {affiliate_link}")
    print(f"[REEL] Short   : {short_link}")
    print(f"[REEL] Price   : {price}  |  Discount: {discount}")

    tg_cap = build_seo_caption(title, price, discount, rating, reviews,
                                affiliate_link, platform="telegram")
    ig_cap = build_seo_caption(title, price, discount, rating, reviews,
                                short_link, platform="instagram")

    video_path = create_reel_video(title, price, discount, image_url, short_link)
    if not video_path:
        print("[REEL] Video creation failed — aborting."); return

    results = {}

    try:
        results["telegram"] = post_video_telegram(video_path, tg_cap)
    except Exception as e:
        print(f"[REEL][TG] {e}"); results["telegram"] = False
    print(f"[REEL] Telegram  : {'✅' if results['telegram'] else '❌'}")
    time.sleep(3)

    try:
        results["facebook"] = post_video_facebook(video_path, ig_cap)
    except Exception as e:
        print(f"[REEL][FB] {e}"); results["facebook"] = False
    print(f"[REEL] Facebook  : {'✅' if results['facebook'] else '❌'}")
    time.sleep(3)

    try:
        results["instagram"] = post_reel_instagram(video_path, ig_cap)
    except Exception as e:
        print(f"[REEL][IG] {e}"); results["instagram"] = False
    print(f"[REEL] Instagram : {'✅' if results['instagram'] else '❌'}")

    try:
        results["youtube"] = post_video_youtube(
            video_path, title, price, discount, affiliate_link, hashtags)
    except Exception as e:
        print(f"[REEL][YT] {e}"); results["youtube"] = False
    print(f"[REEL] YouTube   : {'✅' if results.get('youtube') else '❌'}")

    try:
        os.unlink(video_path)
    except Exception:
        pass

    print(f"[REEL] ===== Done: TG={results['telegram']} FB={results['facebook']} "
          f"IG={results['instagram']} YT={results.get('youtube')} =====")
    return results


if __name__ == "__main__":
    post_daily_reel()
