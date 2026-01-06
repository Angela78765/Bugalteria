import os, json
import requests
from flask import Flask, request
from html import escape

TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
app = Flask(__name__)

# Чаты в ожидании ответа админа: user_id -> статус ('pending', 'active')
active_chats = {}  # user_id: {'status': 'pending'/'active'}

def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup: data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: data["parse_mode"] = parse_mode
    requests.post(url, data=data, timeout=7)

def send_media(user_id, msg):
    send_funcs = [
        ("photo", "sendPhoto"), ("document", "sendDocument"),
        ("video", "sendVideo"), ("audio", "sendAudio"), ("voice", "sendVoice")
    ]
    for k, api in send_funcs:
        if k in msg:
            file_id = msg[k][-1]["file_id"] if k=="photo" else msg[k]["file_id"]
            payload = {"chat_id": user_id, k: file_id}
            if "caption" in msg: payload["caption"] = msg.get("caption")
            requests.post(f"https://api.telegram.org/bot{TOKEN}/{api}", data=payload)
            return True
    return False

def user_markup(status):
    if status == "active":
        return {"keyboard": [[{"text": "Завершить чат"}]], "resize_keyboard": True, "one_time_keyboard": False}
    if status == "pending":
        return {"keyboard": [[{"text": "Завершить чат"}]], "resize_keyboard": True, "one_time_keyboard": False}
    # стандартное меню не показываем во время диалога

def admin_markup_pending(user_id):
    return {"inline_keyboard": [[{"text": "Принять чат", "callback_data": f"accept_{user_id}"}]]}

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    # CALLBACK - админ принимает чат
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_data = cb.get("data", "")
        from_id = cb["from"]["id"]
        if from_id == ADMIN_ID and cb_data.startswith("accept_"):
            user_id = int(cb_data.split("_")[1])
            active_chats[user_id] = {"status":"active"}
            send_message(ADMIN_ID, f"🟢 Чат с пользователем {user_id} активен.")
            send_message(user_id, "Администратор принял Ваш запрос — Вы теперь можете вести переписку.\n(Только кнопка 'Завершить чат' доступна)", reply_markup=user_markup("active"))
        return "ok", 200

    msg = update.get("message")
    if not msg: return "ok",200

    chat_id = msg.get("chat",{}).get("id")
    from_id = msg.get("from",{}).get("id")
    text = msg.get("text","") or ""
    first_last = (msg.get("from",{}).get("first_name","") + " " + msg.get("from",{}).get("last_name","")).strip()
    user_name = first_last if first_last else "Пользователь"

    # Пользователь инициирует связь с админом
    if text == "Связь с админом":
        active_chats[chat_id] = {"status":"pending"}
        send_message(chat_id, "Ожидание ответа администратора...", reply_markup=user_markup("pending"))
        notify = (f"Запрос на чат от <b>{escape(user_name)}</b>\nID: <pre>{chat_id}</pre>")
        send_message(ADMIN_ID, notify, reply_markup=admin_markup_pending(chat_id), parse_mode="HTML")
        return "ok", 200

    # Пользователь завершает чат
    if text == "Завершить чат" and chat_id in active_chats:
        send_message(chat_id, "⛔️ Чат завершён. Для нового запроса выберите 'Связь с админом'")
        send_message(ADMIN_ID, f"Пользователь {chat_id} завершил чат.")
        del active_chats[chat_id]
        return "ok", 200

    # Ведется переписка (чат активен)
    if chat_id in active_chats:
        if active_chats[chat_id]["status"] != "active":
            send_message(chat_id, "Ожидайте подтверждения администратора или завершите чат.", reply_markup=user_markup("pending"))
            return "ok", 200
        # Медиа или текст -> админу
        if any(k in msg for k in ("photo","video","document","audio","voice")):
            send_media(ADMIN_ID,msg)
            send_message(ADMIN_ID, f"[медиа от пользователя {chat_id}]", parse_mode="HTML")
        elif text and text != "Завершить чат":
            send_message(ADMIN_ID, f"Сообщение от пользователя {chat_id}:\n<pre>{escape(text)}</pre>",parse_mode="HTML")
        return "ok", 200

    # Админ завершает чат
    if chat_id == ADMIN_ID and text.startswith("завершить") and len(text.split())>1:
        target = text.split()[1]
        try:
            target_id = int(target)
            if target_id in active_chats:
                send_message(target_id, f"⛔️ Администратор завершил чат.")
                send_message(ADMIN_ID, f"Чат с {target_id} завершен.")
                del active_chats[target_id]
        except: pass
        return "ok",200

    # Если админ пишет в чат с ботом, пытаемся переслать в последний активный чат
    if chat_id == ADMIN_ID and len(active_chats)>0:
        # Берём первый активный чат
        targets = [uid for uid, c in active_chats.items() if c["status"]=="active"]
        if targets:
            target_id = targets[0]
            if any(k in msg for k in ("photo","video","document","audio","voice")):
                send_media(target_id, msg)
                send_message(ADMIN_ID, f"✅ Медиа отправлено пользователю.")
                send_message(target_id, "💬 Ответ администратора (медиа).")
            elif text:
                send_message(target_id, f"💬 Ответ адміністратора:\n<pre>{escape(text)}</pre>",parse_mode="HTML")
                send_message(ADMIN_ID, f"✅ Ваше сообщение отправлено пользователю.")
            return "ok", 200

    # /start — стандартное приветствие.
    if text.startswith("/start"):
        menu = {
            "keyboard": [
                [{"text": "Меню"}],
                [{"text": "Связь с админом"}, {"text": "Реквізити оплати"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }
        send_message(chat_id, f"👋 Добро пожаловать!", reply_markup=menu)
        return "ok", 200

    # Функции выводим только если пользователь не в чате
    if text == "Меню" and chat_id not in active_chats:
        send_message(chat_id, "✨ Доступні дії:\n- Меню\n- Связь с админом\n- Реквізити оплати",reply_markup={
            "keyboard": [
                [{"text": "Меню"}],
                [{"text": "Связь с админом"}, {"text": "Реквізити оплати"}]
            ], "resize_keyboard": True, "one_time_keyboard": False
        })
        return "ok", 200
    if text == "Реквізити оплати" and chat_id not in active_chats:
        send_message(chat_id, "Ось реквізити:\n" +
                              "ПриватБанк: 1234 5678 0000 1111\n"
                              "МоноБанк: 4444 5678 1234 5678\n"
                              "IBAN: UA12 1234 5678 0000 1111 1234 5678", reply_markup={
            "keyboard": [
                [{"text": "Меню"}],
                [{"text": "Связь с админом"}, {"text": "Реквізити оплати"}]
            ], "resize_keyboard": True, "one_time_keyboard": False
        })
        return "ok", 200

    # fallback для прочих действий (нет доступа)
    if chat_id in active_chats:
        send_message(chat_id, "В чаті з адміністратором доступні тільки повідомлення і кнопка 'Завершить чат'.")
        return "ok", 200
    send_message(chat_id, "Будь ласка, оберіть дію з меню 👇")
    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run("0.0.0.0", port=port)
