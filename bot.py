import os
import json
from flask import Flask, request
import requests
from html import escape

TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if not TOKEN or not ADMIN_ID:
    raise RuntimeError("API_TOKEN и ADMIN_ID должны быть заданы в переменных окружения!")

# Меню-клавиатура
MAIN_MARKUP = {
    "keyboard": [
        [{"text": "Меню"}],
        [{"text": "Связь с админом"}, {"text": "Реквізити оплати"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

REKV_TEXT = (
    "<b>Реквізити для оплати:</b>\n"
    "ПриватБанк: 1234 5678 0000 1111\n"
    "МоноБанк: 4444 5678 1234 5678\n"
    "IBAN: UA12 1234 5678 0000 1111 1234 5678"
)

waiting_feedback = set()

app = Flask(__name__)

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    requests.post(url, data=data, timeout=8)

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "") or ""
    user = msg.get("from", {})
    user_name = (user.get("first_name", "") + " " + user.get("last_name", "")).strip() or "Без имени"

    # /start (любой вариант)
    if text.startswith("/start"):
        send_message(chat_id, f"👋 Вітаємо, <b>{escape(user_name)}</b>! Виберіть дію з меню нижче.", reply_markup=MAIN_MARKUP, parse_mode="HTML")
        return "ok", 200

    # Reply-кнопки
    if text == "Меню":
        send_message(chat_id, "✨ Доступні дії:\n- Меню\n- Связь с админом\n- Реквізити оплати", reply_markup=MAIN_MARKUP)
        return "ok", 200
    if text == "Реквізити оплати":
        send_message(chat_id, REKV_TEXT, reply_markup=MAIN_MARKUP, parse_mode="HTML")
        return "ok", 200
    if text == "Связь с админом":
        waiting_feedback.add(chat_id)
        send_message(chat_id, "✉️ Введіть повідомлення для адміністратора:", reply_markup=MAIN_MARKUP)
        return "ok", 200

    # Принятие сообщения для админа
    if chat_id in waiting_feedback:
        sent = (
            f"<b>Повідомлення адміну!</b>\n"
            f"Від: <b>{escape(user_name)}</b> (id: {user.get('id')})\n"
            f"\n{escape(text)}"
        )
        send_message(ADMIN_ID, sent, parse_mode="HTML")
        send_message(chat_id, "✅ Повідомлення відправлено адміністратору.", reply_markup=MAIN_MARKUP)
        waiting_feedback.discard(chat_id)
        return "ok", 200

    # Всё остальное — просто просим выбрать действие
    send_message(chat_id, "Будь ласка, оберіть дію з меню 👇", reply_markup=MAIN_MARKUP)
    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"Bot started at port {port}")
    app.run(host="0.0.0.0", port=port)
