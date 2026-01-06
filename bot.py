import telebot

# Твой токен
TOKEN = '8465183620:AAFJn7oANCnjTz_uoed0uRtOkITR1Tj7PQI'
ADMIN_ID = 887078537

bot = telebot.TeleBot(TOKEN)

# Разметка клавиатуры
markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
markup.add(telebot.types.KeyboardButton("Питання"))
markup.add(telebot. types.KeyboardButton("Отримати реквізити"))

REKV_TEXT = (
    "<b>Реквізити для переказу</b>\n"
    "ПриватБанк: 1234 5678 0000 1111\n"
    "МоноБанк: 4444 5678 1234 5678\n"
    "IBAN: UA12 1234 5678 0000 1111 1234 5678"
)

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Ласкаво просимо! Оберіть дію з меню.", reply_markup=markup)

# Кнопка "Питання"
@bot.message_handler(func=lambda message: message.text == "Питання")
def ask_question(message):
    msg = bot.send_message(message.chat.id, "Задайте своє питання:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_question)

def process_question(message):
    question_text = message.text
    bot.send_message(message.chat.id, "Дякуємо! Ваше питання отримано.", reply_markup=markup)
    
    # Відправляємо адміну
    user_name = f"{message.from_user.first_name} {message.from_user.last_name}".strip() or "Користувач"
    admin_msg = f"<b>Нове питання!</b>\nВід: {user_name}\nID: {message.from_user.id}\nТекст: {question_text}"
    bot. send_message(ADMIN_ID, admin_msg, parse_mode="HTML")

# Кнопка "Отримати реквізити"
@bot.message_handler(func=lambda message: message. text == "Отримати реквізити")
def send_rekv(message):
    bot.send_message(message. chat.id, REKV_TEXT, parse_mode="HTML", reply_markup=markup)

# Всі інші повідомлення
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.send_message(message.chat.id, "Оберіть дію з меню ⬇", reply_markup=markup)

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
