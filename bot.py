import os
import json
import datetime
import threading
from flask import Flask, request
from sqlalchemy import create_engine, text
from html import escape

# ====== Мини-конфигурация ======
TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    raise RuntimeError("API_TOKEN environment variable not set!")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except Exception:
    ADMIN_ID = 0

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    loc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db")
    db_url = f"sqlite:///{loc_path}"
else:
    db_url = DATABASE_URL

# ========== БАЗА ==========
_engine = None
def get_engine():
    global _engine
    if _engine is None:
        if db_url.startswith("sqlite:///"):
            _engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
        else:
            _engine = create_engine(db_url, future=True)
    return _engine

def init_db():
    engine = get_engine()
    create_sql = """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        dt TEXT NOT NULL
    );
    """ if engine.dialect.name == "sqlite" else """
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        category TEXT NOT NULL,
        dt TIMESTAMP NOT NULL
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_sql))

def save_event(category):
    engine = get_engine()
    now = datetime.datetime.utcnow()
    if engine.dialect.name == "sqlite":
        dt_val = now.isoformat()
        insert_sql = "INSERT INTO events (category, dt) VALUES (:cat, :dt)"
        with engine.begin() as conn:
            conn.execute(text(insert_sql), {"cat": category, "dt": dt_val})
    else:
        insert_sql = "INSERT INTO events (category, dt) VALUES (:cat, :dt)"
        with engine.begin() as conn:
            conn.execute(text(insert_sql), {"cat": category, "dt": now})

init_db()

# ========== Flask-приложение ==========
app = Flask(__name__)

MAIN_MARKUP = {
    "keyboard": [
        [{"text":"Питання"}],
        [{"text":"Отримати реквізити"}]
    ],
    "resize_keyboard": True,
}

REKV_TEXT = "<b>Реквізити для переказу</b>\nПриватБанк: 1234 5678 0000 1111\nМоноБанк: 4444 5678 1234 5678\nIBAN: UA12 1234 5678 0000 1111 1234 5678\n"

waiting_ids = set()

@app.route(f"/webhook/{TOKEN}", methods=['POST'])
def webhook():
    try:
        data = request.get_data(as_text=True)
        update = json.loads(data)
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            user = message.get("from", {})
            if text == "/start":
                send_message(chat_id, "Ласкаво просимо! Оберіть дію з меню.", reply_markup=MAIN_MARKUP)
            elif text == "Питання":
                send_message(chat_id, "Задайте своє питання текстом. Ми передамо його адміністратору.", reply_markup=MAIN_MARKUP)
                waiting_ids.add(chat_id)
            elif text == "Отримати реквізити":
                send_message(chat_id, REKV_TEXT, parse_mode="HTML", reply_markup=MAIN_MARKUP)
            elif chat_id in waiting_ids:
                save_event("Питання")
                send_message(chat_id, "Дякуємо! Ваше питання отримано.", reply_markup=MAIN_MARKUP)
                user_name = (user.get('first_name') or '') + ' ' + (user.get('last_name') or '')
                admin_msg = "<b>Нове питання!</b>\n" \
                            f"Від: {escape(user_name.strip()) or 'Користувач'}\n" \
                            f"ID: {user.get('id')}\n" \
                            f"Текст: <pre>{escape(text)}</pre>"
                if ADMIN_ID:
                    send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                waiting_ids.discard(chat_id)
            else:
                send_message(chat_id, "Оберіть дію з меню ⬇", reply_markup=MAIN_MARKUP)
        return "ok", 200
    except Exception as e:
        print("Error:", e)
        return "ok", 200

@app.route('/', methods=['GET'])
def index():
    return "Bot working", 200

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    if not TOKEN:
        print("API_TOKEN not set; cannot send message.")
        return None
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
    }
    if reply_markup: payload['reply_markup'] = json.dumps(reply_markup)
    if parse_mode: payload['parse_mode'] = parse_mode
    try:
        import requests
        return requests.post(url, data=payload, timeout=8)
    except Exception as e:
        print("Error sending message:", e)
        return None

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting bot on port {port}...")
    app.run("0.0.0.0", port=port, debug=True)
