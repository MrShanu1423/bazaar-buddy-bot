"""
Bazaar Buddy Loot Deals — Auto Posting Web App
Toggle ON/OFF auto-posting to Telegram + Facebook + Instagram every 20 minutes.
Runs 24/7 when deployed (even if your laptop is off).
"""
import os
import json
import time
import threading
from flask import Flask, render_template, jsonify, request

import bot

app = Flask(__name__)

STATE_FILE = "bot_state.json"
POST_INTERVAL_SECONDS = 1200  # 20 minutes


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "enabled": True,
        "last_post": None,
        "last_result": None,
        "next_post_at": None,
        "stats": {"telegram": 0, "facebook": 0, "instagram": 0, "total_rounds": 0},
        "history": []
    }


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"State save error: {e}")


_state_lock = threading.Lock()


def update_state(updater):
    with _state_lock:
        state = load_state()
        updater(state)
        save_state(state)
        return state


def background_loop():
    """Continuously check toggle state and post when enabled."""
    print("[BG] Background posting loop started")
    while True:
        try:
            state = load_state()
            if state.get("enabled"):
                print(f"[BG] Toggle ON — posting round at {time.strftime('%H:%M:%S')}")
                result = bot.post_one_round()
                print(f"[BG] Round done: TG={result['telegram']} FB={result['facebook']} IG={result['instagram']}")

                def upd(s):
                    s["last_post"] = result["timestamp"]
                    s["last_result"] = result
                    s["next_post_at"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + POST_INTERVAL_SECONDS))
                    s["stats"]["total_rounds"] = s["stats"].get("total_rounds", 0) + 1
                    if result["telegram"]:
                        s["stats"]["telegram"] = s["stats"].get("telegram", 0) + 1
                    if result["facebook"]:
                        s["stats"]["facebook"] = s["stats"].get("facebook", 0) + 1
                    if result["instagram"]:
                        s["stats"]["instagram"] = s["stats"].get("instagram", 0) + 1
                    history = s.get("history", [])
                    history.insert(0, {
                        "time": result["timestamp"],
                        "title": result["title"][:80],
                        "telegram": result["telegram"],
                        "facebook": result["facebook"],
                        "instagram": result["instagram"]
                    })
                    s["history"] = history[:20]
                update_state(upd)

                # Wait the full interval
                time.sleep(POST_INTERVAL_SECONDS)
            else:
                # Toggle is OFF — check again every 10 seconds
                time.sleep(10)
        except Exception as e:
            print(f"[BG] Loop error: {e}")
            time.sleep(30)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/status")
def api_status():
    state = load_state()
    return jsonify(state)


@app.route("/api/toggle", methods=["POST"])
def api_toggle():
    def upd(s):
        s["enabled"] = not s.get("enabled", False)
        if s["enabled"]:
            s["next_post_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            s["next_post_at"] = None
    state = update_state(upd)
    return jsonify(state)


@app.route("/api/post-now", methods=["POST"])
def api_post_now():
    """Trigger a manual post immediately in a separate thread."""
    def do_post():
        result = bot.post_one_round()
        def upd(s):
            s["last_post"] = result["timestamp"]
            s["last_result"] = result
            s["stats"]["total_rounds"] = s["stats"].get("total_rounds", 0) + 1
            if result["telegram"]: s["stats"]["telegram"] = s["stats"].get("telegram", 0) + 1
            if result["facebook"]: s["stats"]["facebook"] = s["stats"].get("facebook", 0) + 1
            if result["instagram"]: s["stats"]["instagram"] = s["stats"].get("instagram", 0) + 1
            history = s.get("history", [])
            history.insert(0, {
                "time": result["timestamp"],
                "title": result["title"][:80],
                "telegram": result["telegram"],
                "facebook": result["facebook"],
                "instagram": result["instagram"]
            })
            s["history"] = history[:20]
        update_state(upd)
    threading.Thread(target=do_post, daemon=True).start()
    return jsonify({"started": True})


# Start the background posting loop in a daemon thread
_bg_started = False
_bg_lock = threading.Lock()

def ensure_background():
    global _bg_started
    with _bg_lock:
        if not _bg_started:
            t = threading.Thread(target=background_loop, daemon=True)
            t.start()
            _bg_started = True

ensure_background()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
