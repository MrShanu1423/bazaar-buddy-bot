import requests
import time

BOT_TOKEN = "8608712234:AAEQIOKSBzTeDnIZeuVUg-3mobgbBIT_KVU"
CHAT_ID = "-1003706154836"

def send_message():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": "🔥 Bot running from Replit successfully!"
    }

    response = requests.post(url, data=data)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sent message, status: {response.status_code}")

while True:
    send_message()
    time.sleep(60)
