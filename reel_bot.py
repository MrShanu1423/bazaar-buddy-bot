"""
Bazaar Buddy — Daily Reel Bot v5 (Cinematic Multi-Scene)
=========================================================
Format : 1080×1920  9:16  30 FPS  H.264  AAC-48kHz  20 sec
Engine : 4 separate PNG scenes → ffmpeg xfade concat → final MP4

SCENE STRUCTURE
  Scene 1 (0–4s)   HOOK       — black/orange, animated deal-alert text
  Scene 2 (4–10s)  PRODUCT    — full-screen product image, title, rating
  Scene 3 (10–15s) FEATURES   — WHY BUY section, 4 bullet features
  Scene 4 (15–20s) PRICE+CTA  — big price, discount, link, subscribe CTA

Crash-proofing:
  • 3-layer image download (direct → weserv proxy → text placeholder)
  • 3-level video render (full xfade → simple concat → static fallback)
  • Product junk-filter & fallback product list
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

# ─── Constants ────────────────────────────────────────────────────────────────
W, H  = 1080, 1920
FPS   = 30
DUR   = 20

# Scene durations (seconds)
S1_DUR = 4    # Hook
S2_DUR = 6    # Product
S3_DUR = 5    # Features
S4_DUR = 5    # Price + CTA
XFADE  = 0.6  # Transition duration

# ─── Palette ─────────────────────────────────────────────────────────────────
BG     = (8,   8,  14)
ORANGE = (255, 153,  0)
GOLD   = (255, 210, 20)
WHITE  = (255, 255, 255)
GREY   = (170, 170, 185)
CYAN   = (0,   210, 255)
RED    = (220,  40,  40)
GREEN  = (30,  200,  80)
DARK   = (16,  16,  26)


# ═══════════════════════════════════════════════════════════════════════════════
# FONTS + DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def font(size, bold=False):
    paths = (
        ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSans.ttf"]
    )
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: continue
    return ImageFont.load_default()


def vgrad(draw, x0, y0, x1, y1, top, bot_col):
    h = max(y1 - y0, 1)
    for dy in range(h):
        t = dy / h
        c = tuple(int(top[i] + t*(bot_col[i]-top[i])) for i in range(3))
        draw.line([(x0, y0+dy), (x1, y0+dy)], fill=c)


def txt(draw, xy, text, fnt, fill, shadow_col=(0,0,0), anchor="mm", sdx=3, sdy=3):
    x, y = xy
    if shadow_col:
        draw.text((x+sdx, y+sdy), text, font=fnt, fill=shadow_col, anchor=anchor)
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor)


def pill_btn(draw, cx, cy, text, fnt, bg, fg, rx=18, py_pad=16, px_pad=36):
    try:
        bb = draw.textbbox((0,0), text, font=fnt)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        x0, y0 = cx-tw//2-px_pad, cy-th//2-py_pad
        x1, y1 = cx+tw//2+px_pad, cy+th//2+py_pad
        draw.rounded_rectangle([x0+4, y0+4, x1+4, y1+4], radius=rx, fill=(0,0,0))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=rx, fill=bg)
        draw.text((cx, cy), text, font=fnt, fill=fg, anchor="mm")
        return y1
    except Exception:
        return cy + 60


def glow_border(draw, x0, y0, x1, y1, col, r=18):
    for off in [9, 6, 3, 1]:
        c = tuple(max(0, v*off//9) for v in col)
        draw.rounded_rectangle([x0-off, y0-off, x1+off, y1+off],
                                radius=r+off, outline=c, width=2)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=col, width=3)


def new_canvas():
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    vgrad(draw, 0, 0, W, H, (12,12,20), (5,5,12))
    return img, draw


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE DOWNLOAD — 3-layer fallback
# ═══════════════════════════════════════════════════════════════════════════════
IMG_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.amazon.in/",
}


def _img_variants(url):
    import re
    vs = [url]
    clean = re.sub(r'\._[A-Z]{2,3}\d*_\.', '.', url)
    if clean != url: vs.append(clean)
    for sz in ["_SL1000_", "_SL800_", "_AC_SX522_"]:
        vs.append(re.sub(r'_S[LX]\d+_', sz, url))
    return list(dict.fromkeys(vs))


def fetch_image(image_url):
    if not image_url:
        return None
    # Layer 1 — direct
    for url in _img_variants(image_url):
        try:
            r = requests.get(url, headers=IMG_HDR, timeout=20)
            if r.status_code == 200 and len(r.content) > 3_000:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                print(f"[IMG] Direct OK ({len(r.content)//1024}KB)")
                return img
        except Exception: pass
    # Layer 2 — weserv proxy
    try:
        stripped = image_url.replace("https://","").replace("http://","")
        proxy = f"https://images.weserv.nl/?url={urllib.parse.quote(stripped,safe='')}&w=900&output=png"
        r = requests.get(proxy, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 3_000:
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            print(f"[IMG] Proxy OK ({len(r.content)//1024}KB)")
            return img
    except Exception as e:
        print(f"[IMG] Proxy fail: {e}")
    print("[IMG] All failed — placeholder")
    return None


def make_placeholder(title):
    img  = Image.new("RGB", (900, 700), (20, 20, 36))
    draw = ImageDraw.Draw(img)
    vgrad(draw, 0, 0, 900, 700, (30,20,55), (12,8,28))
    draw.rounded_rectangle([28,28,872,672], radius=30, outline=ORANGE, width=4)
    f = font(90, bold=True)
    draw.text((450,250), "🛍️", font=f, fill=ORANGE, anchor="mm")
    f2 = font(36)
    for i, line in enumerate(textwrap.wrap(title[:60], 20)[:3]):
        draw.text((450, 370+i*52), line, font=f2, fill=WHITE, anchor="mm")
    return img.convert("RGBA")


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 1 — HOOK (black bg, orange deal alert)
# ═══════════════════════════════════════════════════════════════════════════════
def scene_hook():
    img  = Image.new("RGB", (W, H), (6, 6, 10))
    draw = ImageDraw.Draw(img)

    # Background radial glow
    for r in range(500, 0, -50):
        alpha = int(25 * (500-r) / 500)
        c = (min(255, ORANGE[0]*alpha//25),
             min(255, ORANGE[1]*alpha//40), 0)
        draw.ellipse([W//2-r, H//2-r-200, W//2+r, H//2+r-200], fill=c)

    # Top thin orange accent line
    draw.rectangle([0, 0, W, 6], fill=ORANGE)
    draw.rectangle([0, H-6, W, H], fill=ORANGE)

    # HOT DEAL ALERT — giant text
    f1 = font(88, bold=True)
    txt(draw, (W//2, 760), "🔥 HOT DEAL", f1, WHITE, ORANGE, sdx=5, sdy=5)
    txt(draw, (W//2, 870), "ALERT!  🔥", f1, ORANGE, (100,50,0), sdx=5, sdy=5)

    # Subtext
    f2 = font(50)
    txt(draw, (W//2, 990), "Amazon India Bestseller", f2, GREY, shadow_col=None)

    f3 = font(40)
    txt(draw, (W//2, 1060), "Exclusive Deal — Limited Time Only!", f3, (200,200,200), shadow_col=None)

    # Bottom branding
    draw.rectangle([0, H-120, W, H-116], fill=ORANGE)
    fb = font(32, bold=True)
    txt(draw, (W//2, H-82), "🔔 SUBSCRIBE ▸ @BazaarBuddyLootDeals", fb, GOLD, shadow_col=None)
    txt(draw, (W//2, H-44), "📢 t.me/BazaarBuddyLootDeals  •  ❤️ @bazaarbuddylootdeals", font(26), GREY, shadow_col=None)

    return img


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 2 — PRODUCT (full-screen product image + title + rating)
# ═══════════════════════════════════════════════════════════════════════════════
def scene_product(title, prod_img_pil, rating, reviews):
    img  = Image.new("RGB", (W, H), DARK)
    draw = ImageDraw.Draw(img)
    vgrad(draw, 0, 0, W, H, (14,14,24), (8,8,16))

    # Top label
    draw.rectangle([0, 0, W, 100], fill=(18,18,30))
    draw.rectangle([0, 96, W, 100], fill=ORANGE)
    ft = font(38, bold=True)
    txt(draw, (W//2, 50), "🛍️  PRODUCT SHOWCASE", ft, WHITE, shadow_col=None)

    # ─── Product image card (large, centered) ──────────────────────────
    CARD_X0, CARD_Y0 = 30, 110
    CARD_X1, CARD_Y1 = W-30, 1300
    CARD_W  = CARD_X1 - CARD_X0
    CARD_H  = CARD_Y1 - CARD_Y0

    # White card bg
    draw.rounded_rectangle([CARD_X0, CARD_Y0, CARD_X1, CARD_Y1],
                            radius=24, fill=(252, 252, 255))
    glow_border(draw, CARD_X0, CARD_Y0, CARD_X1, CARD_Y1, ORANGE, r=24)

    # Paste product image
    prod = (prod_img_pil or make_placeholder(title)).convert("RGBA")
    prod.thumbnail((CARD_W-60, CARD_H-60), Image.LANCZOS)
    px = CARD_X0 + (CARD_W - prod.width) // 2
    py = CARD_Y0 + (CARD_H - prod.height) // 2

    # Alpha composite product onto canvas
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    overlay.paste(prod, (px, py), mask=prod)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ─── Info below card ───────────────────────────────────────────────
    y = CARD_Y1 + 18

    # Title (2 lines max)
    f_title = font(42, bold=True)
    wrapped = textwrap.wrap(title[:100], width=24)
    for line in wrapped[:2]:
        txt(draw, (W//2, y+26), line, f_title, WHITE, sdx=2, sdy=2)
        y += 60
    y += 10

    # Star rating
    if rating:
        try:
            stars = min(5, max(0, int(float(rating))))
            star_str = "★" * stars + "☆" * (5-stars)
            f_star = font(40, bold=True)
            txt(draw, (W//2, y+26), f"{star_str}  {rating}/5", f_star, GOLD,
                shadow_col=(60,50,0), sdx=2, sdy=2)
            if reviews:
                txt(draw, (W//2, y+72), f"({reviews} Reviews) • Amazon India",
                    font(28), GREY, shadow_col=None)
            y += 100
        except Exception:
            pass

    # Amazon Loot Deal badge
    pill_btn(draw, W//2, y+36, "✅  Amazon India Loot Deal — Best Price!",
             font(30, bold=True), GREEN, WHITE)

    # Footer
    draw.rectangle([0, H-90, W, H], fill=(10,10,18))
    txt(draw, (W//2, H-46), "🔔 SUBSCRIBE  ▸  @BazaarBuddyLootDeals  ▸  Daily Deals",
        font(28, bold=True), GOLD, shadow_col=None)

    return img


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 3 — FEATURES (WHY BUY section)
# ═══════════════════════════════════════════════════════════════════════════════
def scene_features(title, features, prod_img_pil):
    img  = Image.new("RGB", (W, H), (10, 10, 18))
    draw = ImageDraw.Draw(img)
    vgrad(draw, 0, 0, W, H, (14,10,28), (8,6,16))

    # Top bar
    draw.rectangle([0, 0, W, 110], fill=(20,14,42))
    draw.rectangle([0, 106, W, 110], fill=ORANGE)
    txt(draw, (W//2, 55), "💡  WHY BUY THIS?", font(46, bold=True), WHITE,
        shadow_col=ORANGE, sdx=3, sdy=3)

    # Small product thumbnail on right
    if prod_img_pil:
        try:
            thumb = prod_img_pil.copy().convert("RGBA")
            thumb.thumbnail((280, 280), Image.LANCZOS)
            thumb_bg = Image.new("RGB", (thumb.width+16, thumb.height+16), WHITE)
            img_rgba = img.convert("RGBA")
            overlay  = Image.new("RGBA", (W, H), (0,0,0,0))
            tx = W - thumb.width - 24 - 8
            ty = 122
            thumb_full = Image.new("RGBA", (thumb.width+16, thumb.height+16), (255,255,255,255))
            thumb_full.paste(thumb, (8,8), mask=thumb)
            overlay.paste(thumb_full, (tx-8, ty-8))
            img = Image.alpha_composite(img_rgba, overlay).convert("RGB")
            draw = ImageDraw.Draw(img)
            # Orange border around thumb
            draw.rounded_rectangle([tx-10, ty-10, tx+thumb.width+10, ty+thumb.height+10],
                                    radius=12, outline=ORANGE, width=3)
        except Exception:
            pass

    # Feature bullets — big, high contrast, easy to read
    feat_list = features[:4] if features else [
        "Premium quality build",
        "Easy to use & setup",
        "Trusted by thousands",
        "Best value for money",
    ]

    icons    = ["⚡", "✅", "🔥", "💡"]
    icon_col = [ORANGE, GREEN, RED, GOLD]
    fy = 430
    f_feat = font(38, bold=True)
    f_desc = font(30)

    for i, feat in enumerate(feat_list):
        icon = icons[i % 4]
        ic   = icon_col[i % 4]
        # Row background
        draw.rounded_rectangle([20, fy, W-20, fy+88], radius=18,
                                fill=(20, 18, 38))
        draw.rounded_rectangle([20, fy, W-20, fy+88], radius=18,
                                outline=ic, width=2)
        # Left color bar
        draw.rounded_rectangle([20, fy, 28, fy+88], radius=6, fill=ic)
        # Icon
        draw.text((70, fy+20), icon, font=font(44, bold=True), fill=ic)
        # Feature text (up to 2 lines)
        lines = textwrap.wrap(feat, width=28)
        if len(lines) == 1:
            txt(draw, (W//2+20, fy+44), lines[0], f_feat, WHITE, shadow_col=None)
        else:
            txt(draw, (W//2+20, fy+26), lines[0], f_desc, WHITE, shadow_col=None)
            txt(draw, (W//2+20, fy+62), lines[1][:35], f_desc, GREY, shadow_col=None)
        fy += 104

    # Bottom: product name reminder
    y = fy + 20
    draw.rectangle([0, y, W, y+3], fill=ORANGE)
    txt(draw, (W//2, y+44), title[:55], font(34, bold=True), ORANGE, shadow_col=None)

    # Footer
    draw.rectangle([0, H-90, W, H], fill=(10,10,18))
    txt(draw, (W//2, H-46), "🔔 SUBSCRIBE  ▸  @BazaarBuddyLootDeals  ▸  Daily Deals",
        font(28, bold=True), GOLD, shadow_col=None)

    return img


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 4 — PRICE + CTA
# ═══════════════════════════════════════════════════════════════════════════════
def scene_cta(title, price, discount, short_link):
    img  = Image.new("RGB", (W, H), (8, 6, 14))
    draw = ImageDraw.Draw(img)
    vgrad(draw, 0, 0, W, H, (16, 8, 6), (8, 4, 4))

    # Top full-width orange bar
    vgrad(draw, 0, 0, W, 120, (220, 100, 0), (255, 153, 0))
    txt(draw, (W//2, 60), "💰  GRAB THE DEAL!", font(50, bold=True), WHITE,
        shadow_col=(80,30,0), sdx=4, sdy=4)

    # Divider
    draw.rectangle([0, 120, W, 126], fill=GOLD)

    # Price — HUGE
    y = 200
    if price:
        f_price = font(110, bold=True)
        txt(draw, (W//2, y+60), price, f_price, GOLD,
            shadow_col=(80,60,0), sdx=6, sdy=6)
        y += 140

    # Discount badge
    if discount:
        y = pill_btn(draw, W//2, y+50,
                     f"🏷️  {discount} OFF  —  LIMITED OFFER!",
                     font(48, bold=True), RED, WHITE) + 30

    # Delivery + rating quick-stats
    stats = [("🚚", "Free Delivery"), ("⭐", "Top Rated"), ("✅", "Amazon Verified")]
    sx = W // (len(stats) + 1)
    for i, (icon, label) in enumerate(stats):
        cx = sx * (i+1)
        draw.rounded_rectangle([cx-90, y, cx+90, y+90], radius=14, fill=(22,18,40))
        draw.rounded_rectangle([cx-90, y, cx+90, y+90], radius=14, outline=ORANGE, width=2)
        draw.text((cx, y+28), icon, font=font(32), fill=ORANGE, anchor="mm")
        draw.text((cx, y+66), label, font=font(22, bold=True), fill=WHITE, anchor="mm")
    y += 110

    # Link box
    y += 20
    draw.rounded_rectangle([24, y, W-24, y+64], radius=16, fill=(0,24,60))
    draw.rounded_rectangle([24, y, W-24, y+64], radius=16, outline=CYAN, width=3)
    txt(draw, (W//2, y+32), f"🛒  {short_link}", font(36), CYAN, shadow_col=None)
    y += 84

    # BUY NOW button
    y = pill_btn(draw, W//2, y+40,
                 "👆  TAP LINK — BUY NOW  👆",
                 font(50, bold=True), ORANGE, WHITE, rx=28) + 30

    # Product title reminder
    draw.rectangle([0, y+10, W, y+13], fill=(60,40,0))
    txt(draw, (W//2, y+44), title[:52], font(32, bold=True), ORANGE, shadow_col=None)

    # Footer strip
    draw.rectangle([0, H-148, W, H], fill=(10,10,18))
    draw.rectangle([0, H-148, W, H-145], fill=ORANGE)
    txt(draw, (W//2, H-114), "🔔 SUBSCRIBE  ▸  YouTube: @BazaarBuddyLootDeals",
        font(30, bold=True), GOLD, shadow_col=None)
    txt(draw, (W//2, H-76), "❤️ Instagram: @bazaarbuddylootdeals  •  📢 t.me/BazaarBuddyLootDeals",
        font(24), CYAN, shadow_col=None)
    txt(draw, (W//2, H-40), "🛍️ Best Amazon India Deals — Daily — 100% Free",
        font(22), GREY, shadow_col=None)

    return img


# ═══════════════════════════════════════════════════════════════════════════════
# MUSIC + AUDIO
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
]


def get_music():
    random.shuffle(MUSIC_URLS)
    p = tempfile.mktemp(suffix=".mp3")
    for url in MUSIC_URLS:
        try:
            r = requests.get(url, timeout=22, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 15_000:
                with open(p, "wb") as f: f.write(r.content)
                print(f"[MUSIC] OK ({len(r.content)//1024}KB)")
                return p
        except Exception: pass
    # Synth fallback
    out = tempfile.mktemp(suffix=".mp3")
    bpm  = 128
    bt   = 60/bpm
    expr = (
        f"0.18*sin(2*PI*60*t)*exp(-8*mod(t,{bt:.4f}))"
        f"+0.15*sin(2*PI*110*t)"
        f"+0.12*sin(2*PI*330*(1+0.012*sin(2*PI*0.5*t))*t)"
        f"+0.08*sin(2*PI*660*t)"
    )
    cmd = ["ffmpeg","-y","-f","lavfi",
           "-i",f"aevalsrc='{expr}':s=44100:d={DUR+3}",
           "-af",f"afade=t=in:st=0:d=2,afade=t=out:st={DUR+1}:d=2,volume=0.6",
           "-q:a","4", out]
    res = subprocess.run(cmd, capture_output=True, timeout=60)
    return out if res.returncode == 0 else None


# ═══════════════════════════════════════════════════════════════════════════════
# ELEVENLABS VOICEOVER
# ═══════════════════════════════════════════════════════════════════════════════
def get_voiceover(title, price, discount, features):
    if not ELEVENLABS_API_KEY:
        return None
    feat_str = ". ".join((features or [])[:2])
    disc_str = f"Get {discount} off!" if discount else ""
    price_str = f"Just {price} on Amazon India!" if price else ""
    script = (
        f"Amazon deal alert! {title[:45]}. "
        f"{disc_str} {price_str} {feat_str} "
        "Tap the link to buy now. Subscribe for daily deals!"
    )[:380]
    try:
        r = requests.post(
            "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL",
            headers={"xi-api-key": ELEVENLABS_API_KEY,
                     "Content-Type":"application/json","Accept":"audio/mpeg"},
            json={"text": script, "model_id":"eleven_multilingual_v2",
                  "voice_settings":{"stability":0.55,"similarity_boost":0.80}},
            timeout=40,
        )
        if r.status_code == 200 and len(r.content) > 2_000:
            p = tempfile.mktemp(suffix=".mp3")
            with open(p,"wb") as f: f.write(r.content)
            print(f"[VO] ElevenLabs OK ({len(r.content)//1024}KB)")
            return p
        print(f"[VO] ElevenLabs {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"[VO] Exception: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# VIDEO RENDERER — 4-scene xfade concat
# ═══════════════════════════════════════════════════════════════════════════════
def _save_scene(img, suffix):
    p = tempfile.mktemp(suffix=suffix)
    img.save(p, "PNG", optimize=False)
    return p


def _ffrun(cmd, label, timeout=600):
    print(f"[REEL] {label}...")
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        print(f"[REEL] {label} FAIL:", r.stderr.decode()[-600:])
    return r.returncode == 0


def _make_clip(scene_path, duration, zoom_dir="in"):
    """Turn a static PNG into an animated clip with Ken Burns effect."""
    out = tempfile.mktemp(suffix=".mp4")
    total = int(duration * FPS)
    if zoom_dir == "in":
        # Zoom 1.0 → 1.08
        z_expr = f"min(1.0+0.08*on/{total},1.08)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif zoom_dir == "out":
        # Zoom 1.08 → 1.0
        z_expr = f"max(1.08-0.08*on/{total},1.0)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    else:
        # Pan right
        z_expr = "1.05"
        x_expr = f"(iw-(iw/zoom))*on/{total}"
        y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"zoompan=z='{z_expr}'"
        f":x='{x_expr}':y='{y_expr}'"
        f":d={total}:s={W}x{H}:fps={FPS}"
    )
    cmd = [
        "ffmpeg","-y","-loop","1","-i",scene_path,
        "-vf",vf,
        "-t",str(duration),
        "-c:v","libx264","-preset","fast","-crf","18",
        "-pix_fmt","yuv420p","-r",str(FPS),
        out,
    ]
    ok = _ffrun(cmd, f"clip({zoom_dir} {duration}s)")
    return out if ok else None


def _concat_xfade(clips, durations, xfade_dur=XFADE):
    """Concatenate clips with xfade transitions."""
    out = tempfile.mktemp(suffix=".mp4")

    transitions = ["fade", "slideleft", "wipeleft", "slideup"]

    if len(clips) == 1:
        return clips[0]

    # Build filter_complex
    inputs = []
    for c in clips:
        inputs += ["-i", c]

    # Build xfade chain: [v0][v1] → xfade → [x1]; [x1][v2] → xfade → [x2] …
    parts = []
    # Offset for each transition = cumulative duration minus overlap
    cum = 0
    labels = [f"[v{i}]" for i in range(len(clips))]

    # Rename inputs
    rename = ""
    for i in range(len(clips)):
        rename += f"[{i}:v]copy[v{i}];"

    chain = ""
    prev_label = "[v0]"
    for i in range(1, len(clips)):
        cum += durations[i-1] - xfade_dur
        ttype = transitions[(i-1) % len(transitions)]
        out_label = f"[xf{i}]" if i < len(clips)-1 else "[vout]"
        chain += (
            f"{prev_label}[v{i}]"
            f"xfade=transition={ttype}:duration={xfade_dur}:offset={cum:.2f}"
            f"{out_label};"
        )
        prev_label = f"[xf{i}]"
        cum += xfade_dur  # account for the overlap consumed

    filter_str = rename.rstrip(";") + ";" + chain.rstrip(";")

    cmd = (
        ["ffmpeg","-y"]
        + inputs
        + ["-filter_complex", filter_str,
           "-map","[vout]",
           "-t",str(DUR),
           "-c:v","libx264","-preset","fast","-crf","18",
           "-pix_fmt","yuv420p","-r",str(FPS),
           out]
    )
    ok = _ffrun(cmd, "xfade concat")
    return out if ok else None


def _add_audio(video_path, music_path, vo_path, dur=DUR):
    out = tempfile.mktemp(suffix=".mp4")

    if not music_path and not vo_path:
        return video_path

    inputs = ["-i", video_path]
    filter_parts = []
    mix_labels   = []
    idx = 1

    if music_path and os.path.exists(music_path):
        vol = "0.25" if vo_path else "0.55"
        filter_parts.append(
            f"[{idx}:a]aloop=loop=-1:size=2e+09,"
            f"atrim=0:{dur},"
            f"afade=t=in:st=0:d=1.5,"
            f"afade=t=out:st={dur-2}:d=2,"
            f"volume={vol}[music]"
        )
        mix_labels.append("[music]")
        inputs += ["-i", music_path]
        idx += 1

    if vo_path and os.path.exists(vo_path):
        filter_parts.append(f"[{idx}:a]adelay=300|300,volume=1.3[vo]")
        mix_labels.append("[vo]")
        inputs += ["-i", vo_path]
        idx += 1

    if not filter_parts:
        return video_path

    if len(mix_labels) == 1:
        filter_str = ";".join(filter_parts) + f";{mix_labels[0]}acopy[aout]"
    else:
        filter_str = (";".join(filter_parts)
                      + f";{''.join(mix_labels)}amix=inputs={len(mix_labels)}"
                      f":duration=first[aout]")

    cmd = (
        ["ffmpeg","-y"]
        + inputs
        + ["-filter_complex", filter_str,
           "-map","0:v","-map","[aout]",
           "-t",str(dur),
           "-c:v","copy",
           "-c:a","aac","-b:a","192k","-ar","48000",
           "-movflags","+faststart",
           out]
    )
    ok = _ffrun(cmd, "audio mix")
    return out if ok else video_path


def create_reel_video(title, price, discount, image_url, short_link,
                       features=None, rating=None, reviews=None):
    print("[REEL] ── Fetching product image...")
    prod_img = fetch_image(image_url)

    # ── Generate 4 scene PNGs ──────────────────────────────────────────
    print("[REEL] ── Building scene frames...")
    s1 = _save_scene(scene_hook(),                                     "_s1.png")
    s2 = _save_scene(scene_product(title, prod_img, rating, reviews),  "_s2.png")
    s3 = _save_scene(scene_features(title, features or [], prod_img),  "_s3.png")
    s4 = _save_scene(scene_cta(title, price, discount, short_link),    "_s4.png")
    scene_paths    = [s1, s2, s3, s4]
    scene_durations= [S1_DUR, S2_DUR, S3_DUR, S4_DUR]
    zoom_dirs      = ["in", "out", "pan", "in"]

    # ── Render each scene as animated clip ────────────────────────────
    print("[REEL] ── Rendering scene clips...")
    clips = []
    for i, (sp, dur, zd) in enumerate(zip(scene_paths, scene_durations, zoom_dirs)):
        clip = _make_clip(sp, dur, zd)
        if clip:
            clips.append((clip, dur))
        else:
            print(f"[REEL] Scene {i+1} clip failed — using static fallback")
            # Still add the PNG path so concat can use it
            fallback = tempfile.mktemp(suffix=".mp4")
            cmd = ["ffmpeg","-y","-loop","1","-i",sp,
                   "-t",str(dur),"-c:v","libx264","-preset","ultrafast","-crf","22",
                   "-pix_fmt","yuv420p","-r",str(FPS),"-vf",f"scale={W}:{H}",fallback]
            if _ffrun(cmd, f"static clip {i+1}", timeout=120):
                clips.append((fallback, dur))

    # ── Concat scenes with xfade ──────────────────────────────────────
    print("[REEL] ── Concatenating scenes with transitions...")
    video_path = None
    if len(clips) >= 2:
        video_path = _concat_xfade([c for c,_ in clips],
                                    [d for _,d in clips])

    # Fallback: simple concat without xfade
    if not video_path and clips:
        print("[REEL] xfade failed — simple concat fallback...")
        list_file = tempfile.mktemp(suffix=".txt")
        with open(list_file, "w") as f:
            for clip_path, _ in clips:
                f.write(f"file '{clip_path}'\n")
        out = tempfile.mktemp(suffix=".mp4")
        cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",list_file,
               "-c","copy","-t",str(DUR),out]
        if _ffrun(cmd, "simple concat", timeout=120):
            video_path = out

    # Absolute fallback: just use scene 2 (product scene)
    if not video_path and clips:
        print("[REEL] Using single scene fallback...")
        video_path = clips[0][0]

    if not video_path:
        print("[REEL] ❌ Video render completely failed")
        return None

    # ── Audio ─────────────────────────────────────────────────────────
    print("[REEL] ── Getting music...")
    music_path = get_music()

    vo_path = None
    if ELEVENLABS_API_KEY:
        print("[REEL] ── Generating voiceover...")
        vo_path = get_voiceover(title, price, discount, features)

    print("[REEL] ── Mixing audio...")
    final_path = _add_audio(video_path, music_path, vo_path)

    # ── Cleanup temp files ────────────────────────────────────────────
    for p in scene_paths + [c for c,_ in clips] + [music_path, vo_path]:
        try:
            if p and p != final_path and os.path.exists(p):
                os.unlink(p)
        except Exception:
            pass

    if final_path and os.path.exists(final_path):
        kb = os.path.getsize(final_path) // 1024
        print(f"[REEL] ✅ Final video: {kb} KB")
    return final_path


# ═══════════════════════════════════════════════════════════════════════════════
# SEO CAPTIONS
# ═══════════════════════════════════════════════════════════════════════════════
_TAGS = (
    "#Shorts #Reels #AmazonIndia #LootDeals #AmazonDeals #OnlineShopping "
    "#TechDeals #IndiaDeals #BestDeals #BuyNow #DealAlert "
    "#BazaarBuddy #AmazonSale #FlashSale #DealOfTheDay #SaleAlert"
)


def build_caption(title, price, discount, rating, reviews, link,
                   platform="instagram", features=None):
    deal  = f"🔥 {discount} OFF!" if discount else "🔥 Hot Deal!"
    p_ln  = f"💰 Only {price}" if price else ""
    r_ln  = f"⭐ {rating}/5 • {reviews} Reviews" if rating and reviews else ""
    fb    = ("\n\n🎯 Why Buy?\n" + "\n".join(f"  ✅ {f}" for f in (features or [])[:4])
             if features else "")

    if platform == "telegram":
        return (
            f"🛒 <b>BUY NOW</b> 👉 <a href='{link}'>ORDER HERE ← CLICK</a>\n\n"
            f"🔥 <b>{title}</b>\n\n{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + fb
            + f"\n\n🔗 {link}\n\n"
            "📢 https://t.me/BazaarBuddyLootDeals"
        )
    if platform == "youtube":
        return (
            f"🛒 BUY NOW 👉 {link}\n⬆️ Click above to order!\n\n"
            f"🔥 {title}\n\n{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + fb
            + "\n\n✅ Amazon India Loot Deal — Best Price!\n\n"
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
        "❤️ Follow @bazaarbuddylootdeals\n\n" + _TAGS
    )


def yt_title(title, price, discount):
    disc = f"{discount} OFF | " if discount else ""
    pr   = f" at {price}" if price else ""
    return f"🔥 {disc}{title[:55]}{pr} | Amazon India #Shorts"[:100]


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM POSTING
# ═══════════════════════════════════════════════════════════════════════════════
def post_telegram(video_path, caption):
    url = f"https://api.telegram.org/bot{bot.BOT_TOKEN}/sendVideo"
    with open(video_path,"rb") as f:
        r = requests.post(url,
            data={"chat_id":bot.CHAT_ID,"caption":caption,
                  "parse_mode":"HTML","supports_streaming":True},
            files={"video":("reel.mp4",f,"video/mp4")},
            timeout=180)
    ok = r.status_code == 200
    if not ok: print("[TG] Error:", r.text[:200])
    return ok


def post_facebook(video_path, desc):
    url = f"https://graph.facebook.com/v21.0/{bot.FB_PAGE_ID}/videos"
    with open(video_path,"rb") as f:
        r = requests.post(url,
            data={"access_token":bot.FB_PAGE_TOKEN,"description":desc},
            files={"source":("reel.mp4",f,"video/mp4")},
            timeout=240)
    ok = "id" in r.json()
    if not ok: print("[FB] Error:", r.json())
    return ok


def post_instagram(video_path, caption):
    token, ig_id = bot.FB_PAGE_TOKEN, bot.IG_USER_ID
    fsize = os.path.getsize(video_path)
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media",
        params={"media_type":"REELS","upload_type":"resumable",
                "caption":caption,"share_to_feed":"true","access_token":token},
        timeout=30)
    d = r.json()
    if "id" not in d: print("[IG] Container error:", d); return False
    cid = d["id"]; up_url = d.get("uri")
    if not up_url: print("[IG] No URI"); return False
    with open(video_path,"rb") as f: vb = f.read()
    up = requests.post(up_url,
        headers={"Authorization":f"OAuth {token}","offset":"0","file_size":str(fsize)},
        data=vb, timeout=240)
    if up.status_code not in (200,201):
        print("[IG] Upload error:", up.text[:200]); return False
    print("[IG] Processing...")
    for i in range(20):
        time.sleep(10)
        st = requests.get(f"https://graph.facebook.com/v21.0/{cid}",
            params={"fields":"status_code","access_token":token},timeout=20).json()
        sc = st.get("status_code","")
        print(f"[IG] {i+1}/20: {sc}")
        if sc == "FINISHED": break
        if sc == "ERROR": print("[IG] Error:", st); return False
    else: print("[IG] Timeout"); return False
    pub = requests.post(f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
        params={"creation_id":cid,"access_token":token},timeout=30)
    ok = "id" in pub.json()
    if not ok: print("[IG] Publish error:", pub.json())
    return ok


def post_youtube(video_path, title, price, discount, buy_link,
                  features=None, max_tries=3):
    """Upload to YouTube Shorts using google-api-python-client (most reliable)."""
    if not YOUTUBE_REFRESH_TOKEN:
        print("[YT] No YOUTUBE_REFRESH_TOKEN — skipping")
        return False

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError
    except ImportError as e:
        print(f"[YT] google-api-python-client not installed: {e}")
        return False

    sl      = bot.shorten_url(bot.clean_affiliate_url(buy_link))
    title_s = yt_title(title, price, discount)
    desc    = build_caption(title, price, discount, None, None, sl,
                             platform="youtube", features=features)
    tags    = ["AmazonDeals","LootDeals","AmazonIndia","Shorts","BazaarBuddy",
               "DealAlert","IndiaDeals","OnlineShopping","FlashSale",
               "AmazonSale","DealOfTheDay","BestDeals"]

    # Build credentials and force-refresh to get a valid access token
    try:
        from google.auth.transport.requests import Request as GoogleRequest
    except ImportError as e:
        print(f"[YT] google-auth not installed: {e}")
        return False

    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"],
    )
    try:
        creds.refresh(GoogleRequest())
        print(f"[YT] Token refreshed OK, expires: {creds.expiry}")
    except Exception as e:
        print(f"[YT] Token refresh FAILED: {e}")
        return False

    for attempt in range(1, max_tries+1):
        print(f"[YT] Upload attempt {attempt}/{max_tries}...")
        try:
            youtube = build("youtube", "v3", credentials=creds,
                            cache_discovery=False)
            body = {
                "snippet": {
                    "title": title_s,
                    "description": desc,
                    "tags": tags,
                    "categoryId": "26",
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                    "madeForKids": False,
                },
            }
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True,
                chunksize=5 * 1024 * 1024,  # 5 MB chunks
            )
            insert_req = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = None
            while response is None:
                status, response = insert_req.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f"[YT] Uploading... {pct}%")
            vid_id = response.get("id", "")
            print(f"[YT] ✅ https://youtube.com/shorts/{vid_id}")
            return vid_id or True

        except HttpError as e:
            print(f"[YT] HttpError {attempt}: {e.status_code} — {e.content[:300]}")
            if e.status_code in (400, 403):
                return False  # don't retry auth/quota errors
            time.sleep(15 * attempt)
        except Exception as e:
            print(f"[YT] Exception {attempt}: {e}")
            time.sleep(15 * attempt)
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════
FALLBACK = [
    ("boAt Rockerz 450 Wireless Bluetooth Headphones", "₹1,299",
     "https://www.amazon.in/dp/B07QFR85LP?tag=dattatrey07-21",
     "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=900",
     "https://www.amazon.in/dp/B07QFR85LP"),
    ("Xiaomi Power Bank 3i 20000mAh 18W Fast Charge", "₹1,499",
     "https://www.amazon.in/dp/B07ZY4QRPF?tag=dattatrey07-21",
     "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=900",
     "https://www.amazon.in/dp/B07ZY4QRPF"),
    ("Portronics Toad 23 Wireless Mouse", "₹499",
     "https://www.amazon.in/dp/B08FXNJKTR?tag=dattatrey07-21",
     "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=900",
     "https://www.amazon.in/dp/B08FXNJKTR"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def post_daily_reel():
    print("[REEL] ══════════ Daily Reel Bot v5 ══════════")

    # 1 — Scrape
    products = None
    for attempt in range(3):
        try:
            products = bot.scrape_products()
            if products: break
        except Exception as e:
            print(f"[REEL] Scrape exception {attempt+1}: {e}")
        time.sleep(8)

    if not products:
        print("[REEL] Scraping failed — using fallback products")
        products = list(FALLBACK)

    title, price, affiliate_link, image_url, base_link = random.choice(products)

    try:   affiliate_link = bot.clean_affiliate_url(affiliate_link)
    except Exception: pass

    # 2 — Details + features
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

    short_link = affiliate_link
    try:   short_link = bot.shorten_url(affiliate_link)
    except Exception: pass

    print(f"[REEL] Title   : {title[:70]}")
    print(f"[REEL] Price   : {price}  Discount: {discount}")
    print(f"[REEL] Feat    : {features}")
    print(f"[REEL] Link    : {short_link}")

    # 3 — Captions
    tg_cap = build_caption(title, price, discount, rating, reviews,
                            affiliate_link, platform="telegram", features=features)
    ig_cap = build_caption(title, price, discount, rating, reviews,
                            short_link, platform="instagram", features=features)

    # 4 — Video (2 attempts)
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
        print("[REEL] ❌ Video creation failed — aborting")
        return

    # 5 — Post
    res = {}

    print("\n[REEL] ── Telegram...")
    try:    res["tg"] = post_telegram(video_path, tg_cap)
    except Exception as e: print(f"[TG] {e}"); res["tg"] = False
    print(f"  Telegram  : {'✅' if res['tg'] else '❌'}")
    time.sleep(4)

    print("\n[REEL] ── Facebook...")
    try:    res["fb"] = post_facebook(video_path, ig_cap)
    except Exception as e: print(f"[FB] {e}"); res["fb"] = False
    print(f"  Facebook  : {'✅' if res['fb'] else '❌'}")
    time.sleep(4)

    print("\n[REEL] ── Instagram...")
    try:    res["ig"] = post_instagram(video_path, ig_cap)
    except Exception as e: print(f"[IG] {e}"); res["ig"] = False
    print(f"  Instagram : {'✅' if res['ig'] else '❌'}")
    time.sleep(4)

    print("\n[REEL] ── YouTube Shorts...")
    yt_r = False
    try:    yt_r = post_youtube(video_path, title, price, discount,
                                 affiliate_link, features=features)
    except Exception as e: print(f"[YT] {e}")
    res["yt"] = bool(yt_r)
    print(f"  YouTube   : {'✅' if res['yt'] else '❌'}")

    try:    os.unlink(video_path)
    except Exception: pass

    print(f"\n[REEL] ══ DONE  TG={res['tg']} FB={res['fb']} "
          f"IG={res['ig']} YT={res['yt']} ══")
    return res


if __name__ == "__main__":
    post_daily_reel()
