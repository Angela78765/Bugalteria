import os
import telebot
import telebot.util

# Получаем токен и ADMIN_ID из окружения (рекомендуется)
TOKEN = os.getenv("API_TOKEN") or "<ВАШ_ТОКЕН_ЗДЕСЬ>"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # 0 означает, что пересылки админу не будет

if not TOKEN or TOKEN.startswith("<ВАШ_ТОКЕН"):
    raise RuntimeError("Установите API_TOKEN в переменных окружения или замените в коде.")

bot = telebot.TeleBot(TOKEN)

# Клавиатура
markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
markup.add(telebot.types.KeyboardButton("Питання"))
markup.add(telebot.types.KeyboardButton("Отримати реквізити"))

REKV_TEXT = (
    "<b>Реквізити для переказу</b>\n"
    "ПриватБанк: 1234 5678 0000 1111\n"
    "МоноБанк: 4444 5678 1234 5678\n"
    "IBAN: UA12 1234 5678 0000 1111 1234 5678"
)

# /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Ласкаво просимо! Оберіть дію з меню.", reply_markup=markup)

# Кнопка "Питання"
@bot.message_handler(func=lambda m: m.text == "Питання")
def ask_question(message):
    sent = bot.send_message(message.chat.id, "Задайте своє питання:", reply_markup=markup)
    bot.register_next_step_handler(sent, process_question)

def process_question(message):
    question_text = message.text or ""
    bot.send_message(message.chat.id, "Дякуємо! Ваше питання отримано.", reply_markup=markup)

    # Подготовка и отправка админу (если указан ADMIN_ID)
    user_name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name])) or "Користувач"
    safe_name = telebot.util.escape_html(user_name)
    safe_text = telebot.util.escape_html(question_text)
    admin_msg = f"<b>Нове питання!</b>\nВід: {safe_name}\nID: {message.from_user.id}\nТекст: <pre>{safe_text}</pre>"

    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        except Exception as e:
            # не фатал — логируем
            print("Не удалось отправить админу:", e)

# Кнопка "Отримати реквізити"
@bot.message_handler(func=lambda m: m.text == "Отримати реквізити")
def send_rekv(message):
    bot.send_message(message.chat.id, REKV_TEXT, parse_mode="HTML", reply_markup=markup)

# Все остальные сообщения
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "Оберіть дію з меню ⬇", reply_markup=markup)

if __name__ == "__main__":
    print("Бот запущен. Ожидаю сообщений...")
    # Рекомендуется использовать infinity_polling для долгого запуска
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
