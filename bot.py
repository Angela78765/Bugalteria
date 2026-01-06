import os
import time
import json
from html import escape
import requests

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise RuntimeError("API_TOKEN environment variable is not set")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
API_URL = f"https://api.telegram.org/bot8465183620:AAFo-O8lqEG91o0xF-emAj5iplvvWqO1knA"

MAIN_MARKUP = {
    "keyboard": [
        [{"text": "Питання"}],
        [{"text": "Отримати реквізити"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

REKV_TEXT = (
    "<b>Реквізити для переказу</b>\n"
    "ПриватБанк: 1234 5678 0000 1111\n"
    "МоноБанк: 4444 5678 1234 5678\n"
    "IBAN: UA12 1234 5678 0000 1111 1234 5678\n"
)

waiting_ids = set()
offset = 0  # Для getUpdates

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(f"{API_URL}/sendMessage", data=data, timeout=10)
    except Exception as e:
        print("Error sending message:", e)

def build_welcome(user):
    name = ((user.get("first_name") or "") + " " + (user.get("last_name") or "")).strip() or "Друже"
    return f"<b>Ласкаво просимо, {escape(name)}!</b>\n\nОберіть дію за допомогою кнопок внизу."

def get_updates():
    global offset
    try:
        r = requests.get(f"{API_URL}/getUpdates", params={"timeout": 30, "offset": offset}, timeout=35)
        data = r.json()
        if not data.get("ok"):
            return []
        updates = data["result"]
        if updates:
            offset = updates[-1]["update_id"] + 1
        return updates
    except Exception as e:
        print("Error getting updates:", e)
        time.sleep(2)
        return []

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    text = (msg.get("text") or "").strip()

    if text.startswith("/start"):
        send_message(chat_id, build_welcome(user), MAIN_MARKUP, "HTML")
        return

    if text == "Питання":
        waiting_ids.add(chat_id)
        send_message(chat_id, "Напишіть своє питання текстом.", MAIN_MARKUP)
        return

    if text == "Отримати реквізити":
        send_message(chat_id, REKV_TEXT, MAIN_MARKUP, "HTML")
        return

    if chat_id in waiting_ids:
        waiting_ids.discard(chat_id)
        name = ((user.get("first_name") or "") + " " + (user.get("last_name") or "")).strip() or "Користувач"
        admin_text = (
            "<b>Нове питання</b>\n"
            f"Від: {escape(name)}\n"
            f"ID: {user.get('id')}\n\n"
            f"<pre>{escape(text)}</pre>"
        )
        if ADMIN_ID:
            send_message(ADMIN_ID, admin_text, "HTML")
        send_message(chat_id, "Дякуємо! Питання передано адміністратору.", MAIN_MARKUP)
        return

    send_message(chat_id, "Оберіть дію з меню ⬇", MAIN_MARKUP)

# Основной цикл polling
print("Bot started via polling")
while True:
    updates = get_updates()
    for update in updates:
        if "message" in update:
            handle_message(update["message"])
    time.sleep(0.5)  # чуть снижаем нагрузку на сервер
