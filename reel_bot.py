"""
Bazaar Buddy — Daily Reel Bot (v3 — Crash-Proof + Cinematic)
============================================================
* 9:16 vertical Short/Reel for YouTube, Instagram, Facebook & Telegram
* 3D deep-space frame:  stars · hex grid · Ken Burns zoom · neon glows
* WHY BUY section:  product features rendered as glowing pill bullets
* Background music  (10 download sources  →  synthetic fallback)
* Sound-effect layer (cash-register ding on price reveal via ffmpeg)
* Animated text overlays fade/slide in across 30-second timeline
* Every function is individually guarded — one crash never kills the run
* Final Telegram report: shows per-platform result + video link
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

import requests
from PIL import (Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont)

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

# ─── Canvas ───────────────────────────────────────────────────────────────────
W, H = 1080, 1920   # 9:16 vertical

# ─── Palette ─────────────────────────────────────────────────────────────────
C_BG1    = (6,   4,  22)
C_BG2    = (18,  8,  52)
C_NEON   = (255, 40, 100)
C_GOLD   = (255, 195,  0)
C_CYAN   = (0,  220, 255)
C_PURPLE = (160, 40, 255)
C_WHITE  = (255, 255, 255)
C_LIME   = (80,  255, 120)
C_ORANGE = (255, 120,  20)


# ═══════════════════════════════════════════════════════════════════════════════
# DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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


BOLD_FONT_PATH = next(
    (p for p in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ] if os.path.exists(p)),
    ""
)


def gradient_rect(draw, x0, y0, x1, y1, top_col, bot_col):
    h = y1 - y0
    for dy in range(h):
        t = dy / max(h - 1, 1)
        r = int(top_col[0] + t * (bot_col[0] - top_col[0]))
        g = int(top_col[1] + t * (bot_col[1] - top_col[1]))
        b = int(top_col[2] + t * (bot_col[2] - top_col[2]))
        draw.line([(x0, y0 + dy), (x1, y0 + dy)], fill=(r, g, b))


def gradient_bg(draw, w, h, top, bot):
    gradient_rect(draw, 0, 0, w, h, top, bot)


def draw_grid_lines(draw, w, h, color=(35, 18, 75), spacing=80):
    vp_x, vp_y = w // 2, h // 3
    for i in range(12):
        y = h // 2 + i * spacing
        if y < h:
            draw.line([(0, y), (w, y)], fill=color, width=1)
    for x in range(0, w + 1, spacing):
        draw.line([(vp_x, vp_y), (x, h)], fill=color, width=1)


def draw_stars(draw, count=140, seed=7):
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, W)
        y = rng.randint(0, H * 2 // 3)
        r = rng.choice([1, 1, 1, 2, 2, 3])
        b = rng.randint(150, 255)
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(b, b, b))


def draw_hexagons(draw, seed=42):
    rng = random.Random(seed)
    colors = [C_NEON, C_CYAN, C_PURPLE, C_GOLD, C_LIME]
    for _ in range(14):
        cx = rng.randint(0, W)
        cy = rng.randint(0, H // 2)
        r  = rng.randint(18, 60)
        col = rng.choice(colors)
        pts = [(cx + r * math.cos(math.radians(60*i - 30)),
                cy + r * math.sin(math.radians(60*i - 30))) for i in range(6)]
        draw.polygon(pts, outline=col)


def neon_text(draw, xy, text, font, fill, glow=None, anchor="mm"):
    gc = glow or fill
    x, y = xy
    for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,-4),(0,4),(-4,0),(4,0)]:
        faded = tuple(max(0, v // 4) for v in gc[:3])
        draw.text((x+dx, y+dy), text, font=font, fill=faded, anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def pill_badge(draw, cx, cy, text, font, bg, fg):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        px, py = 40, 18
        x0, y0 = cx-tw//2-px, cy-th//2-py
        x1, y1 = cx+tw//2+px, cy+th//2+py
        draw.rounded_rectangle([x0+4, y0+4, x1+4, y1+4], radius=50, fill=(0,0,0))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=50, fill=bg)
        draw.text((cx, cy), text, font=font, fill=fg, anchor="mm")
        return y1
    except Exception:
        return cy + 60


def glowing_border(draw, x0, y0, x1, y1, color, radius=18):
    for off in [9, 6, 3, 1]:
        faded = tuple(max(0, int(v * off / 9)) for v in color[:3])
        draw.rounded_rectangle([x0-off, y0-off, x1+off, y1+off],
                                radius=radius+off, outline=faded, width=2)


def paste_product_image(canvas, image_url, box_y0, box_y1):
    """Download + paste product image with white card, glow border & reflection."""
    try:
        resp = requests.get(image_url, headers=bot.HEADERS, timeout=18)
        resp.raise_for_status()
        prod = Image.open(io.BytesIO(resp.content)).convert("RGBA")

        max_w, max_h = W - 80, box_y1 - box_y0 - 30
        prod.thumbnail((max_w, max_h), Image.LANCZOS)

        pad = 18
        card = Image.new("RGB", (prod.width + pad*2, prod.height + pad*2), (255,255,255))
        card.paste(prod, (pad, pad), mask=prod)

        cx = (W - card.width) // 2
        cy = box_y0 + (box_y1 - box_y0 - card.height) // 2

        # Subtle reflection
        ref_h = card.height // 4
        ref = card.crop((0, card.height-ref_h, card.width, card.height))
        ref = ref.transpose(Image.FLIP_TOP_BOTTOM)
        ref = ref.filter(ImageFilter.GaussianBlur(4))
        ref = ImageEnhance.Brightness(ref).enhance(0.18)
        mask = Image.new("L", ref.size, 0)
        for i in range(ref_h):
            mask.paste(max(0, int(50*(1-i/ref_h))), (0, i, ref.width, i+1))
        ref.putalpha(mask)
        rp = (cx, cy + card.height + 2)
        if rp[1] + ref.height < H:
            canvas.paste(ref, rp, mask=ref)

        canvas.paste(card, (cx, cy))
        d = ImageDraw.Draw(canvas)
        glowing_border(d, cx, cy, cx+card.width, cy+card.height, C_CYAN, radius=14)
        return True
    except Exception as e:
        print(f"[REEL] Image error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# FRAME BUILDER  —  the static poster baked into every video frame
# ═══════════════════════════════════════════════════════════════════════════════

def build_frame(title, price, discount, image_url, short_link,
                features=None, rating=None, reviews=None):
    img  = Image.new("RGB", (W, H), C_BG1)
    draw = ImageDraw.Draw(img)

    # ── Background scene ──────────────────────────────────────────────────
    gradient_bg(draw, W, H, C_BG1, C_BG2)
    draw_grid_lines(draw, W, H)
    draw_stars(draw, count=130)
    draw_hexagons(draw)

    # Radial glow from top-center
    for r_size in range(300, 0, -40):
        alpha = int(18 * (300 - r_size) / 300)
        col = tuple(min(255, v + alpha) for v in C_BG1)
        draw.ellipse([W//2 - r_size, -r_size//2,
                      W//2 + r_size, r_size//2 + 100],
                     fill=col)

    # Corner accent triangles
    for pts in [[(0,0),(200,0),(0,200)], [(W,0),(W-200,0),(W,200)],
                [(0,H),(200,H),(0,H-200)], [(W,H),(W-200,H),(W,H-200)]]:
        draw.polygon(pts, fill=(70, 0, 160))

    # ── Top banner ────────────────────────────────────────────────────────
    gradient_rect(draw, 0, 0, W, 150, (140, 0, 80), (90, 0, 180))
    f_banner = load_font(48, bold=True)
    neon_text(draw, (W//2, 75), "🔥  BAZAAR BUDDY LOOT DEALS  🔥",
              f_banner, C_WHITE, C_NEON)
    for off, col in [(0, C_GOLD), (2, C_ORANGE)]:
        draw.rectangle([0, 150+off, W, 154+off], fill=col)

    # ── Product image ─────────────────────────────────────────────────────
    IMG_TOP = 162
    has_feat = bool(features)
    IMG_BOT  = 820 if has_feat else 990
    paste_product_image(img, image_url, IMG_TOP, IMG_BOT)
    draw = ImageDraw.Draw(img)   # refresh after paste

    # DEAL badge (top-right)
    f_sm = load_font(26, bold=True)
    pill_badge(draw, W-88, IMG_TOP+44, "✨ HOT DEAL", f_sm, C_GOLD, (8,4,20))

    # Rating stars (top-left)
    if rating:
        try:
            stars = int(float(rating))
            star_str = "★" * stars + "☆" * (5-stars)
            f_star = load_font(24, bold=True)
            draw.rounded_rectangle([14, IMG_TOP+14, 200, IMG_TOP+52],
                                    radius=8, fill=(10,5,30))
            draw.text((20, IMG_TOP+18), f"{star_str} {rating}", font=f_star,
                      fill=C_GOLD)
        except Exception:
            pass

    # ── WHY BUY — Feature bullets ──────────────────────────────────────────
    if has_feat:
        f_feat = load_font(27)
        fy = IMG_BOT + 8
        icons = ["⚡", "✅", "🔥", "💡"]
        for i, feat in enumerate(features[:4]):
            icon = icons[i % 4]
            # Glowing pill per feature
            draw.rounded_rectangle([16, fy, W-16, fy+42],
                                    radius=12, fill=(16, 9, 48))
            draw.rounded_rectangle([16, fy, W-16, fy+42],
                                    radius=12, outline=(90, 45, 160), width=1)
            # Left accent bar
            draw.rounded_rectangle([16, fy, 22, fy+42],
                                    radius=4, fill=C_CYAN)
            draw.text((42, fy+8), f"{icon} {feat}", font=f_feat, fill=C_WHITE)
            fy += 48
        panel_top = fy + 6
    else:
        panel_top = 1005

    # ── Bottom info panel ─────────────────────────────────────────────────
    gradient_rect(draw, 0, panel_top, W, H, (12, 6, 40), (6, 3, 18))
    for off, col in [(0, C_CYAN), (2, (0,130,160)), (4, (0,60,100))]:
        draw.rectangle([0, panel_top+off, W, panel_top+3+off], fill=col)

    y = panel_top + 16

    # Product title
    f_title = load_font(40, bold=True)
    wrapped = textwrap.wrap(title[:160], width=25)
    for line in wrapped[:3]:
        neon_text(draw, (W//2, y+24), line, f_title, C_WHITE, C_CYAN)
        y += 56
    y += 10

    # Discount badge
    if discount:
        f_disc = load_font(48, bold=True)
        y = pill_badge(draw, W//2, y+44,
                       f"🏷️  {discount} OFF  —  GRAB NOW!",
                       f_disc, C_NEON, C_WHITE) + 20

    # Price
    if price:
        f_price = load_font(60, bold=True)
        neon_text(draw, (W//2, y+36), f"💰 {price}", f_price, C_GOLD, C_GOLD)
        y += 82

    # Reviews
    if reviews:
        f_rev = load_font(26)
        draw.text((W//2, y+10), f"⭐ {rating}/5  •  {reviews} reviews",
                  font=f_rev, fill=(200,200,200), anchor="mm")
        y += 38

    # Affiliate link box
    f_link = load_font(33)
    link_y = max(y+16, H - 370)
    draw.rounded_rectangle([30, link_y-24, W-30, link_y+50],
                            radius=16, fill=(0, 24, 60))
    draw.rounded_rectangle([30, link_y-24, W-30, link_y+50],
                            radius=16, outline=C_CYAN, width=2)
    neon_text(draw, (W//2, link_y+14), f"🛒 {short_link}",
              f_link, C_CYAN, C_CYAN)

    # CTA button
    f_cta = load_font(44, bold=True)
    cta_y = link_y + 100
    pill_badge(draw, W//2, cta_y, "👆  TAP LINK — BUY NOW  👆",
               f_cta, C_GOLD, (8,4,16))

    # ── Footer strip ──────────────────────────────────────────────────────
    strip_y = H - 128
    draw.rectangle([0, strip_y, W, H], fill=(8, 3, 28))
    draw.rectangle([0, strip_y, W, strip_y+3], fill=C_NEON)
    f_sub = load_font(28, bold=True)
    f_fol = load_font(24)
    neon_text(draw, (W//2, strip_y+26),
              "🔔 SUBSCRIBE  ▸  YouTube: @BazaarBuddyLootDeals",
              f_sub, C_GOLD, C_GOLD)
    neon_text(draw, (W//2, strip_y+58),
              "❤️ Instagram: @bazaarbuddylootdeals  •  📢 Telegram: t.me/BazaarBuddyLootDeals",
              f_fol, C_CYAN, C_CYAN)
    neon_text(draw, (W//2, strip_y+92),
              "🛍️ Daily Amazon India Deals  •  100% Free",
              f_fol, (160,120,255), C_PURPLE)

    return img


# ═══════════════════════════════════════════════════════════════════════════════
# MUSIC — 12 download sources + layered synthetic fallback
# ═══════════════════════════════════════════════════════════════════════════════

MUSIC_URLS = [
    # Pixabay royalty-free tracks (upbeat / electronic)
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
    """Try each URL until one works. Returns path or None."""
    random.shuffle(MUSIC_URLS)
    music_path = tempfile.mktemp(suffix=".mp3")
    for url in MUSIC_URLS:
        try:
            r = requests.get(url, timeout=25,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 20_000:
                with open(music_path, "wb") as f:
                    f.write(r.content)
                print(f"[REEL] Music OK ({len(r.content)//1024} KB)")
                return music_path
        except Exception as e:
            print(f"[REEL] Music miss: {e}")
    return None


def generate_music_ffmpeg(duration=32):
    """
    Layered synthetic upbeat track:
    Bass line + mid melody + high shimmer + kick beat.
    """
    out = tempfile.mktemp(suffix=".mp3")
    bpm = 128
    beat = 60 / bpm
    expr = (
        # Sub-bass pulse (kick pattern)
        f"0.20*sin(2*PI*60*t)*exp(-8*mod(t,{beat:.4f}))"
        # Bass note
        f"+0.18*sin(2*PI*110*t)"
        # Mid melody (rises every 4 beats)
        f"+0.15*sin(2*PI*330*(1+0.015*sin(2*PI*0.5*t))*t)"
        # High lead
        f"+0.10*sin(2*PI*660*t*((floor(t*2)%2)*0.5+0.75))"
        # Shimmer
        f"+0.06*sin(2*PI*1320*t)*sin(2*PI*4*t)"
        # Transient clicks (snare approximation)
        f"+0.08*sin(2*PI*200*t)*exp(-40*mod(t,{beat*2:.4f}))"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':s=44100:d={duration}",
        "-af", (
            f"afade=t=in:st=0:d=2,"
            f"afade=t=out:st={max(1,duration-2)}:d=2,"
            f"highpass=f=50,lowpass=f=9000,"
            f"compand=0.3|0.3:1|1:-90/-60|-60/-40|-40/-30|-20/-20:6:0:-90:0.2,"
            f"volume=0.75"
        ),
        "-q:a", "3", out,
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=60)
    if res.returncode == 0:
        print("[REEL] Synthetic music generated")
        return out
    print("[REEL] Synthetic music failed:", res.stderr.decode()[-200:])
    return None


def generate_sfx_cash_register():
    """
    Synthesise a short cash-register 'ding' (used at price reveal t=6).
    Returns path to a short wav/mp3 or None.
    """
    out = tempfile.mktemp(suffix=".mp3")
    expr = (
        "0.5*sin(2*PI*1400*t)*exp(-5*t)"
        "+0.3*sin(2*PI*1800*t)*exp(-7*t)"
        "+0.2*sin(2*PI*2200*t)*exp(-10*t)"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':s=44100:d=0.8",
        "-q:a", "4", out,
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=30)
    return out if res.returncode == 0 else None


# ═══════════════════════════════════════════════════════════════════════════════
# VIDEO RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

def _safe(s, max_len=58):
    """Strip characters that break ffmpeg drawtext filter."""
    return (s or "")[:max_len].replace("'","").replace('"',"").replace("\\","").replace(":","")


def _fade(start, end):
    return f"alpha='if(lt(t,{start}),0,if(lt(t,{end}),(t-{start})/({end}-{start}),1))'"


def _slide_up(y_final, start, end):
    """Slide text up from y_final+60 to y_final while fading in."""
    dy = f"(({y_final}+60)*max(0,1-(t-{start})/({end}-{start}))+{y_final}*min(1,(t-{start})/({end}-{start})))"
    return f"y='{dy}'"


def render_video(frame_path, music_path, sfx_path, title, price, discount,
                 short_link, features, duration=32):
    """
    Build the animated MP4.
    Falls back to a simpler render if the complex filter fails.
    """
    out = tempfile.mktemp(suffix=".mp4")
    fps = 30
    total = duration * fps

    fontfile = BOLD_FONT_PATH or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # ── Video filter: Ken Burns zoom + text overlays ───────────────────────
    zoom_vf = (
        f"zoompan=z='min(1.0+0.12*on/{total},1.12)'"
        f":x='iw/2-(iw/zoom/2)+sin(on/{fps}*0.25)*10'"
        f":y='ih/2-(ih/zoom/2)'"
        f":d={total}:s={W}x{H}:fps={fps}"
    )

    # Text overlays (safe-sanitised)
    title_safe  = _safe(title, 45)
    price_safe  = _safe(price)
    disc_safe   = _safe(discount)
    link_safe   = _safe(short_link, 55)

    text_filters = []

    # t=0 → 2 : Channel name
    if fontfile:
        text_filters.append(
            f"drawtext=text='BAZAAR BUDDY LOOT DEALS'"
            f":fontfile={fontfile}:fontsize=42:fontcolor=0xFFFFFF"
            f":x=(w-tw)/2:y=38:{_fade(0,1.5)}"
            f":shadowcolor=0xFF2864:shadowx=3:shadowy=3"
        )
        # t=1.5 → 3.5 : Deal alert
        text_filters.append(
            f"drawtext=text='🔥 HOT DEAL ALERT 🔥'"
            f":fontfile={fontfile}:fontsize=50:fontcolor=0xFFD700"
            f":x=(w-tw)/2:y=h-380:{_fade(1.5,3.5)}"
            f":shadowcolor=0xFF2864:shadowx=4:shadowy=4"
        )
        # t=5 → 7.5 : Title (slide up)
        if title_safe:
            text_filters.append(
                f"drawtext=text='{title_safe}'"
                f":fontfile={fontfile}:fontsize=38:fontcolor=0xFFFFFF"
                f":x=(w-tw)/2:{_slide_up(H-310, 5, 7)}:{_fade(5,7)}"
                f":shadowcolor=0x000000:shadowx=3:shadowy=3"
            )
        # t=7 → 9 : Price (bigger, gold)
        if price_safe:
            text_filters.append(
                f"drawtext=text='💰 {price_safe}'"
                f":fontfile={fontfile}:fontsize=68:fontcolor=0xFFD700"
                f":x=(w-tw)/2:y=h-260:{_fade(7,9)}"
                f":shadowcolor=0x000000:shadowx=5:shadowy=5"
            )
        # t=9 → 11 : Discount
        if disc_safe:
            text_filters.append(
                f"drawtext=text='{disc_safe} OFF — LIMITED TIME'"
                f":fontfile={fontfile}:fontsize=46:fontcolor=0xFF2864"
                f":x=(w-tw)/2:y=h-195:{_fade(9,11)}"
                f":shadowcolor=0x000000:shadowx=3:shadowy=3"
            )
        # t=12 → 14 : Link (pulsing cyan)
        if link_safe:
            text_filters.append(
                f"drawtext=text='BUY NOW ➜ {link_safe}'"
                f":fontfile={fontfile}:fontsize=36:fontcolor=0x00DCFF"
                f":x=(w-tw)/2:y=h-135:{_fade(12,14)}"
                f":shadowcolor=0x000000:shadowx=2:shadowy=2"
            )
        # t=20 → 22 : Subscribe CTA at the very end
        text_filters.append(
            f"drawtext=text='SUBSCRIBE for Daily Deals!'"
            f":fontfile={fontfile}:fontsize=44:fontcolor=0xFFD700"
            f":x=(w-tw)/2:y=h/2:{_fade(20,22)}"
            f":shadowcolor=0xFF2864:shadowx=4:shadowy=4"
        )

    vf = zoom_vf
    if text_filters:
        vf += "," + ",".join(text_filters)

    def _audio_chain(music_in, sfx_in, dur):
        """Build the complex audio filter string."""
        if music_in and sfx_in:
            return (
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{dur},"
                f"afade=t=in:st=0:d=2,afade=t=out:st={dur-2}:d=2,"
                f"volume=0.5[music];"
                f"[2:a]adelay=6000|6000,volume=1.2[sfx];"
                f"[music][sfx]amix=inputs=2:duration=first[aout]"
            ), True
        elif music_in:
            return (
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{dur},"
                f"afade=t=in:st=0:d=2,afade=t=out:st={dur-2}:d=2,"
                f"volume=0.55[aout]"
            ), False
        return None, False

    def _build_cmd(frame_p, music_p, sfx_p, vf_str, out_p, dur):
        inputs = ["-loop", "1", "-i", frame_p]
        if music_p and os.path.exists(music_p):
            inputs += ["-i", music_p]
        if sfx_p and os.path.exists(sfx_p):
            inputs += ["-i", sfx_p]

        has_music = bool(music_p and os.path.exists(music_p))
        has_sfx   = bool(sfx_p and os.path.exists(sfx_p))

        cmd = ["ffmpeg", "-y"] + inputs

        if has_music:
            audio_flt, dual = _audio_chain(music_p, sfx_p if has_sfx else None, dur)
            cmd += [
                "-filter_complex",
                    f"[0:v]{vf_str}[vout];"
                    f"{audio_flt}",
                "-map", "[vout]",
                "-map", "[aout]",
                "-t", str(dur),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-r", str(fps),
                "-movflags", "+faststart",
                out_p,
            ]
        else:
            cmd += [
                "-filter_complex", f"[0:v]{vf_str}[vout]",
                "-map", "[vout]",
                "-t", str(dur),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-movflags", "+faststart",
                out_p,
            ]
        return cmd

    # First attempt — full quality
    cmd = _build_cmd(frame_path, music_path, sfx_path, vf, out, duration)
    print("[REEL] Rendering full-quality video...")
    res = subprocess.run(cmd, capture_output=True, timeout=600)

    if res.returncode != 0:
        print("[REEL] Full render failed, trying simple fallback...")
        out2 = tempfile.mktemp(suffix=".mp4")
        simple_vf = zoom_vf
        cmd2 = _build_cmd(frame_path, music_path, None, simple_vf, out2, duration)
        res2 = subprocess.run(cmd2, capture_output=True, timeout=300)
        if res2.returncode == 0:
            print("[REEL] Simple render OK")
            return out2
        # Ultra-simple fallback — just encode the image as video, no animations
        print("[REEL] Trying ultra-simple fallback...")
        out3 = tempfile.mktemp(suffix=".mp4")
        cmd3 = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-vf", f"scale={W}:{H}",
            "-movflags", "+faststart",
            out3,
        ]
        res3 = subprocess.run(cmd3, capture_output=True, timeout=120)
        if res3.returncode == 0:
            print("[REEL] Ultra-simple fallback OK")
            return out3
        print("[REEL] All renders failed:", res3.stderr.decode()[-400:])
        return None

    kb = os.path.getsize(out) // 1024
    print(f"[REEL] ✅ Video ready ({kb} KB)")
    return out


def create_reel_video(title, price, discount, image_url, short_link,
                       features=None, rating=None, reviews=None, duration=32):
    frame_img  = build_frame(title, price, discount, image_url, short_link,
                              features=features, rating=rating, reviews=reviews)
    frame_path = tempfile.mktemp(suffix=".jpg")
    frame_img.save(frame_path, quality=96)
    print("[REEL] Poster frame saved.")

    print("[REEL] Downloading music...")
    music_path = download_music()
    if not music_path:
        music_path = generate_music_ffmpeg(duration)

    print("[REEL] Generating cash-register SFX...")
    sfx_path = generate_sfx_cash_register()

    video_path = render_video(frame_path, music_path, sfx_path,
                               title, price, discount, short_link, features, duration)

    for p in [frame_path, music_path, sfx_path]:
        try:
            if p and os.path.exists(p):
                os.unlink(p)
        except Exception:
            pass

    return video_path


# ═══════════════════════════════════════════════════════════════════════════════
# SEO CAPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_HASHTAGS = (
    "#Shorts #Reels #AmazonIndia #LootDeals #AmazonDeals #OnlineShopping "
    "#TechDeals #IndiaDeals #BestDeals #BuyNow #DealAlert #DiscountDeals "
    "#BazaarBuddy #AmazonSale #FlashSale #DealOfTheDay #SaleAlert "
    "#ShoppingDeals #GrabNow #AmazonFinds #DealHunter #SaveMoney "
    "#IndiaOnlineShopping #AmazonOffer #ShoppingIndia"
)


def build_seo_caption(title, price, discount, rating, reviews, link,
                       platform="instagram", features=None):
    deal = f"🔥 {discount} OFF — Limited Time!" if discount else "🔥 Hot Deal Alert!"
    p_ln = f"💰 Only {price} on Amazon India" if price else ""
    r_ln = f"⭐ {rating}/5 • {reviews} reviews" if rating and reviews else ""

    feat_block = ""
    if features:
        feat_block = "\n\n🎯 Why Buy?\n" + "\n".join(
            f"  ✅ {f}" for f in features[:4]
        )

    if platform == "telegram":
        return (
            f"🛒 <b>BUY NOW</b> 👉 <a href='{link}'>ORDER HERE ← CLICK</a>\n\n"
            f"🔥 <b>{title}</b>\n\n"
            f"{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + feat_block
            + f"\n\n✅ Amazon India Affiliate Deal\n🔗 {link}\n\n"
            f"📢 Daily deals on our channel!\n"
            f"👉 https://t.me/BazaarBuddyLootDeals"
        )

    if platform == "youtube":
        return (
            f"🛒 BUY NOW 👉 {link}\n"
            f"⬆️ CLICK ABOVE to grab this deal on Amazon India!\n\n"
            f"🔥 {title}\n\n"
            f"{deal}\n"
            + (f"{p_ln}\n" if p_ln else "")
            + (f"{r_ln}\n" if r_ln else "")
            + feat_block
            + f"\n\n✅ Amazon India Affiliate Deal (tag: dattatrey07-21)\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 SUBSCRIBE for daily Amazon India deals!\n"
            f"👉 https://www.youtube.com/@BazaarBuddyLootDeals\n"
            f"📢 Telegram ▸ https://t.me/BazaarBuddyLootDeals\n"
            f"❤️ Instagram ▸ @bazaarbuddylootdeals\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + _HASHTAGS
        )

    # Instagram / Facebook
    return (
        f"🛒 BUY NOW 👉 {link}\n\n"
        f"🔥 {title}\n\n"
        f"{deal}\n"
        + (f"{p_ln}\n" if p_ln else "")
        + (f"{r_ln}\n" if r_ln else "")
        + feat_block
        + f"\n\n👆 Tap link in caption to order!\n"
        f"❤️ Follow @bazaarbuddylootdeals for daily deals!\n\n"
        + _HASHTAGS
    )


def build_youtube_title(title, price, discount):
    disc = f"{discount} OFF | " if discount else ""
    pr   = f" ₹{price}" if price else ""
    return f"🔥 {disc}{title[:55]}{pr} | Amazon India Deal #Shorts"[:100]


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM POSTING  (each call is independently guarded in post_daily_reel)
# ═══════════════════════════════════════════════════════════════════════════════

def post_video_telegram(video_path, caption):
    url = f"https://api.telegram.org/bot{bot.BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": bot.CHAT_ID, "caption": caption,
                  "parse_mode": "HTML", "supports_streaming": True},
            files={"video": ("reel.mp4", f, "video/mp4")},
            timeout=180,
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
            timeout=240,
        )
    data = resp.json()
    ok = "id" in data
    if not ok:
        print("[REEL][FB] Error:", data)
    return ok


def post_reel_instagram(video_path, caption):
    token, ig_id = bot.FB_PAGE_TOKEN, bot.IG_USER_ID
    file_size = os.path.getsize(video_path)

    # Step 1 — create container
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media",
        params={"media_type": "REELS", "upload_type": "resumable",
                "caption": caption, "share_to_feed": "true",
                "access_token": token},
        timeout=30,
    )
    data = r.json()
    if "id" not in data:
        print("[REEL][IG] Container error:", data)
        return False
    container_id = data["id"]
    upload_url   = data.get("uri")
    if not upload_url:
        print("[REEL][IG] No URI")
        return False

    # Step 2 — upload bytes
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    up = requests.post(
        upload_url,
        headers={"Authorization": f"OAuth {token}",
                 "offset": "0", "file_size": str(file_size)},
        data=video_bytes,
        timeout=240,
    )
    if up.status_code not in (200, 201):
        print("[REEL][IG] Upload error:", up.text[:300])
        return False

    # Step 3 — wait for processing
    print("[REEL][IG] Waiting for Instagram to process...")
    for i in range(20):
        time.sleep(10)
        st = requests.get(
            f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=20,
        ).json()
        status = st.get("status_code", "")
        print(f"[REEL][IG] {i+1}/20: {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            print("[REEL][IG] Error:", st)
            return False
    else:
        print("[REEL][IG] Processing timeout")
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
    if not YOUTUBE_REFRESH_TOKEN:
        return None
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={"client_id": YOUTUBE_CLIENT_ID,
                  "client_secret": YOUTUBE_CLIENT_SECRET,
                  "refresh_token": YOUTUBE_REFRESH_TOKEN,
                  "grant_type": "refresh_token"},
            timeout=20,
        )
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[REEL][YT] Token error: {e}")
        return None


def post_video_youtube(video_path, title, price, discount, affiliate_link,
                        features=None, max_retries=3):
    clean_link = bot.clean_affiliate_url(affiliate_link)
    short_link = bot.shorten_url(clean_link)
    yt_title   = build_youtube_title(title, price, discount)
    yt_desc    = build_seo_caption(title, price, discount, None, None,
                                    short_link, platform="youtube",
                                    features=features)
    file_size  = os.path.getsize(video_path)

    for attempt in range(1, max_retries + 1):
        print(f"[REEL][YT] Upload attempt {attempt}/{max_retries}")
        access_token = get_youtube_access_token()
        if not access_token:
            print("[REEL][YT] No access token — skipping")
            return False

        try:
            init = requests.post(
                "https://www.googleapis.com/upload/youtube/v3/videos"
                "?uploadType=resumable&part=snippet,status",
                headers={"Authorization": f"Bearer {access_token}",
                         "Content-Type": "application/json",
                         "X-Upload-Content-Type": "video/mp4",
                         "X-Upload-Content-Length": str(file_size)},
                json={
                    "snippet": {
                        "title": yt_title,
                        "description": yt_desc,
                        "tags": ["AmazonDeals","LootDeals","AmazonIndia","Shorts",
                                 "IndiaShopping","BazaarBuddy","OnlineShopping",
                                 "DealAlert","FlashSale","BuyNow","DealOfTheDay",
                                 "AmazonOffer","IndiaDeals","TechDeals","ShopNow"],
                        "categoryId": "26",
                        "defaultLanguage": "en",
                    },
                    "status": {
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": False,
                    }
                },
                timeout=30,
            )

            if init.status_code not in (200, 201):
                print(f"[REEL][YT] Init failed {init.status_code}: {init.text[:200]}")
                time.sleep(8 * attempt)
                continue

            upload_url = init.headers.get("Location")
            if not upload_url:
                print("[REEL][YT] No upload URL")
                time.sleep(5)
                continue

            with open(video_path, "rb") as f:
                video_bytes = f.read()

            up = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4",
                         "Content-Length": str(file_size)},
                data=video_bytes,
                timeout=360,
            )

            if up.status_code in (200, 201):
                vid_id = up.json().get("id", "")
                print(f"[REEL][YT] ✅  https://youtube.com/shorts/{vid_id}")
                return vid_id or True

            print(f"[REEL][YT] Upload failed {up.status_code}: {up.text[:200]}")
            time.sleep(12 * attempt)

        except Exception as e:
            print(f"[REEL][YT] Exception attempt {attempt}: {e}")
            time.sleep(12 * attempt)

    print("[REEL][YT] All retries exhausted")
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM REPORT  — sends a success/failure summary to the channel
# ═══════════════════════════════════════════════════════════════════════════════

def send_report(results, title, price, discount, yt_id):
    def icon(v): return "✅" if v else "❌"
    yt_link = f"\n🎬 https://youtube.com/shorts/{yt_id}" if yt_id and yt_id is not True else ""
    msg = (
        f"📊 <b>Daily Reel Report</b>\n\n"
        f"<b>Product:</b> {title[:60]}\n"
        f"<b>Price:</b> {price}  <b>Discount:</b> {discount}\n\n"
        f"Telegram  {icon(results.get('tg'))}\n"
        f"Facebook  {icon(results.get('fb'))}\n"
        f"Instagram {icon(results.get('ig'))}\n"
        f"YouTube   {icon(results.get('yt'))}"
        + yt_link
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot.BOT_TOKEN}/sendMessage",
            data={"chat_id": bot.CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK PRODUCTS — used when Amazon scraping completely fails
# ═══════════════════════════════════════════════════════════════════════════════

FALLBACK_PRODUCTS = [
    (
        "boAt Rockerz 450 Bluetooth Headphones",
        "₹1,299",
        "https://www.amazon.in/dp/B07QFR85LP?tag=dattatrey07-21",
        "https://m.media-amazon.com/images/I/61PzTlnzGEL._SL1500_.jpg",
        "https://www.amazon.in/dp/B07QFR85LP",
    ),
    (
        "Mi Smart Band 7 Fitness Tracker",
        "₹2,799",
        "https://www.amazon.in/dp/B0B2Q5TGJP?tag=dattatrey07-21",
        "https://m.media-amazon.com/images/I/51jkrS-bqXL._SL1500_.jpg",
        "https://www.amazon.in/dp/B0B2Q5TGJP",
    ),
    (
        "Portronics 10000mAh Power Bank Fast Charging",
        "₹899",
        "https://www.amazon.in/dp/B09XYZFAKE?tag=dattatrey07-21",
        "https://m.media-amazon.com/images/I/61hFHpMNXsL._SL1500_.jpg",
        "https://www.amazon.in/s?k=portronics+power+bank",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def post_daily_reel():
    print("[REEL] ══════════ Daily Reel Job Started ══════════")

    # 1 — Scrape products (with fallback)
    products = None
    for attempt in range(3):
        try:
            products = bot.scrape_products()
            if products:
                break
            print(f"[REEL] Scrape attempt {attempt+1} returned 0 products, retrying...")
            time.sleep(10)
        except Exception as e:
            print(f"[REEL] Scrape exception attempt {attempt+1}: {e}")
            time.sleep(10)

    if not products:
        print("[REEL] Using fallback product list...")
        products = [
            (title, price, link, img, base)
            for title, price, link, img, base in FALLBACK_PRODUCTS
        ]

    title, price, affiliate_link, image_url, base_link = random.choice(products)

    # 2 — Clean link
    try:
        affiliate_link = bot.clean_affiliate_url(affiliate_link)
    except Exception:
        pass

    # 3 — Fetch details + features
    rating, reviews, seller, original_price, discount = "", "", "", "", ""
    features = []
    try:
        rating, reviews, seller, original_price, discount = bot.get_product_details(base_link)
    except Exception as e:
        print(f"[REEL] Details error: {e}")
    try:
        features = bot.get_product_features(base_link)
    except Exception as e:
        print(f"[REEL] Features error: {e}")

    # 4 — Shorten link
    short_link = affiliate_link
    try:
        short_link = bot.shorten_url(affiliate_link)
    except Exception:
        pass

    print(f"[REEL] Product  : {title[:80]}")
    print(f"[REEL] Price    : {price}  |  Discount: {discount}")
    print(f"[REEL] Rating   : {rating}  |  Reviews: {reviews}")
    print(f"[REEL] Features : {features}")
    print(f"[REEL] Link     : {short_link}")

    # 5 — Build captions
    tg_cap = build_seo_caption(title, price, discount, rating, reviews,
                                affiliate_link, platform="telegram",
                                features=features)
    ig_cap = build_seo_caption(title, price, discount, rating, reviews,
                                short_link, platform="instagram",
                                features=features)

    # 6 — Create video
    video_path = None
    for attempt in range(2):
        try:
            video_path = create_reel_video(
                title, price, discount, image_url, short_link,
                features=features, rating=rating, reviews=reviews,
                duration=32,
            )
            if video_path:
                break
            print(f"[REEL] Video attempt {attempt+1} returned None, retrying...")
        except Exception as e:
            print(f"[REEL] Video exception attempt {attempt+1}: {e}")
        time.sleep(5)

    if not video_path:
        print("[REEL] ❌ Video creation failed after 2 attempts — aborting.")
        return

    # 7 — Post to all platforms (each guarded independently)
    results = {}

    print("\n[REEL] ── Posting to Telegram...")
    try:
        results["tg"] = post_video_telegram(video_path, tg_cap)
    except Exception as e:
        print(f"[REEL][TG] Exception: {e}")
        results["tg"] = False
    print(f"[REEL] Telegram  : {'✅' if results['tg'] else '❌'}")
    time.sleep(5)

    print("\n[REEL] ── Posting to Facebook...")
    try:
        results["fb"] = post_video_facebook(video_path, ig_cap)
    except Exception as e:
        print(f"[REEL][FB] Exception: {e}")
        results["fb"] = False
    print(f"[REEL] Facebook  : {'✅' if results['fb'] else '❌'}")
    time.sleep(5)

    print("\n[REEL] ── Posting to Instagram...")
    try:
        results["ig"] = post_reel_instagram(video_path, ig_cap)
    except Exception as e:
        print(f"[REEL][IG] Exception: {e}")
        results["ig"] = False
    print(f"[REEL] Instagram : {'✅' if results['ig'] else '❌'}")
    time.sleep(5)

    print("\n[REEL] ── Uploading to YouTube Shorts...")
    yt_result = False
    try:
        yt_result = post_video_youtube(
            video_path, title, price, discount, affiliate_link, features=features)
        results["yt"] = bool(yt_result)
    except Exception as e:
        print(f"[REEL][YT] Exception: {e}")
        results["yt"] = False
    print(f"[REEL] YouTube   : {'✅' if results['yt'] else '❌'}")

    # 8 — Cleanup
    try:
        os.unlink(video_path)
    except Exception:
        pass

    # 9 — Send Telegram report
    send_report(results, title, price, discount,
                yt_result if isinstance(yt_result, str) else None)

    print(
        f"\n[REEL] ══════════ Done  TG={results['tg']}  FB={results['fb']}  "
        f"IG={results['ig']}  YT={results['yt']} ══════════"
    )
    return results


if __name__ == "__main__":
    post_daily_reel()
