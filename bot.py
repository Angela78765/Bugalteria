import os
import json
import time
from html import escape
from flask import Flask, request
import requests

TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise RuntimeError("API_TOKEN environment variable is not set")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except Exception:
    ADMIN_ID = 0

# Клавиатура — reply-кнопки
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

# State: чаты, которые находятся в режиме "чекаємо питання"
waiting_ids = set()

app = Flask(__name__)

def send_message(chat_id, text, reply_markup=None, parse_mode=None, timeout=8):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        r = requests.post(url, data=data, timeout=timeout)
        if not r.ok:
            print(f"send_message failed {r.status_code}: {r.text}")
        return r
    except Exception as e:
        print(f"Error in send_message: {e}")
        return None

def build_welcome_message(user: dict) -> str:
    first = (user.get('first_name') or "").strip()
    last = (user.get('last_name') or "").strip()
    display = (first + (" " + last if last else "")).strip() or "Друже"
    return (
        "<b>Ласкаво просимо, " + escape(display) + "!</b>\n\n"
        "Оберіть дію за допомогою кнопок внизу."
    )

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        data_raw = request.get_data(as_text=True)
        update = json.loads(data_raw)

        if "message" in update:
            msg = update["message"]
            chat = msg.get("chat", {}) or {}
            frm = msg.get("from", {}) or {}
            chat_id = chat.get("id")
            from_id = frm.get("id")
            text = msg.get("text", "")

            # Исправление: обработка вариантов команды /start
            if text.startswith("/start"):
                # Учитываем варианты: '/start', '/start@BotName', '/start аргументы'
                if " " in text:  # Если есть аргументы: /start аргументы
                    arg = text.split(" ", 1)[1]
                    welcome = f"<b>Отримано аргумент:</b> <pre>{escape(arg)}</pre>\n\n"
                else:
                    welcome = ""
                welcome += build_welcome_message(frm)
                send_message(chat_id, welcome, reply_markup=MAIN_MARKUP, parse_mode="HTML")
                return "ok", 200

            # user pressed "Питання"
            if text.strip() == "Питання":
                waiting_ids.add(chat_id)
                send_message(chat_id, "Напишіть, будь ласка, своє питання текстом. Ми передамо його адміністратору.", reply_markup=MAIN_MARKUP)
                return "ok", 200

            # user pressed "Отримати реквізити"
            if text.strip() == "Отримати реквізити":
                send_message(chat_id, REKV_TEXT, reply_markup=MAIN_MARKUP, parse_mode="HTML")
                return "ok", 200

            # if chat is waiting for question — forward to admin and confirm
            if chat_id in waiting_ids:
                user_name = (frm.get('first_name') or '') + ' ' + (frm.get('last_name') or '')
                user_name = user_name.strip() or 'Користувач'
                admin_text = (
                    "<b>Нове питання</b>\n"
                    f"Від: {escape(user_name)}\n"
                    f"ID: {escape(str(from_id))}\n\n"
                    f"<b>Текст:</b>\n<pre>{escape(text)}</pre>"
                )
                if ADMIN_ID:
                    send_message(ADMIN_ID, admin_text, parse_mode="HTML")
                send_message(chat_id, "Дякуємо! Ваше питання отримано та передане адміністратору.", reply_markup=MAIN_MARKUP)
                waiting_ids.discard(chat_id)
                return "ok", 200

            # default fallback
            send_message(chat_id, "Оберіть дію з меню ⬇", reply_markup=MAIN_MARKUP)
        return "ok", 200
    except Exception as e:
        print(f"Error in webhook: {e}")
        return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"Starting app on port {port} ...")
    app.run(host="0.0.0.0", port=port)
