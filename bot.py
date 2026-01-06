import os
import json
import datetime
from flask import Flask, request
from sqlalchemy import create_engine, text
from html import escape

# ----------- Ваши значения -----------
TOKEN = '8465183620:AAFJn7oANCnjTz_uoed0uRtOkITR1Tj7PQI'  # <-- вставлен ваш токен
ADMIN_ID = 887078537                                      # <-- вставлен ваш ID

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db")
db_url = f"sqlite:///{db_path}"

waiting_ids = set()

# -------- Создание базы ------------
_engine = None
def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    return _engine

def init_db():
    engine = get_engine()
    create_sql = """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        dt TEXT NOT NULL
    );"""
    with engine.begin() as conn:
        conn.execute(text(create_sql))

def save_event(category):
    engine = get_engine()
    now = datetime.datetime.utcnow().isoformat()
    insert_sql = "INSERT INTO events (category, dt) VALUES (:cat, :dt)"
    with engine.begin() as conn:
        conn.execute(text(insert_sql), {"cat": category, "dt": now})

init_db()

# ----------- Flask и бизнес-логика -----------
app = Flask(__name__)

MAIN_MARKUP = {
    "keyboard": [
        [{"text": "Питання"}],
        [{"text": "Отримати реквізити"}]
    ],
    "resize_keyboard": True
}

REKV_TEXT = (
    "<b>Реквізити для переказу</b>\n"
    "ПриватБанк: 1234 5678 0000 1111\n"
    "МоноБанк: 4444 5678 1234 5678\n"
    "IBAN: UA12 1234 5678 0000 1111 1234 5678\n"
)

@app.route(f"/webhook/{TOKEN}", methods=['POST'])
def webhook():
    try:
        data = request.get_data(as_text=True)
        print("Получен апдейт:", data)
        update = json.loads(data)
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "").strip()
            user = message.get("from", {})
            print(f"---- message from {chat_id}: '{text}'")

            if text == "/start":
                send_message(chat_id, "Ласкаво просимо! Оберіть дію з меню.", reply_markup=MAIN_MARKUP)
            elif text == "Питання":
                send_message(chat_id, "Задайте своє питання текстом. Ми передамо його адміністратору.", reply_markup=MAIN_MARKUP)
                waiting_ids.add(chat_id)
            elif text == "Отримати реквізити":
                send_message(chat_id, REKV_TEXT, parse_mode="HTML", reply_markup=MAIN_MARKUP)
            elif chat_id in waiting_ids and text:
                save_event("Питання")
                send_message(chat_id, "Дякуємо! Ваше питання отримано.", reply_markup=MAIN_MARKUP)
                user_name = (user.get('first_name') or '') + ' ' + (user.get('last_name') or '')
                admin_msg = (
                    "<b>Нове питання!</b>\n"
                    f"Від: {escape(user_name.strip()) or 'Користувач'}\n"
                    f"ID: {user.get('id')}\n"
                    f"Текст: <pre>{escape(text)}</pre>"
                )
                if ADMIN_ID:
                    send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                waiting_ids.discard(chat_id)
            else:
                send_message(chat_id, "Оберіть дію з меню ⬇", reply_markup=MAIN_MARKUP)
        else:
            print("Нет message!", update)
        return "ok", 200
    except Exception as e:
        print("Ошибка в webhook:", e)
        return "ok", 200

@app.route("/", methods=['GET'])
def root():
    return "Bot is running", 200

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        import requests
        resp = requests.post(url, data=payload, timeout=10)
        print(f"[send_message] Ответ {resp.status_code}", resp.text)
        return resp
    except Exception as e:
        print("[send_message] Ошибка:", e)
        return None

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Стартую на порту {port} ...")
    app.run("0.0.0.0", port=port, debug=True)
