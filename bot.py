import os
import json
from flask import Flask, request
import requests
from html import escape

# ======= Конфігурація =======
TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ======= Новый блок для реквизитов =======
PAY_DETAILS_TEXT = (
    "Отримувач:\n"
    "ФОП Романюк Анжела Василівна\n"
    "UA033220010000026006340057875\n"
    "ЄДРПОУ 3316913762\n"
    "Призначення платежу: \n"
    "Оплата за консультаційні інформаційні послуги"
)

app = Flask(__name__)

# ======= State для керування чатами =======
active_chats = {}  # user_id -> stage: 'pending' | 'active'

# ======= State для консультацій і етапів звітів =======
consult_request = {}  # user_id -> {"stage": "choose_duration"/"await_contact", "duration": "30"|"45"|"60"}
reports_request = {}  # user_id -> {"stage": "...", "type": "submit"/"taxcheck"}
prro_request = {}     # Можна розширити, якщо знадобиться логіка ПРРО

# ======= State для декретних (додано) =======
decret_request = {}   # user_id -> {"stage": "await_contact"}

# ======= Reply та Inline розмітки =======
def main_menu_markup():
    return {
        "keyboard": [
            [{"text": "Меню"}],
            [{"text": "Поставити питання"}, {"text": "Реквізити для оплати"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def user_finish_markup():
    return {
        "keyboard": [[{"text": "Завершити чат"}]],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def admin_reply_markup(user_id):
    return {
        "inline_keyboard": [
            [{"text": "Відповісти", "callback_data": f"reply_{user_id}"}],
            [{"text": "Завершити чат", "callback_data": f"close_{user_id}"}],
        ]
    }

def welcome_services_inline():
    return {
        "inline_keyboard": [
            [{"text": "• консультації", "callback_data": "consult"}],
            [{"text": "• супровід ФОП", "callback_data": "support"}],
            [{"text": "• реєстрація / закриття", "callback_data": "regclose"}],
            [{"text": "• звітність і податки", "callback_data": "reports"}],
            [{"text": "реєстрація/закриття ПРРО", "callback_data": "prro"}],
            [{"text": "• декрет ФОП", "callback_data": "decret"}]
        ]
    }

def return_to_menu_markup():
    return {
        "keyboard": [[{"text": "Повернутися в меню"}]],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# ======= Inline розмітка для консультації =======
def consult_duration_inline():
    return {
        "inline_keyboard": [
            [{"text": "20 хв", "callback_data": "consult_30"}],
            [{"text": "40 хв", "callback_data": "consult_45"}],
            [{"text": "Повернутися в меню", "callback_data": "consult_back"}]
        ]
    }

# ======= Inline розмітка для супровід ФОП =======
def support_groups_inline():
    return {
        "inline_keyboard": [
            [{"text": "Група ФОП 1", "callback_data": "support_1"}],
            [{"text": "Група ФОП 2", "callback_data": "support_2"}],
            [{"text": "Група ФОП 3", "callback_data": "support_3"}],
            [{"text": "Повернутися в меню", "callback_data": "support_back"}]
        ]
    }

def support_next_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реквізити для оплати", "callback_data": "support_pay"}],
            [{"text": "Поставити питання", "callback_data": "support_admin"}],
            [{"text": "Повернутися в меню", "callback_data": "support_back"}]
        ]
    }

# ======= Inline розмітка для реєстрація / закриття ФОП =======
def regclose_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реєстрація ФОП", "callback_data": "fop_register"}],
            [{"text": "Закриття ФОП", "callback_data": "fop_close"}],
            [{"text": "Повернутися в меню", "callback_data": "regclose_back"}]
        ]
    }

def fop_register_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реєструємо", "callback_data": "fop_register_pay"}],
            [{"text": "Повернутися", "callback_data": "regclose"}]
        ]
    }

def fop_close_inline():
    return {
        "inline_keyboard": [
            [{"text": "Закриваємо", "callback_data": "fop_close_pay"}],
            [{"text": "Повернутися", "callback_data": "regclose"}]
        ]
    }

# ======= Inline розмітка для звітність і податки =======
def reports_inline():
    return {
        "inline_keyboard": [
            [{"text": "Подача звіту", "callback_data": "report_submit"}],
            [{"text": "Оплата податку / перевірка ФОП", "callback_data": "report_tax_check"}],
            [{"text": "Повернутися в меню", "callback_data": "reports_back"}],
        ]
    }

def report_submit_service_inline():
    return {
        "inline_keyboard": [
            [{"text": "Хочу цю послугу", "callback_data": "report_submit_contacts"}],
            [{"text": "Повернутися", "callback_data": "reports"}],
        ]
    }

def report_tax_check_inline():
    return {
        "inline_keyboard": [
            [{"text": "Перевіряємо", "callback_data": "tax_check_contacts"}],
            [{"text": "Повернутися", "callback_data": "reports"}]
        ]
    }

def tax_check_pay_inline():
    return {
        "inline_keyboard": [
            [{"text": "Оплата / реквізити", "callback_data": "tax_check_pay"}],
            [{"text": "Повернутися", "callback_data": "reports"}]
        ]
    }

# ======= Inline розмітка для реєстрація/закриття ПРРО =======
def prro_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реєстрація ПРРО", "callback_data": "prro_register"}],
            [{"text": "Закриття ПРРО", "callback_data": "prro_close"}],
            [{"text": "Повернутися в меню", "callback_data": "prro_back"}]
        ]
    }

def prro_register_step_inline():
    return {
        "inline_keyboard": [
            [{"text": "Реєструємо", "callback_data": "prro_register_pay"}],
            [{"text": "Повернутися", "callback_data": "prro"}],
        ]
    }

def prro_register_pay_inline():
    return {
        "inline_keyboard": [
            [{"text": "Оплата / реквізити", "callback_data": "prro_pay"}],
            [{"text": "Повернутися", "callback_data": "prro"}],
        ]
    }

# ======= Inline розмітка для закриття ПРРО =======
def prro_close_step_inline():
    return {
        "inline_keyboard": [
            [{"text": "Закриваємо", "callback_data": "prro_close_apply"}],
            [{"text": "Повернутися", "callback_data": "prro"}],
        ]
    }


def prro_close_pay_inline():
    return {
        "inline_keyboard": [
            [{"text": "Оплата / реквізити", "callback_data": "prro_close_pay"}],
            [{"text": "Повернутися", "callback_data": "prro"}],
        ]
    }

# ======= Inline розмітка для декрет ФОП =======
def decret_inline():
    return {
        "inline_keyboard": [
            [{"text": "Хочу оформити", "callback_data": "decret_apply"}],
            [{"text": "Повернутися в меню", "callback_data": "decret_back"}]
        ]
    }

def decret_pay_inline():
    return {
        "inline_keyboard": [
            [{"text": "Оплатити / реквізити", "callback_data": "decret_pay"}],
            [{"text": "Повернутися", "callback_data": "decret"}]
        ]
    }

# ======= ТЕКСТИ для всіх сервісів =======
# ... Берутся из вашего оригинального файла, заменять не надо ...

# ======= Текст для закриття ПРРО =======
PRRO_CLOSE_INTRO_TEXT = (
    "Допомагаю професійно та швидко закрити ваш програмний реєстратор розрахункових операцій (ПРРО) відповідно до вимог законодавства України.\n\n"
    "Що входить у послугу:\n"
    "- Консультація щодо процесу закриття\n"
    "  Пояснюю, коли і як потрібно закривати ПРРО, а також можливі наслідки.\n\n"
    "- Підготовка необхідних документів\n"
    "  Готую всі потрібні заяви та документи для подання у податкову службу.\n\n"
    "- Подання заяви на закриття ПРРО\n"
    "  Офіційно подаю заявку на зняття ПРРО з обліку через електронний кабінет платника податків.\n\n"
    "- Контроль статусу заявки\n"
    "  Відслідковую процес розгляду і підтвердження закриття податковою службою.\n\n"
    "Ваші переваги:\n"
    "⚪ Мінімум клопоту — ми зробимо всю роботу за вас\n"
    "⚪ Оперативне і правильне оформлення документів\n"
    "⚪ Упевненість у дотриманні всіх вимог законодавства\n"
    "⚪ Підтримка та консультації на кожному етапі"
)

PRRO_CLOSE_CONTACT_TEXT = (
    "Дякую за звернення щодо закриття ПРРО.\n"
    "Для початку надайте, будь ласка:\n\n"
    "- Повну назву вашого бізнесу або ПІБ підприємця\n"
    "- Ідентифікаційний код платника податків (ІПН)\n"
    "- Електронний ключ та пароль\n"
    "- Оплату послуги\n\n"
    "Вартість послуги - 1800 грн.\n\n"
    "Ці дані необхідні для оформлення документів і подальшої подачі заявки до податкової служби."
)

# ======= Хелпери для відправки повідомлень і медіа =======
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(url, data=data, timeout=8)
    except Exception:
        pass

def send_media(chat_id, msg):
    for key, api in [
        ("photo", "sendPhoto"), ("document", "sendDocument"),
        ("video", "sendVideo"), ("audio", "sendAudio"), ("voice", "sendVoice")
    ]:
        if key in msg:
            file_id = msg[key][-1]["file_id"] if key == "photo" else msg[key]["file_id"]
            payload = {"chat_id": chat_id, key: file_id}
            if "caption" in msg:
                payload["caption"] = msg.get("caption")
            try:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/{api}", data=payload)
            except Exception:
                pass
            return True
    return False

# ======= Головний обробник подій Telegram =======
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    # --- Обробка інлайн-кнопок (callback_query) ---
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        from_id = cb["from"]["id"]

        # ====== Інлайн-кнопки для супровід ФОП ======
        if data == "support":
            send_message(chat_id, SUPPORT_INFO_TEXT, reply_markup=support_groups_inline())
            return "ok", 200

        if data in ("support_1", "support_2", "support_3"):
            send_message(chat_id, SUPPORT_GROUP_SELECTED_TEXT, reply_markup=support_next_inline())
            return "ok", 200

        if data == "support_pay":
            send_message(
                chat_id,
                PAY_DETAILS_TEXT,
                parse_mode="HTML"
            )
            return "ok", 200

        if data == "support_admin":
            if chat_id not in active_chats:
                active_chats[chat_id] = "pending"
                send_message(chat_id, "Очікуйте відповіді адміністратора...", reply_markup=user_finish_markup())
                notif = f"<b>Нове повідомлення по супроводу ФОП!</b>\nID: <pre>{chat_id}</pre>"
                send_message(ADMIN_ID, notif, parse_mode="HTML", reply_markup=admin_reply_markup(chat_id))
            else:
                send_message(chat_id, "Очікуйте відповіді адміністратора...", reply_markup=user_finish_markup())
            return "ok", 200

        if data == "support_back":
            send_message(chat_id, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
            return "ok", 200

        # >>>>>>> БЛОК ДЛЯ КОНСУЛЬТАЦІЇ <<<<<<<<
        if data == "consult":
            consult_request[from_id] = {"stage": "choose_duration"}
            send_message(chat_id, CONSULT_INTRO_TEXT, reply_markup=consult_duration_inline())
            return "ok", 200

        if data in ("consult_30", "consult_45", "consult_60"):
            duration = data.split("_")[1]
            consult_request[from_id] = {"stage": "await_contact", "duration": duration}
            send_message(chat_id, CONSULT_CONTACTS_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "consult_back":
            consult_request.pop(from_id, None)
            active_chats.pop(from_id, None)
            send_message(chat_id, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
            return "ok", 200

        # ====== Реєстрація / Закриття ФОП =====
        if data == "regclose":
            send_message(chat_id, REGCLOSE_INTRO_TEXT, reply_markup=regclose_inline())
            return "ok", 200

        if data == "fop_register":
            send_message(chat_id, FOP_REGISTER_TEXT, reply_markup=fop_register_inline())
            return "ok", 200

        if data == "fop_register_pay":
            send_message(chat_id, FOP_REGISTER_PAY_TEXT, reply_markup=regclose_inline())
            return "ok", 200

        if data == "fop_close":
            send_message(chat_id, FOP_CLOSE_TEXT, reply_markup=fop_close_inline())
            return "ok", 200

        if data == "fop_close_pay":
            send_message(chat_id, FOP_CLOSE_PAY_TEXT, reply_markup=regclose_inline())
            return "ok", 200

        if data == "regclose_back":
            send_message(chat_id, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
            return "ok", 200

        # ====== Блок звітність і податки ======
        if data == "reports":
            send_message(chat_id, REPORTS_INTRO_TEXT, reply_markup=reports_inline())
            return "ok", 200

        if data == "report_submit":
            send_message(chat_id, REPORT_SUBMIT_TEXT, reply_markup=report_submit_service_inline())
            return "ok", 200

        if data == "report_submit_contacts":
            reports_request[from_id] = {"stage": "await_contact", "type": "submit"}
            send_message(chat_id, REPORT_SUBMIT_CONTACTS_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "report_tax_check":
            send_message(chat_id, REPORT_TAX_CHECK_TEXT, reply_markup=report_tax_check_inline())
            return "ok", 200

        if data == "tax_check_contacts":
            reports_request[from_id] = {"stage": "await_contact", "type": "taxcheck"}
            send_message(chat_id, REPORT_TAX_CHECK_CONTACTS_TEXT, reply_markup=tax_check_pay_inline())
            return "ok", 200

        if data == "tax_check_pay":
            send_message(chat_id, TAX_CHECK_PAY_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "reports_back":
            send_message(chat_id, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
            return "ok", 200

        # ====== БЛОК ПРРО ======
        if data == "prro":
            send_message(chat_id, PRRO_INTRO_TEXT, reply_markup=prro_inline())
            return "ok", 200

        if data == "prro_register":
            send_message(chat_id, PRRO_REGISTER_TEXT, reply_markup=prro_register_step_inline())
            return "ok", 200

        if data == "prro_register_pay":
            send_message(chat_id, PRRO_REGISTER_CONTACTS_TEXT, reply_markup=prro_register_pay_inline())
            return "ok", 200

        if data == "prro_pay":
            send_message(chat_id, PRRO_REGISTER_PAY_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        # ====== Закриття ПРРО измененный сценарий ======
        if data == "prro_close":
            send_message(chat_id, PRRO_CLOSE_INTRO_TEXT, reply_markup=prro_close_step_inline())
            return "ok", 200

        if data == "prro_close_apply":
            send_message(chat_id, PRRO_CLOSE_CONTACT_TEXT, reply_markup=prro_close_pay_inline())
            return "ok", 200

        if data == "prro_close_pay":
            send_message(chat_id, PAY_DETAILS_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "prro_back":
            send_message(chat_id, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
            return "ok", 200

        # ====== ДЕКРЕТ ФОП ======
        if data == "decret":
            send_message(chat_id, DECRET_SERVICE_TEXT, reply_markup=decret_inline())
            return "ok", 200

        if data == "decret_apply":
            decret_request[from_id] = {"stage": "await_contact"}
            send_message(chat_id, DECRET_CONTACTS_TEXT, reply_markup=decret_pay_inline())
            return "ok", 200

        if data == "decret_pay":
            send_message(chat_id, DECRET_PAY_TEXT, reply_markup=return_to_menu_markup())
            return "ok", 200

        if data == "decret_back":
            send_message(chat_id, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
            return "ok", 200

        if data.startswith("reply_") and int(from_id) == ADMIN_ID:
            user_id = int(data.split("_")[1])
            active_chats[user_id] = "active"
            send_message(ADMIN_ID, f"Надішліть повідомлення або медіа для користувача {user_id}.")
            return "ok", 200

        if data.startswith("close_") and int(from_id) == ADMIN_ID:
            user_id = int(data.split("_")[1])
            active_chats.pop(user_id, None)
            send_message(user_id, "⛔️ Чат завершено адміністратором. Ви повернулись у головне меню.", reply_markup=main_menu_markup())
            send_message(ADMIN_ID, "Чат завершено.", reply_markup=main_menu_markup())
            return "ok", 200

    msg = update.get("message")
    if not msg:
        return "ok", 200
    cid = msg.get("chat", {}).get("id")
    text = msg.get("text", "") or ""
    user_data = msg.get("from", {})
    user_id = user_data.get("id")
    user_name = (user_data.get("first_name", "") + " " + user_data.get("last_name", "")).strip() or "Користувач"

    # ... Дальше обработка сообщений пользователя без изменений ...

    # === ОБРАБОТКА ДЛЯ MENU etc ===

    # --- Головне меню / старт ---
    if text.startswith("/start") or text == "Повернутися в меню":
        consult_request.pop(user_id, None)
        active_chats.pop(user_id, None)
        reports_request.pop(user_id, None)
        decret_request.pop(user_id, None)
        send_message(cid, "👋 Ласкаво просимо! Оберіть дію:", reply_markup=main_menu_markup())
        return "ok", 200

    if text == "Меню":
        send_message(cid, WELCOME_SERVICES_TEXT, reply_markup=welcome_services_inline(), parse_mode="HTML")
        return "ok", 200

    if text == "Реквізити для оплати" and cid not in active_chats:
        send_message(cid, f"<b>Реквізити для оплати:</b>\n{PAY_DETAILS_TEXT}", parse_mode="HTML", reply_markup=return_to_menu_markup())
        return "ok", 200

    # --- Запит на поставити питання (адмін) ---
    if text == "Поставити питання" and cid not in active_chats:
        active_chats[cid] = "pending"
        send_message(cid, "Очікуйте відповіді адміністратора...", reply_markup=user_finish_markup())
        notif = f"<b>Нове повідомлення від користувача!</b>\nВід: {escape(user_name)}\nID: <pre>{cid}</pre>"
        send_message(ADMIN_ID, notif, parse_mode="HTML", reply_markup=admin_reply_markup(cid))
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_media(ADMIN_ID, msg)
        elif text != "Поставити питання":
            send_message(ADMIN_ID, f"<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=admin_reply_markup(cid))
        return "ok", 200

    # --- Завершення чату користувачем ---
    if text == "Завершити чат" and cid in active_chats:
        active_chats.pop(cid, None)
        send_message(cid, "⛔️ Чат завершено. Ви повернулись у головне меню.", reply_markup=main_menu_markup())
        send_message(ADMIN_ID, f"Користувач {cid} завершив чат.", reply_markup=main_menu_markup())
        return "ok", 200

    # --- Переписка користувача з адміном ---
    if cid in active_chats and active_chats[cid] == "active":
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_media(ADMIN_ID, msg)
            send_message(ADMIN_ID, f"[медіа від {cid}]", reply_markup=admin_reply_markup(cid))
        elif text != "Завершити чат":
            send_message(ADMIN_ID, f"Користувач {cid}:\n<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=admin_reply_markup(cid))
        return "ok", 200

    # --- Відповідь адміна користувачу (якщо є активний чат) ---
    if cid == ADMIN_ID:
        targets = [u for u, s in active_chats.items() if s == "active"]
        if not targets:
            return "ok", 200
        target = targets[0]
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_media(target, msg)
            send_message(target, "💬 Відповідь адміністратора (медіа).", reply_markup=user_finish_markup())
        elif text.lower().startswith("завершити"):
            active_chats.pop(target, None)
            send_message(target, "⛔️ Чат завершено адміністратором. Ви повернулись у головне меню.", reply_markup=main_menu_markup())
            send_message(ADMIN_ID, "Чат завершено.", reply_markup=main_menu_markup())
        elif text:
            send_message(target, f"💬 Відповідь адміністратора:\n<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=user_finish_markup())
        return "ok", 200

    # --- Якщо користувач у чаті, доступні лише переписка і "Завершити чат" ---
    if cid in active_chats:
        send_message(cid, "У активному чаті доступні тільки переписка і кнопка 'Завершити чат'.", reply_markup=user_finish_markup())
        return "ok", 200

    # === ОБРОБКА КОНТАКТІВ ДЛЯ КОНСУЛЬТАЦІЇ ===
    if user_id in consult_request and consult_request[user_id].get("stage") == "await_contact":
        duration = consult_request[user_id].get("duration")
        note = (
            f"<b>Заявка на консультацію</b>\n"
            f"Тривалість: {duration} хв\n"
            f"Від: {escape(user_name)}\n"
            f"ID: <pre>{user_id}</pre>\n"
        )
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_media(ADMIN_ID, msg)
        elif text:
            note += f"Контакти: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
        send_message(user_id, "Дякуємо! Ваші дані отримано, з вами зв'яжеться адміністратор.", reply_markup=main_menu_markup())
        consult_request.pop(user_id, None)
        return "ok", 200

    # === ОБРОБКА КОНТАКТІВ ДЛЯ ЗВІТНОСТІ/ПОДАТКІВ ===
    if user_id in reports_request and reports_request[user_id].get("stage") == "await_contact":
        req_type = reports_request[user_id].get("type")
        note = ""
        if req_type == "submit":
            note = (
                f"<b>Заявка на подання звітності</b>\n"
                f"Від: {escape(user_name)}\n"
                f"ID: <pre>{user_id}</pre>\n"
            )
            if text:
                note += f"Контакти для звітності: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_message(user_id, "Дякуємо! Ваші дані отримано, звітність буде підготовлена найближчим часом.", reply_markup=main_menu_markup())
            reports_request.pop(user_id, None)
            return "ok", 200
        elif req_type == "taxcheck":
            note = (
                f"<b>Запит на перевірку ФОП/податків</b>\n"
                f"Від: {escape(user_name)}\n"
                f"ID: <pre>{user_id}</pre>\n"
            )
            if text:
                note += f"Контакти для перевірки: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_message(user_id, "Дякуємо! Перевірка буде виконана і вся інформація надана у відповіді.", reply_markup=main_menu_markup())
            reports_request.pop(user_id, None)
            return "ok", 200

    # === ОБРОБКА КОНТАКТІВ ДЛЯ ДЕКРЕТУ (нове) ===
    if user_id in decret_request and decret_request[user_id].get("stage") == "await_contact":
        note = (
            f"<b>Заявка на оформлення декретних</b>\n"
            f"Від: {escape(user_name)}\n"
            f"ID: <pre>{user_id}</pre>\n"
        )
        if any(k in msg for k in ("photo", "document", "video", "audio", "voice")):
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
            send_media(ADMIN_ID, msg)
        elif text:
            note += f"Контакти для декретних: <pre>{escape(text.strip())}</pre>"
            send_message(ADMIN_ID, note, parse_mode="HTML", reply_markup=admin_reply_markup(user_id))
        send_message(user_id, "Дякуємо! Ваші дані отримано, розпочнемо підготовку документів. Якщо потрібно щось ще — звертайтеся!", reply_markup=main_menu_markup())
        decret_request.pop(user_id, None)
        return "ok", 200

    # --- Fallback: меню за замовчуванням ---
    send_message(cid, "Будь ласка, оберіть дію з меню 👇", reply_markup=main_menu_markup())
    return "ok", 200

# ======= Пінг для uptime моніторингу / перевірки =======
@app.route("/", methods=["GET"])
def index():
    return "OK", 200

if __name__ == "__main__":
    app.run("0.0.0.0", port=int(os.getenv("PORT", "5000")))
