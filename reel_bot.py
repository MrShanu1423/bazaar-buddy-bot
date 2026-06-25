"""
Bazaar Buddy — Daily Reel Bot v4 (Professional Edition)
========================================================
Format  : 1080×1920  9:16  30 FPS  H.264  AAC-48kHz
Duration: 20 seconds
Design  : Amazon-style professional ad (black / orange / gold)
Features:
  • Image proxy (images.weserv.nl) bypasses Amazon CDN IP blocks
  • 5-scene animated structure per master prompt
  • ElevenLabs AI voiceover (English/Hindi blend)
  • Layered background music + SFX
  • 3-level ffmpeg fallback so video ALWAYS renders
  • Telegram report at end
"""

import io
import json
import math
import os
import random
import subprocess
import tempfile
import textwrap
import time
import urllib.parse

import requests
from PIL import (Image, ImageDraw, ImageEnhance, ImageFilter,
                 ImageFont, ImageOps)

import bot

# ─── Credentials ──────────────────────────────────────────────────────────────
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
ELEVENLABS_API_KEY    = os.environ.get("ELEVENLABS_API_KEY", "")

if not YOUTUBE_REFRESH_TOKEN and os.path.exists("youtube_token.json"):
    try:
        with open("youtube_token.json") as _f:
            _tok = json.load(_f)
            YOUTUBE_REFRESH_TOKEN = _tok.get("refresh_token", "")
            YOUTUBE_CLIENT_ID     = YOUTUBE_CLIENT_ID or _tok.get("client_id", "")
            YOUTUBE_CLIENT_SECRET = YOUTUBE_CLIENT_SECRET or _tok.get("client_secret", "")
    except Exception:
        pass

# ─── Canvas ───────────────────────────────────────────────────────────────────
W, H   = 1080, 1920
FPS    = 30
DUR    = 20          # seconds — sweet spot for affiliate reels

# ─── Color palette (Amazon-style) ────────────────────────────────────────────
C_BLACK  = (8,   8,  12)
C_DARK   = (18,  18, 28)
C_ORANGE = (255, 153,  0)   # Amazon orange
C_GOLD   = (255, 200, 10)
C_WHITE  = (255, 255, 255)
C_GREY   = (180, 180, 190)
C_GREEN  = ( 0,  185,  80)
C_CYAN   = ( 0,  210, 255)
C_RED    = (220,  40,  40)


# ═══════════════════════════════════════════════════════════════════════════════
# FONTS
# ═══════════════════════════════════════════════════════════════════════════════
def load_font(size, bold=False):
    candidates = (
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
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

BOLD_TTF = next(
    (p for p in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ] if os.path.exists(p)), ""
)


# ═══════════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def grad_rect(draw, x0, y0, x1, y1, top, bot_col):
    h = max(y1 - y0, 1)
    for dy in range(h):
        t = dy / h
        r = int(top[0] + t * (bot_col[0] - top[0]))
        g = int(top[1] + t * (bot_col[1] - top[1]))
        b = int(top[2] + t * (bot_col[2] - top[2]))
        draw.line([(x0, y0 + dy), (x1, y0 + dy)], fill=(r, g, b))


def shadow_text(draw, xy, text, font, fill, shadow=(0,0,0), anchor="mm", offset=3):
    x, y = xy
    draw.text((x+offset, y+offset), text, font=font, fill=shadow, anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def pill(draw, cx, cy, text, font, bg, fg, px=32, py=14):
    """Rounded pill badge."""
    try:
        bb = draw.textbbox((0,0), text, font=font)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        x0, y0 = cx-tw//2-px, cy-th//2-py
        x1, y1 = cx+tw//2+px, cy+th//2+py
        draw.rounded_rectangle([x0+3, y0+3, x1+3, y1+3], radius=40, fill=(0,0,0))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=40, fill=bg)
        draw.text((cx, cy), text, font=font, fill=fg, anchor="mm")
        return y1
    except Exception:
        return cy + 55


def glow_rect(draw, x0, y0, x1, y1, color, radius=16):
    for off in [8, 5, 2]:
        c = tuple(max(0, v * off // 9) for v in color[:3])
        draw.rounded_rectangle([x0-off, y0-off, x1+off, y1+off],
                                radius=radius+off, outline=c, width=2)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=color, width=3)


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE DOWNLOAD — with proxy fallback to bypass Amazon CDN blocks
# ═══════════════════════════════════════════════════════════════════════════════
IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.amazon.in/",
    "sec-fetch-dest": "image",
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "cross-site",
}


def _url_variants(url):
    """Generate alternate size variants of an Amazon image URL."""
    variants = [url]
    # Strip size modifier and try clean URL
    import re
    clean = re.sub(r'\._[A-Z]{2,3}\d*_\.', '.', url)
    if clean != url:
        variants.append(clean)
    # Common size replacements
    for size in ["_SL1000_", "_SL800_", "_AC_SX522_", "_AC_"]:
        v = re.sub(r'_S[LX]\d+_', size, url)
        variants.append(v)
    return list(dict.fromkeys(variants))   # deduplicate, preserve order


def download_product_image(image_url):
    """
    Download product image with three strategies:
    1. Direct download with browser headers
    2. images.weserv.nl image proxy (bypasses IP blocks)
    3. Return None → caller creates placeholder
    """
    if not image_url:
        return None

    # Strategy 1 — direct with browser headers + variant URLs
    for url in _url_variants(image_url):
        try:
            r = requests.get(url, headers=IMG_HEADERS, timeout=20)
            if r.status_code == 200 and len(r.content) > 3000:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                print(f"[IMAGE] Direct download OK ({len(r.content)//1024} KB)")
                return img
        except Exception as e:
            print(f"[IMAGE] Direct fail: {e}")

    # Strategy 2 — image proxy (weserv.nl)
    try:
        # weserv.nl accepts URL without the protocol prefix
        stripped = image_url.replace("https://", "").replace("http://", "")
        proxy_url = f"https://images.weserv.nl/?url={urllib.parse.quote(stripped, safe='')}&w=1000&output=jpg"
        r = requests.get(proxy_url, timeout=25,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 3000:
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            print(f"[IMAGE] Proxy download OK ({len(r.content)//1024} KB)")
            return img
    except Exception as e:
        print(f"[IMAGE] Proxy fail: {e}")

    print("[IMAGE] All download attempts failed — will use placeholder")
    return None


def make_placeholder(title):
    """Create a stylised product image placeholder."""
    img = Image.new("RGB", (900, 700), (25, 25, 40))
    draw = ImageDraw.Draw(img)
    # Gradient bg
    grad_rect(draw, 0, 0, 900, 700, (30, 20, 60), (15, 10, 35))
    # Box outline
    draw.rounded_rectangle([30, 30, 870, 670], radius=30,
                            outline=C_ORANGE, width=4)
    # Emoji icon
    f_big = load_font(120, bold=True)
    draw.text((450, 280), "🛍️", font=f_big, fill=C_ORANGE, anchor="mm")
    # Title text (wrapped)
    f_title = load_font(36)
    words = textwrap.wrap(title[:80], width=22)
    y = 400
    for line in words[:3]:
        draw.text((450, y), line, font=f_title, fill=C_WHITE, anchor="mm")
        y += 50
    return img.convert("RGBA")


# ═══════════════════════════════════════════════════════════════════════════════
# FRAME BUILDER  —  Professional Amazon-ad style
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Layout (1920px tall):
#   0 – 110   : Top banner  (orange gradient)
#  110 – 980  : Product image  [870px — 45% of frame]
#  980 – 1220 : WHY BUY features  [4 pills × 60px]
# 1220 – 1450 : Price + discount section
# 1450 – 1720 : Link + CTA
# 1720 – 1920 : Footer / subscribe strip

def build_frame(title, price, discount, prod_img_pil,
                short_link, features=None, rating=None, reviews=None):
    canvas = Image.new("RGB", (W, H), C_BLACK)
    draw   = ImageDraw.Draw(canvas)

    # ── Full background ───────────────────────────────────────────────────
    grad_rect(draw, 0, 0, W, H, (12, 12, 20), (6, 6, 14))

    # Subtle diagonal lines texture
    for i in range(0, W+H, 55):
        draw.line([(i, 0), (0, i)], fill=(20, 20, 35), width=1)

    # ── TOP BANNER ────────────────────────────────────────────────────────
    grad_rect(draw, 0, 0, W, 112, (200, 80, 0), (230, 120, 0))
    draw.rectangle([0, 0, W, 4], fill=C_GOLD)
    draw.rectangle([0, 108, W, 112], fill=C_GOLD)

    f_brand = load_font(44, bold=True)
    shadow_text(draw, (W//2, 56),
                "🔥  BAZAAR BUDDY LOOT DEALS  🔥",
                f_brand, C_WHITE, (80, 30, 0), offset=3)

    # ── PRODUCT IMAGE ZONE (110–980) ──────────────────────────────────────
    IMG_Y0, IMG_Y1 = 112, 980
    IMG_W = W - 40       # near full width
    IMG_H = IMG_Y1 - IMG_Y0 - 10

    # White card background
    card_x0 = (W - IMG_W) // 2
    card_y0 = IMG_Y0 + 5
    draw.rounded_rectangle([card_x0, card_y0, card_x0+IMG_W, card_y0+IMG_H],
                            radius=22, fill=(250, 250, 255))

    # Product image — fill card
    prod = prod_img_pil or make_placeholder(title)
    # Scale to fill card keeping aspect ratio
    prod_rgb = prod.convert("RGBA")
    prod_rgb.thumbnail((IMG_W - 40, IMG_H - 40), Image.LANCZOS)

    px = card_x0 + (IMG_W - prod_rgb.width) // 2
    py = card_y0 + (IMG_H - prod_rgb.height) // 2

    # White canvas under image (handles transparent PNGs)
    bg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bg_layer.paste(prod_rgb, (px, py), mask=prod_rgb)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), bg_layer).convert("RGB")
    draw   = ImageDraw.Draw(canvas)

    # Orange glow border around card
    glow_rect(draw, card_x0, card_y0, card_x0+IMG_W, card_y0+IMG_H,
              C_ORANGE, radius=22)

    # DEAL badge (top-right of card)
    if discount:
        f_badge = load_font(30, bold=True)
        pill(draw, W - 70, IMG_Y0 + 46,
             f"🏷 {discount} OFF", f_badge, C_RED, C_WHITE, px=20, py=10)

    # Rating stars (top-left of card)
    if rating:
        try:
            stars = min(5, max(0, int(float(rating))))
            star_str = "★" * stars + "☆" * (5-stars) + f"  {rating}"
            f_star = load_font(28, bold=True)
            draw.rounded_rectangle([card_x0+10, card_y0+10,
                                    card_x0+10+230, card_y0+10+44],
                                    radius=8, fill=(255, 200, 0))
            draw.text((card_x0+22, card_y0+16), star_str,
                      font=f_star, fill=(20,20,20))
        except Exception:
            pass

    # ── WHY BUY — Feature pills (980–1220) ───────────────────────────────
    FEAT_Y0 = 988
    feat_icons = ["⚡", "✅", "🔥", "💡"]
    if features:
        f_feat = load_font(28)
        fy = FEAT_Y0
        for i, feat in enumerate(features[:4]):
            icon = feat_icons[i % 4]
            # Pill background
            draw.rounded_rectangle([14, fy, W-14, fy+50],
                                    radius=14, fill=(24, 24, 40))
            # Left accent
            draw.rounded_rectangle([14, fy, 20, fy+50],
                                    radius=4, fill=C_ORANGE)
            draw.text((44, fy+12), f"{icon}  {feat}",
                      font=f_feat, fill=C_WHITE)
            fy += 56
        PRICE_Y0 = fy + 8
    else:
        PRICE_Y0 = FEAT_Y0

    # ── PRICE + DISCOUNT (dynamic Y) ─────────────────────────────────────
    draw.rectangle([0, PRICE_Y0, W, PRICE_Y0+3], fill=C_ORANGE)
    y = PRICE_Y0 + 16

    # Product title
    f_title = load_font(38, bold=True)
    wrapped = textwrap.wrap(title[:140], width=26)
    for line in wrapped[:2]:
        shadow_text(draw, (W//2, y+22), line, f_title, C_WHITE, offset=2)
        y += 52
    y += 8

    # Price in big gold
    if price:
        f_price = load_font(66, bold=True)
        shadow_text(draw, (W//2, y+36), f"💰 {price}",
                    f_price, C_GOLD, (60, 50, 0), offset=4)
        y += 84

    # Discount pill
    if discount:
        f_disc = load_font(44, bold=True)
        y = pill(draw, W//2, y+36,
                 f"🔥 {discount} OFF — LIMITED TIME!",
                 f_disc, C_RED, C_WHITE) + 16

    # Reviews line
    if rating and reviews:
        f_rev = load_font(28)
        draw.text((W//2, y+16),
                  f"⭐ {rating}/5   •   {reviews} Reviews   •   Amazon India",
                  font=f_rev, fill=C_GREY, anchor="mm")
        y += 44

    # ── LINK + CTA ────────────────────────────────────────────────────────
    link_y = max(y + 20, H - 330)

    # Link box
    draw.rounded_rectangle([24, link_y, W-24, link_y+56],
                            radius=16, fill=(0, 28, 68))
    draw.rounded_rectangle([24, link_y, W-24, link_y+56],
                            radius=16, outline=C_CYAN, width=2)
    f_link = load_font(34)
    shadow_text(draw, (W//2, link_y+28), f"🛒  {short_link}",
                f_link, C_CYAN, offset=2)

    # CTA button
    f_cta = load_font(46, bold=True)
    pill(draw, W//2, link_y+110,
         "👆  TAP LINK TO BUY NOW  👆",
         f_cta, C_ORANGE, C_WHITE)

    # ── FOOTER STRIP ─────────────────────────────────────────────────────
    FT = H - 148
    draw.rectangle([0, FT, W, H], fill=(14, 14, 24))
    draw.rectangle([0, FT, W, FT+3], fill=C_ORANGE)

    f_sub = load_font(26, bold=True)
    f_fol = load_font(22)
    shadow_text(draw, (W//2, FT+28),
                "🔔 SUBSCRIBE  ▸  YouTube: @BazaarBuddyLootDeals",
                f_sub, C_GOLD, offset=2)
    shadow_text(draw, (W//2, FT+62),
                "❤️ Instagram: @bazaarbuddylootdeals  •  📢 t.me/BazaarBuddyLootDeals",
                f_fol, C_CYAN, offset=1)
    shadow_text(draw, (W//2, FT+96),
                "🛍️ Best Amazon India Deals  •  Daily  •  100% Free",
                f_fol, (200, 200, 220), offset=1)
    shadow_text(draw, (W//2, FT+126),
                "Amazon India Affiliate | dattatrey07-21",
                load_font(18), (100,100,110), offset=1)

    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
# ELEVENLABS VOICEOVER
# ═══════════════════════════════════════════════════════════════════════════════
EL_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"   # "Bella" — clear female voice

def build_voiceover_script(title, price, discount, features):
    """15-second voiceover script for the reel."""
    feat_line = ""
    if features:
        feat_line = ". ".join(features[:2]) + "."

    disc_line = f"Get {discount} off!" if discount else "At an amazing price!"
    price_line = f"Just {price} on Amazon India!" if price else "Available on Amazon India!"

    script = (
        f"Amazon deal alert! {title[:50]}. "
        f"{disc_line} {price_line} "
        f"{feat_line} "
        f"Tap the link to buy now. Subscribe for daily deals!"
    )
    return script[:400]


def generate_voiceover(script):
    """Call ElevenLabs TTS API. Returns mp3 path or None."""
    if not ELEVENLABS_API_KEY:
        print("[VO] No ElevenLabs API key — skipping voiceover")
        return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_ID}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": script,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.80,
                "style": 0.20,
                "use_speaker_boost": True,
            },
        }
        r = requests.post(url, json=payload, headers=headers, timeout=40)
        if r.status_code == 200 and len(r.content) > 2000:
            p = tempfile.mktemp(suffix=".mp3")
            with open(p, "wb") as f:
                f.write(r.content)
            print(f"[VO] ElevenLabs voiceover OK ({len(r.content)//1024} KB)")
            return p
        print(f"[VO] ElevenLabs error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[VO] ElevenLabs exception: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# MUSIC
# ═══════════════════════════════════════════════════════════════════════════════
MUSIC_URLS = [
    "https://cdn.pixabay.com/download/audio/2023/10/26/audio_e2062a7f17.mp3",
    "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3",
    "https://cdn.pixabay.com/download/audio/2023/06/07/audio_0b7fae6ccd.mp3",
    "https://cdn.pixabay.com/download/audio/2022/08/23/audio_2dde668d05.mp3",
    "https://cdn.pixabay.com/download/audio/2024/02/14/audio_fbfa035a6b.mp3",
    "https://cdn.pixabay.com/download/audio/2023/05/16/audio_1c47f2bab2.mp3",
    "https://cdn.pixabay.com/download/audio/2022/10/25/audio_0f2c24ead6.mp3",
    "https://cdn.pixabay.com/download/audio/2023/01/11/audio_84e5f3afe3.mp3",
    "https://cdn.pixabay.com/download/audio/2022/12/07/audio_95b85c6a12.mp3",
    "https://cdn.pixabay.com/download/audio/2021/11/15/audio_e7b7b0d6db.mp3",
    "https://cdn.pixabay.com/download/audio/2023/03/07/audio_84f18efaf6.mp3",
    "https://cdn.pixabay.com/download/audio/2022/03/24/audio_6bca92e5d4.mp3",
]


def download_music():
    order = random.sample(MUSIC_URLS, len(MUSIC_URLS))
    p = tempfile.mktemp(suffix=".mp3")
    for url in order:
        try:
            r = requests.get(url, timeout=22,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 15_000:
                with open(p, "wb") as f:
                    f.write(r.content)
                print(f"[MUSIC] OK ({len(r.content)//1024} KB)")
                return p
        except Exception:
            pass
    return None


def synth_music(duration=22):
    out = tempfile.mktemp(suffix=".mp3")
    bpm  = 128
    beat = 60 / bpm
    expr = (
        f"0.18*sin(2*PI*60*t)*exp(-8*mod(t,{beat:.4f}))"
        f"+0.16*sin(2*PI*110*t)"
        f"+0.13*sin(2*PI*330*(1+0.012*sin(2*PI*0.5*t))*t)"
        f"+0.09*sin(2*PI*660*t*((floor(t*2)%2)*0.5+0.75))"
        f"+0.05*sin(2*PI*1320*t)*sin(2*PI*4*t)"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':s=44100:d={duration}",
        "-af", (
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={duration-2}:d=2,"
            "highpass=f=50,lowpass=f=9000,volume=0.7"
        ),
        "-q:a", "4", out,
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=60)
    return out if res.returncode == 0 else None


def gen_ding():
    """Short cash-register ding SFX."""
    out = tempfile.mktemp(suffix=".mp3")
    expr = (
        "0.5*sin(2*PI*1400*t)*exp(-5*t)"
        "+0.3*sin(2*PI*1800*t)*exp(-7*t)"
        "+0.2*sin(2*PI*2200*t)*exp(-10*t)"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':s=44100:d=0.8",
        "-q:a", "5", out,
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return out if res.returncode == 0 else None


# ═══════════════════════════════════════════════════════════════════════════════
# VIDEO RENDERER — animated overlays + Ken Burns zoom
# ═══════════════════════════════════════════════════════════════════════════════
def _s(text, n=55):
    """Sanitise text for ffmpeg drawtext."""
    return (text or "")[:n].replace("'","").replace('"',"").replace("\\","").replace(":","")


def _fade(t0, t1):
    return f"alpha='if(lt(t,{t0}),0,if(lt(t,{t1}),(t-{t0})/({t1}-{t0}),1))'"


def render_video(frame_path, music_path, vo_path, ding_path,
                 title, price, discount, short_link, dur=DUR):
    out   = tempfile.mktemp(suffix=".mp4")
    total = dur * FPS

    # ── Ken Burns zoom (subtle, 1.0→1.08) ────────────────────────────────
    zoom_vf = (
        f"zoompan=z='min(1.0+0.08*on/{total},1.08)'"
        f":x='iw/2-(iw/zoom/2)'"
        f":y='ih/2-(ih/zoom/2)'"
        f":d={total}:s={W}x{H}:fps={FPS}"
    )

    # ── Text overlays — 5-scene structure ────────────────────────────────
    texts = []
    ff    = BOLD_TTF or ""

    def dt(text, fs, fc, x, y, t0, t1, sx=3, sy=3, sc="0x000000"):
        if not ff:
            return
        texts.append(
            f"drawtext=text='{text}'"
            f":fontfile={ff}:fontsize={fs}:fontcolor={fc}"
            f":x={x}:y={y}:{_fade(t0, t1)}"
            f":shadowcolor={sc}:shadowx={sx}:shadowy={sy}"
        )

    # Scene 1 (0-3s) — Hook
    dt("AMAZON DEAL ALERT!", 62, "0xFFFFFF",
       "(w-tw)/2", "h/2-80", 0, 1.5, sc="0xFF6600")
    dt("Don't miss this!", 44, "0xFF9900",
       "(w-tw)/2", "h/2", 1.5, 3, sc="0x000000")

    # Scene 2 (3-7s) — Product (frame itself shows it; just brand reminder)
    dt("BAZAAR BUDDY LOOT DEALS", 36, "0xFFFFFF",
       "(w-tw)/2", "h-200", 3, 5)

    # Scene 3 (7-12s) — Price reveal
    price_s = _s(price)
    disc_s  = _s(discount)
    if price_s:
        dt(price_s, 74, "0xFFCC00",
           "(w-tw)/2", "h-300", 7, 9, sc="0x000000", sx=5, sy=5)
    if disc_s:
        dt(f"{disc_s} OFF - GRAB NOW!", 48, "0xFF3333",
           "(w-tw)/2", "h-230", 9, 11)

    # Scene 4 (12-17s) — CTA
    link_s = _s(short_link, 50)
    if link_s:
        dt(f"BUY NOW >> {link_s}", 38, "0x00D4FF",
           "(w-tw)/2", "h-160", 12, 14)
    dt("TAP THE LINK BELOW!", 50, "0xFF9900",
       "(w-tw)/2", "h-90", 15, 17, sc="0x000000")

    # Scene 5 (17-20s) — Subscribe
    dt("SUBSCRIBE for Daily Deals!", 46, "0xFFCC00",
       "(w-tw)/2", "h/2", 17, 19, sc="0xFF3300")

    vf = zoom_vf
    if texts:
        vf += "," + ",".join(texts)

    # ── Build audio filter ────────────────────────────────────────────────
    # Inputs: frame(0), music(1?), vo(2?), ding(3?)
    inputs = ["-loop", "1", "-i", frame_path]
    audio_inputs = []
    if music_path and os.path.exists(music_path):
        inputs += ["-i", music_path];  audio_inputs.append("music")
    if vo_path and os.path.exists(vo_path):
        inputs += ["-i", vo_path];     audio_inputs.append("vo")
    if ding_path and os.path.exists(ding_path):
        inputs += ["-i", ding_path];   audio_inputs.append("ding")

    has_audio = bool(audio_inputs)

    # Build audio mixing chain
    idx = 1   # input index counter (0=frame)
    audio_flt_parts = []
    mix_labels      = []

    if "music" in audio_inputs:
        audio_flt_parts.append(
            f"[{idx}:a]aloop=loop=-1:size=2e+09,"
            f"atrim=0:{dur},"
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={dur-2}:d=2,"
            f"volume={'0.25' if 'vo' in audio_inputs else '0.55'}"
            f"[music]"
        )
        mix_labels.append("[music]")
        idx += 1

    if "vo" in audio_inputs:
        audio_flt_parts.append(
            f"[{idx}:a]adelay=500|500,volume=1.4[vo]"
        )
        mix_labels.append("[vo]")
        idx += 1

    if "ding" in audio_inputs:
        audio_flt_parts.append(
            f"[{idx}:a]adelay=7000|7000,volume=1.0[ding]"
        )
        mix_labels.append("[ding]")
        idx += 1

    def _run(cmd_args, label):
        print(f"[REEL] {label}...")
        r = subprocess.run(cmd_args, capture_output=True, timeout=600)
        if r.returncode != 0:
            print(f"[REEL] {label} failed:", r.stderr.decode()[-500:])
        return r.returncode == 0

    # Attempt 1 — full render
    if has_audio and mix_labels:
        n_mix = len(mix_labels)
        audio_flt = ";".join(audio_flt_parts)
        if n_mix == 1:
            audio_flt += f";{mix_labels[0]}acopy[aout]"
        else:
            audio_flt += f";{''.join(mix_labels)}amix=inputs={n_mix}:duration=first[aout]"

        cmd1 = [
            "ffmpeg", "-y",
        ] + inputs + [
            "-filter_complex",
                f"[0:v]{vf}[vout];{audio_flt}",
            "-map", "[vout]", "-map", "[aout]",
            "-t", str(dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-r", str(FPS),
            "-movflags", "+faststart",
            out,
        ]
        if _run(cmd1, "Full render"):
            print(f"[REEL] ✅ Video {os.path.getsize(out)//1024} KB")
            return out

    # Attempt 2 — video only (no audio mixing)
    out2 = tempfile.mktemp(suffix=".mp4")
    music_i = inputs[:]
    # Keep only frame + first music source
    simple_inputs = ["-loop","1","-i",frame_path]
    if music_path and os.path.exists(music_path):
        simple_inputs += ["-i", music_path]
        cmd2 = [
            "ffmpeg", "-y",
        ] + simple_inputs + [
            "-filter_complex",
                f"[0:v]{vf}[vout];"
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{dur},"
                f"afade=t=in:st=0:d=1,afade=t=out:st={dur-1}:d=1,"
                f"volume=0.5[aout]",
            "-map","[vout]","-map","[aout]",
            "-t",str(dur),
            "-c:v","libx264","-preset","fast","-crf","20",
            "-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","128k","-ar","48000",
            "-r",str(FPS),"-movflags","+faststart",
            out2,
        ]
    else:
        cmd2 = [
            "ffmpeg", "-y",
            "-loop","1","-i",frame_path,
            "-filter_complex",f"[0:v]{vf}[vout]",
            "-map","[vout]",
            "-t",str(dur),
            "-c:v","libx264","-preset","fast","-crf","20",
            "-pix_fmt","yuv420p",
            "-r",str(FPS),"-movflags","+faststart",
            out2,
        ]
    if _run(cmd2, "Simple render"):
        return out2

    # Attempt 3 — absolute minimum (static image as video)
    out3 = tempfile.mktemp(suffix=".mp4")
    cmd3 = [
        "ffmpeg", "-y",
        "-loop","1","-i",frame_path,
        "-t",str(dur),
        "-vf",f"scale={W}:{H},setsar=1",
        "-c:v","libx264","-preset","ultrafast","-crf","22",
        "-pix_fmt","yuv420p","-r",str(FPS),
        "-movflags","+faststart",
        out3,
    ]
    if _run(cmd3, "Ultra-simple render"):
        return out3

    print("[REEL] All render attempts failed!")
    return None


def create_reel_video(title, price, discount, image_url, short_link,
                       features=None, rating=None, reviews=None):
    # 1 — Download product image
    print("[REEL] Downloading product image...")
    prod_img = download_product_image(image_url)

    # 2 — Build static frame
    print("[REEL] Building poster frame...")
    frame = build_frame(title, price, discount, prod_img,
                        short_link, features=features,
                        rating=rating, reviews=reviews)
    frame_path = tempfile.mktemp(suffix=".png")
    frame.save(frame_path, "PNG")

    # 3 — Generate voiceover
    vo_path = None
    if ELEVENLABS_API_KEY:
        script = build_voiceover_script(title, price, discount, features)
        print(f"[REEL] Voiceover script: {script[:80]}...")
        vo_path = generate_voiceover(script)

    # 4 — Get background music
    print("[REEL] Getting music...")
    music_path = download_music() or synth_music(DUR + 2)

    # 5 — Cash register ding SFX
    ding_path = gen_ding()

    # 6 — Render video
    video_path = render_video(
        frame_path, music_path, vo_path, ding_path,
        title, price, discount, short_link, dur=DUR,
    )

    # 7 — Cleanup temp files
    for p in [frame_path, music_path, vo_path, ding_path]:
        try:
            if p and os.path.exists(p):
                os.unlink(p)
        except Exception:
            pass

    return video_path


# ═══════════════════════════════════════════════════════════════════════════════
# SEO CAPTIONS
# ═══════════════════════════════════════════════════════════════════════════════
_TAGS = (
    "#Shorts #Reels #AmazonIndia #LootDeals #AmazonDeals #OnlineShopping "
    "#TechDeals #IndiaDeals #BestDeals #BuyNow #DealAlert #DiscountDeals "
    "#BazaarBuddy #AmazonSale #FlashSale #DealOfTheDay #SaleAlert "
    "#ShoppingDeals #GrabNow #AmazonFinds #SaveMoney #AmazonOffer"
)


def _feat_block(features):
    if not features:
        return ""
    return "\n\n🎯 Why Buy?\n" + "\n".join(f"  ✅ {f}" for f in features[:4])


def build_seo_caption(title, price, discount, rating, reviews, link,
                       platform="instagram", features=None):
    deal  = f"🔥 {discount} OFF!" if discount else "🔥 Hot Deal!"
    p_ln  = f"💰 Only {price} on Amazon India" if price else ""
    r_ln  = f"⭐ {rating}/5 • {reviews} Reviews" if rating and reviews else ""
    fb    = _feat_block(features)

    if platform == "telegram":
        return (
            f"🛒 <b>BUY NOW</b> 👉 <a href='{link}'>ORDER HERE ← CLICK</a>\n\n"
            f"🔥 <b>{title}</b>\n\n{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + fb
            + f"\n\n✅ Amazon India Affiliate Deal\n🔗 {link}\n\n"
            "📢 Daily deals 👉 https://t.me/BazaarBuddyLootDeals"
        )

    if platform == "youtube":
        return (
            f"🛒 BUY NOW 👉 {link}\n"
            f"⬆️ Click above for this Amazon India deal!\n\n"
            f"🔥 {title}\n\n{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + fb
            + f"\n\n✅ Amazon India Affiliate Deal (tag: dattatrey07-21)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔔 SUBSCRIBE ▸ https://www.youtube.com/@BazaarBuddyLootDeals\n"
            "📢 Telegram  ▸ https://t.me/BazaarBuddyLootDeals\n"
            "❤️ Instagram ▸ @bazaarbuddylootdeals\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            + _TAGS
        )

    return (
        f"🛒 BUY NOW 👉 {link}\n\n🔥 {title}\n\n{deal}\n"
        + (f"{p_ln}\n" if p_ln else "")
        + (f"{r_ln}\n" if r_ln else "")
        + fb
        + "\n\n👆 Tap link in caption!\n"
        "❤️ Follow @bazaarbuddylootdeals for daily deals!\n\n"
        + _TAGS
    )


def build_yt_title(title, price, discount):
    disc = f"{discount} OFF | " if discount else ""
    pr   = f" at {price}" if price else ""
    return f"🔥 {disc}{title[:55]}{pr} | Amazon India Deal #Shorts"[:100]


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM POSTERS
# ═══════════════════════════════════════════════════════════════════════════════
def post_telegram(video_path, caption):
    url = f"https://api.telegram.org/bot{bot.BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        r = requests.post(url,
            data={"chat_id": bot.CHAT_ID, "caption": caption,
                  "parse_mode": "HTML", "supports_streaming": True},
            files={"video": ("reel.mp4", f, "video/mp4")},
            timeout=180)
    ok = r.status_code == 200
    if not ok:
        print("[TG] Error:", r.text[:200])
    return ok


def post_facebook(video_path, desc):
    url = f"https://graph.facebook.com/v21.0/{bot.FB_PAGE_ID}/videos"
    with open(video_path, "rb") as f:
        r = requests.post(url,
            data={"access_token": bot.FB_PAGE_TOKEN, "description": desc},
            files={"source": ("reel.mp4", f, "video/mp4")},
            timeout=240)
    ok = "id" in r.json()
    if not ok:
        print("[FB] Error:", r.json())
    return ok


def post_instagram(video_path, caption):
    token, ig_id = bot.FB_PAGE_TOKEN, bot.IG_USER_ID
    file_size    = os.path.getsize(video_path)

    r = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media",
        params={"media_type":"REELS","upload_type":"resumable",
                "caption":caption,"share_to_feed":"true",
                "access_token":token},
        timeout=30)
    d = r.json()
    if "id" not in d:
        print("[IG] Container error:", d); return False
    cid = d["id"];  up_url = d.get("uri")
    if not up_url:
        print("[IG] No URI"); return False

    with open(video_path,"rb") as f:
        vb = f.read()
    up = requests.post(up_url,
        headers={"Authorization":f"OAuth {token}",
                 "offset":"0","file_size":str(file_size)},
        data=vb, timeout=240)
    if up.status_code not in (200,201):
        print("[IG] Upload error:", up.text[:200]); return False

    print("[IG] Processing...")
    for i in range(20):
        time.sleep(10)
        st = requests.get(
            f"https://graph.facebook.com/v21.0/{cid}",
            params={"fields":"status_code","access_token":token},
            timeout=20).json()
        sc = st.get("status_code","")
        print(f"[IG] {i+1}/20: {sc}")
        if sc == "FINISHED": break
        if sc == "ERROR":
            print("[IG] Error:", st); return False
    else:
        print("[IG] Timeout"); return False

    pub = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
        params={"creation_id":cid,"access_token":token},
        timeout=30)
    ok = "id" in pub.json()
    if not ok: print("[IG] Publish error:", pub.json())
    return ok


def get_yt_token():
    if not YOUTUBE_REFRESH_TOKEN: return None
    try:
        r = requests.post("https://oauth2.googleapis.com/token",
            data={"client_id":YOUTUBE_CLIENT_ID,
                  "client_secret":YOUTUBE_CLIENT_SECRET,
                  "refresh_token":YOUTUBE_REFRESH_TOKEN,
                  "grant_type":"refresh_token"},
            timeout=20)
        return r.json().get("access_token")
    except Exception as e:
        print(f"[YT] Token error: {e}"); return None


def post_youtube(video_path, title, price, discount, affiliate_link,
                  features=None, max_tries=3):
    sl    = bot.shorten_url(bot.clean_affiliate_url(affiliate_link))
    yt_t  = build_yt_title(title, price, discount)
    yt_d  = build_seo_caption(title, price, discount, None, None,
                               sl, platform="youtube", features=features)
    fsize = os.path.getsize(video_path)

    for attempt in range(1, max_tries+1):
        print(f"[YT] Upload attempt {attempt}/{max_tries}")
        tok = get_yt_token()
        if not tok:
            print("[YT] No token"); return False
        try:
            init = requests.post(
                "https://www.googleapis.com/upload/youtube/v3/videos"
                "?uploadType=resumable&part=snippet,status",
                headers={"Authorization":f"Bearer {tok}",
                         "Content-Type":"application/json",
                         "X-Upload-Content-Type":"video/mp4",
                         "X-Upload-Content-Length":str(fsize)},
                json={
                    "snippet":{"title":yt_t,"description":yt_d,
                               "tags":["AmazonDeals","LootDeals","AmazonIndia",
                                       "Shorts","BazaarBuddy","DealAlert",
                                       "FlashSale","BuyNow","IndiaDeals",
                                       "OnlineShopping","ShopNow"],
                               "categoryId":"26","defaultLanguage":"en"},
                    "status":{"privacyStatus":"public",
                              "selfDeclaredMadeForKids":False}
                },
                timeout=30)
            if init.status_code not in (200,201):
                print(f"[YT] Init {init.status_code}:", init.text[:200])
                time.sleep(8*attempt); continue
            up_url = init.headers.get("Location")
            if not up_url:
                time.sleep(5); continue
            with open(video_path,"rb") as f:
                vb = f.read()
            up = requests.put(up_url,
                headers={"Content-Type":"video/mp4","Content-Length":str(fsize)},
                data=vb, timeout=360)
            if up.status_code in (200,201):
                vid = up.json().get("id","")
                print(f"[YT] ✅ https://youtube.com/shorts/{vid}")
                return vid or True
            print(f"[YT] Upload {up.status_code}:", up.text[:200])
            time.sleep(12*attempt)
        except Exception as e:
            print(f"[YT] Exception {attempt}: {e}"); time.sleep(12*attempt)

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM REPORT
# ═══════════════════════════════════════════════════════════════════════════════
def send_report(res, title, price, discount, yt_id):
    def ic(v): return "✅" if v else "❌"
    yt_link = f"\n🎬 https://youtube.com/shorts/{yt_id}" if isinstance(yt_id,str) and yt_id else ""
    msg = (
        f"📊 <b>Daily Reel Report</b>\n\n"
        f"<b>Product:</b> {title[:60]}\n"
        f"<b>Price:</b> {price}   <b>Discount:</b> {discount}\n\n"
        f"Telegram  {ic(res.get('tg'))}\n"
        f"Facebook  {ic(res.get('fb'))}\n"
        f"Instagram {ic(res.get('ig'))}\n"
        f"YouTube   {ic(res.get('yt'))}"
        + yt_link
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot.BOT_TOKEN}/sendMessage",
            data={"chat_id":bot.CHAT_ID,"text":msg,"parse_mode":"HTML"},
            timeout=15)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════
FALLBACK_PRODUCTS = [
    ("boAt Rockerz 450 Wireless Bluetooth Headphones",
     "₹1,299",
     "https://www.amazon.in/dp/B07QFR85LP?tag=dattatrey07-21",
     "https://m.media-amazon.com/images/I/61PzTlnzGEL._SL1500_.jpg",
     "https://www.amazon.in/dp/B07QFR85LP"),
    ("Mi Smart Band 7 Fitness Tracker",
     "₹2,799",
     "https://www.amazon.in/dp/B0B2Q5TGJP?tag=dattatrey07-21",
     "https://m.media-amazon.com/images/I/51jkrS-bqXL._SL1500_.jpg",
     "https://www.amazon.in/dp/B0B2Q5TGJP"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def post_daily_reel():
    print("[REEL] ══════════ Daily Reel Job v4 ══════════")

    # 1 — Scrape products
    products = None
    for attempt in range(3):
        try:
            products = bot.scrape_products()
            if products: break
            print(f"[REEL] Scrape {attempt+1} returned 0, retrying...")
        except Exception as e:
            print(f"[REEL] Scrape exception {attempt+1}: {e}")
        time.sleep(10)

    if not products:
        print("[REEL] Using fallback products")
        products = list(FALLBACK_PRODUCTS)

    title, price, affiliate_link, image_url, base_link = random.choice(products)

    # 2 — Clean link
    try:
        affiliate_link = bot.clean_affiliate_url(affiliate_link)
    except Exception:
        pass

    # 3 — Product details
    rating, reviews, discount, features = "", "", "", []
    try:
        r, rv, _, _, discount = bot.get_product_details(base_link)
        rating, reviews = r, rv
    except Exception as e:
        print(f"[REEL] Details error: {e}")
    try:
        features = bot.get_product_features(base_link)
    except Exception as e:
        print(f"[REEL] Features error: {e}")

    # 4 — Short link
    short_link = affiliate_link
    try:
        short_link = bot.shorten_url(affiliate_link)
    except Exception:
        pass

    print(f"[REEL] Title    : {title[:70]}")
    print(f"[REEL] Price    : {price}  Discount: {discount}")
    print(f"[REEL] Rating   : {rating}  Reviews: {reviews}")
    print(f"[REEL] Features : {features}")
    print(f"[REEL] Link     : {short_link}")

    # 5 — Captions
    tg_cap = build_seo_caption(title, price, discount, rating, reviews,
                                affiliate_link, platform="telegram",
                                features=features)
    ig_cap = build_seo_caption(title, price, discount, rating, reviews,
                                short_link, platform="instagram",
                                features=features)

    # 6 — Create video (2 attempts)
    video_path = None
    for attempt in range(2):
        try:
            video_path = create_reel_video(
                title, price, discount, image_url, short_link,
                features=features, rating=rating, reviews=reviews)
            if video_path: break
        except Exception as e:
            print(f"[REEL] Video exception {attempt+1}: {e}")
        time.sleep(5)

    if not video_path:
        print("[REEL] ❌ Video creation failed after 2 attempts — aborting")
        return

    # 7 — Post to all platforms
    res = {}

    print("\n[REEL] ── Telegram...")
    try:    res["tg"] = post_telegram(video_path, tg_cap)
    except Exception as e:
        print(f"[TG] {e}"); res["tg"] = False
    print(f"[REEL] Telegram  : {'✅' if res['tg'] else '❌'}")
    time.sleep(4)

    print("\n[REEL] ── Facebook...")
    try:    res["fb"] = post_facebook(video_path, ig_cap)
    except Exception as e:
        print(f"[FB] {e}"); res["fb"] = False
    print(f"[REEL] Facebook  : {'✅' if res['fb'] else '❌'}")
    time.sleep(4)

    print("\n[REEL] ── Instagram...")
    try:    res["ig"] = post_instagram(video_path, ig_cap)
    except Exception as e:
        print(f"[IG] {e}"); res["ig"] = False
    print(f"[REEL] Instagram : {'✅' if res['ig'] else '❌'}")
    time.sleep(4)

    print("\n[REEL] ── YouTube Shorts...")
    yt_r = False
    try:    yt_r = post_youtube(video_path, title, price, discount,
                                 affiliate_link, features=features)
    except Exception as e:
        print(f"[YT] {e}")
    res["yt"] = bool(yt_r)
    print(f"[REEL] YouTube   : {'✅' if res['yt'] else '❌'}")

    # 8 — Cleanup + report
    try:    os.unlink(video_path)
    except Exception: pass

    send_report(res, title, price, discount,
                yt_r if isinstance(yt_r, str) else None)

    print(f"\n[REEL] ══ DONE  TG={res['tg']} FB={res['fb']} "
          f"IG={res['ig']} YT={res['yt']} ══")
    return res


if __name__ == "__main__":
    post_daily_reel()
