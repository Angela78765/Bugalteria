import os
import json
from html import escape
from flask import Flask, request
import requests

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise RuntimeError("API_TOKEN environment variable is not set")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

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

app = Flask(__name__)

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    requests.post(url, data=payload, timeout=10)

def build_welcome(user):
    name = ((user.get("first_name") or "") + " " + (user.get("last_name") or "")).strip()
    if not name:
        name = "Друже"
    return (
        f"<b>Ласкаво просимо, {escape(name)}!</b>\n\n"
        "Оберіть дію за допомогою кнопок внизу."
    )

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    if "message" not in update:
        return "ok", 200

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    text = (msg.get("text") or "").strip()

    command = text.split()[0]

    if command.startswith("/start"):
        send_message(
            chat_id,
            build_welcome(user),
            reply_markup=MAIN_MARKUP,
            parse_mode="HTML"
        )
        return "ok", 200

    if text == "Питання":
        waiting_ids.add(chat_id)
        send_message(
            chat_id,
            "Напишіть ваше питання текстом.",
            reply_markup=MAIN_MARKUP
        )
        return "ok", 200

    if text == "Отримати реквізити":
        send_message(
            chat_id,
            REKV_TEXT,
            reply_markup=MAIN_MARKUP,
            parse_mode="HTML"
        )
        return "ok", 200

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
            send_message(ADMIN_ID, admin_text, parse_mode="HTML")

        send_message(
            chat_id,
            "Дякуємо! Питання передано адміністратору.",
            reply_markup=MAIN_MARKUP
        )
        return "ok", 200

    send_message(chat_id, "Оберіть дію з меню ⬇", reply_markup=MAIN_MARKUP)
    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
