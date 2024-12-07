import sqlite3
import requests
import telebot
import time
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from PIL import Image
from rapidfuzz import fuzz
from telebot.types import InputFile
from data_base import fetch_toys_by_category, get_user_data

bot = telebot.TeleBot('7923077803:AAEA0l_QzDm6YsUquLXMwIJJnesfN__5OkQ')

# Змінні для зберігання інформації про товари та індекси
toys_by_category = {}
current_toy_index = {}
previous_message_ids = {}
search_mode = {}
user_cart = {}
user_order_data = {}
user_data = {}

ADMIN_ID = 389804772;

# Функція для створення з'єднання з базою даних
def create_connection():
    connection = sqlite3.connect("toys_store.db")
    return connection

@bot.message_handler(commands=['getid'])
def send_chat_id(message):
    bot.send_message(message.chat.id, f"Ваш ID: {message.chat.id}")

@bot.message_handler(commands=['start'])
def main(message):
    bot.send_message(message.chat.id, 'Вітаємо у чат-боті магазину "Цяцькарня🎠"\n\n')
    show_main_menu(message)

def show_main_menu(message):
    main_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_catalog = types.KeyboardButton('Каталог📚')
    btn_search = types.KeyboardButton('Пошук🔍')
    btn_discounts = types.KeyboardButton('Знижки💸')
    btn_cart = types.KeyboardButton('Кошик🛒')
    main_markup.row(btn_catalog, btn_search, btn_discounts, btn_cart)
    bot.send_message(message.chat.id, "Оберіть дію з меню⤵️", reply_markup=main_markup)

@bot.message_handler(func=lambda message: message.text == 'Каталог📚')
def show_catalog(message):
    category_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_painting = types.KeyboardButton('Набори для малювання та розмальовки')
    btn_stickers = types.KeyboardButton('Наліпки та стікербуки')
    btn_creative = types.KeyboardButton('Творчі набори')
    btn_active_games = types.KeyboardButton('Ігри для активного відпочинку')
    btn_back = types.KeyboardButton('⬅️ Назад')

    category_markup.add(btn_painting, btn_creative)
    category_markup.add(btn_stickers, btn_active_games)
    category_markup.add(btn_back)

    bot.send_message(message.chat.id, "Виберіть категорію товарів:", reply_markup=category_markup)

def crop_image_top_bottom(image_path, top_crop, bottom_crop):
    # Відкрити зображення
    with Image.open(image_path) as img:
        width, height = img.size
        # Обрізати зображення зверху і знизу
        cropped_img = img.crop((0, top_crop, width, height - bottom_crop))
        # Зберегти обрізане зображення
        cropped_img.save("cropped_image.jpg")

# Список ID товарів, які не потрібно обрізати
non_croppable_toys = [13, 23, 24, 27, 28, 29, 33, 45, 46, 47, 48, 49, 50]  # замініть на потрібні ID

def send_toy_image(chat_id, toy_id, is_first=False):
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT name, description, price, photo_url FROM toys WHERE id = ?;", (toy_id,))
    toy_data = cursor.fetchone()
    connection.close()

    if toy_data:
        name, description, price, photo_url = toy_data
        response = requests.get(photo_url)

        if response.status_code == 200:
            with open("temp_image.jpg", "wb") as temp_file:
                temp_file.write(response.content)

            if toy_id not in non_croppable_toys:
                # Обрізаємо фото, якщо ID не в списку non_croppable_toys
                image = Image.open("temp_image.jpg")
                width, height = image.size
                cropped_image = image.crop((0, height * 0.1, width, height * 0.9))
                cropped_image = cropped_image.convert("RGB")
                cropped_image.save("temp_image.jpg")

            # Далі відправка фото з уже обрізаним або оригінальним варіантом
            with open("temp_image.jpg", "rb") as temp_file:
                caption = f"<b>{name}</b>\n\n{description}\n\nЦіна: {price} грн"
                inline_markup = types.InlineKeyboardMarkup()
                buttons = []
                if not is_first:
                    buttons.append(types.InlineKeyboardButton("⬅️Попередній", callback_data='previous'))
                buttons.append(types.InlineKeyboardButton("Наступний➡️", callback_data='next'))
                inline_markup.add(*buttons)
                inline_markup.add(types.InlineKeyboardButton("Додати до кошика🛒", callback_data=f'add_cart_{toy_id}'))

                if chat_id in previous_message_ids:
                    try:
                        bot.delete_message(chat_id, previous_message_ids[chat_id])
                    except Exception as e:
                        print(f"Не вдалося видалити повідомлення: {e}")

                message = bot.send_photo(chat_id=chat_id, photo=temp_file, caption=caption, parse_mode='HTML',
                                         reply_markup=inline_markup)
                previous_message_ids[chat_id] = message.message_id


@bot.message_handler(func=lambda message: message.text in ['Наліпки та стікербуки', 'Творчі набори',
                                                           'Набори для малювання та розмальовки',
                                                           'Ігри для активного відпочинку'])
def show_category(message):
    # отримуємо назву категорії з повідомлення користувача
    category = message.text
    waiting_message = bot.send_message(message.chat.id, "Зачекайте, йде пошук товарів...⏳")
    # отримуємо товари за обраною категорією
    toys = fetch_toys_by_category(category)
    # робимо паузу для пошуку
    time.sleep(2)
    bot.delete_message(message.chat.id, waiting_message.message_id)

    if toys:
        # зберігаємо товари за категорією для користувача
        toys_by_category[message.chat.id] = toys
        # встановлюємо індекс поточного товару
        current_toy_index[message.chat.id] = 0
        # надсилаємо зображення першого товару
        send_toy_image(message.chat.id, toys[0][0], is_first=True)
    else:
        bot.send_message(message.chat.id, "На жаль, в цій категорії немає товарів.")



@bot.message_handler(func=lambda message: message.text == 'Пошук🔍')
def start_search(message):
    search_mode[message.chat.id] = True  # Увімкнення режиму пошуку
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_back = types.KeyboardButton('⬅️ Назад')
    markup.add(btn_back)
    bot.send_message(message.chat.id, "Введіть назву або ключове слово для пошуку товару:", reply_markup=markup)

@bot.message_handler(func=lambda message: search_mode.get(message.chat.id, False))
def search_toys(message):
    if message.text == "⬅️ Назад":
        search_mode[message.chat.id] = False  # Вимикаємо режим пошуку
        show_main_menu(message)  # Повертаємося до головного меню
        return  # Припиняємо виконання функції
    keyword = message.text.lower()  # Приведення запиту до нижнього регістру
    connection = create_connection()
    cursor = connection.cursor()

    # Повідомлення про очікування
    waiting_message = bot.send_message(message.chat.id, "Зачекайте, йде пошук товарів...⏳")
    time.sleep(2)  # Затримка для імітації завантаження
    bot.delete_message(message.chat.id, waiting_message.message_id)

    try:
        # Отримання всіх імен і описів товарів з бази
        cursor.execute("SELECT id, name, description FROM toys")
        toys = cursor.fetchall()
    except Exception as e:
        bot.send_message(message.chat.id, f"Сталася помилка: {e}")
        return
    finally:
        connection.close()

    # Пошук за подібністю
    # створюємо список для збереження результатів пошуку

    results = []

    # ітеруємося по списку іграшок
    for toy in toys:
        # обчислюємо схожість за назвою
        name_similarity = fuzz.partial_ratio(keyword, toy[1].lower())
        # обчислюємо схожість за описом
        description_similarity = fuzz.partial_ratio(keyword, toy[2].lower())

        # якщо схожість перевищує поріг, додаємо іграшку до результатів
        if name_similarity > 70 or description_similarity > 70:
            results.append(toy)

    # перевіряємо, чи є результати пошуку
    if results:
        # зберігаємо результати для подальшої роботи
        toys_by_category[message.chat.id] = results
        # встановлюємо індекс першого товару
        current_toy_index[message.chat.id] = 0

        # надсилаємо перший товар із результатів пошуку
        send_toy_image(message.chat.id, results[0][0], is_first=True)
    else:
        bot.send_message(message.chat.id, f"На жаль, за запитом '{keyword}' нічого не знайдено.")

    # Повернення до головного меню
    search_mode[message.chat.id] = False
    show_main_menu(message)

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def go_back(message):
    show_main_menu(message)

def cancel_search(message):
    if search_mode.get(message.chat.id):
        search_mode[message.chat.id] = False  # Вимкнення режиму пошуку
        bot.send_message(message.chat.id, "Пошук скасовано❌")
        show_main_menu(message)


@bot.message_handler(func=lambda message: message.text == 'Знижки💸')
def discounts(message):
    # Надсилаємо користувачу повідомлення про знижку
    markup = types.InlineKeyboardMarkup()
    btn_contact = types.InlineKeyboardButton("Зв'язатись з менеджером", callback_data='contact_admin')
    markup.add(btn_contact)
    bot.send_message(
        message.chat.id,
        "Ви можете отримати *знижку -10%* для військових💸 \n\nДля підтвердження зв'яжіться з менеджером⤵️:", parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'contact_admin')
def contact_admin(call):
    user_nickname = call.from_user.username if call.from_user.username else "Без нікнейму"
    user_link = f'<a href="tg://user?id={call.from_user.id}">{user_nickname}</a>' if call.from_user.username else f"<a href='tg://user?id={call.from_user.id}'>{call.from_user.first_name}</a>"

    try:
        # Надсилаємо адміністратору повідомлення з посиланням на користувача
        bot.send_message(
            ADMIN_ID,
            f"Користувач {user_link} хоче скористатися знижкою.\nЗв'яжіться з ним, щоб підтвердити замовлення.",
            parse_mode="HTML"  # Використовуємо HTML замість Markdown
        )
        sent_message = bot.answer_callback_query(call.id, "Адміністратор отримав запит і в найближчий час зв'яжеться з вами!")
        time.sleep(3)  # Затримка в 3 секунди
        bot.delete_message(call.message.chat.id, sent_message.message_id)

    except Exception as e:
        print(f"Error while sending message to admin: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка. Спробуйте пізніше.")


@bot.callback_query_handler(func=lambda call: call.data in ['previous', 'next'])
def navigate_toys_callback(call):
    if call.message.chat.id in toys_by_category:
        toys = toys_by_category[call.message.chat.id]
        index = current_toy_index[call.message.chat.id]

        if call.data == 'next':
            index += 1
            if index >= len(toys):  # Якщо досягли кінця списку
                index = 0  # Повертаємося на початок
        elif call.data == 'previous':
            index -= 1
            if index < 0:  # Якщо досягли початку списку
                index = len(toys) - 1  # Переходимо до останнього товару

        current_toy_index[call.message.chat.id] = index  # Оновлюємо індекс
        send_toy_image(call.message.chat.id, toys[index][0])  # Відправляємо товар

    # Підтвердження, що колбек оброблений
    bot.answer_callback_query(call.id)


# обробник для кнопки "Додати до кошика"
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_cart_'))
def add_to_cart_callback(call):
    # отримуємо id товару з callback data
    toy_id = int(call.data.split('_')[2])
    # отримуємо id чату користувача
    chat_id = call.message.chat.id

    # перевіряємо, чи є кошик для цього користувача
    if chat_id not in user_cart:
        user_cart[chat_id] = []

    # додаємо товар до кошика, якщо його ще немає
    if toy_id not in user_cart[chat_id]:
        user_cart[chat_id].append(toy_id)
        bot.send_message(chat_id, "Товар додано до кошика!")
    else:
        bot.send_message(chat_id, "Цей товар вже в кошику!")



@bot.message_handler(func=lambda message: message.text == 'Кошик🛒')
def show_cart(message):
    chat_id = message.chat.id
    if chat_id not in user_cart or not user_cart[chat_id]:
        bot.send_message(chat_id, "Ваш кошик порожній!")
        return

    cart_items = user_cart[chat_id]
    response = "Ваш кошик:\n\n"
    total_price = 0

    # Отримуємо всі дані товарів за один запит
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, name, price FROM toys WHERE id IN ({})".format(','.join(['?'] * len(cart_items))),
                   cart_items)
    toys_data = cursor.fetchall()
    connection.close()

    for toy_data in toys_data:
        item_id, name, price = toy_data
        name = name.replace("\n", " ")  # Видалення переносів рядків
        response += f"✅ {name} - {price} грн\n"
        total_price += price

    # Створення інлайн клавіатури з кнопкою "Оформити замовлення"
    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(types.InlineKeyboardButton(f"Оформити замовлення ({total_price} грн)", callback_data='checkout'))
    inline_markup.add(types.InlineKeyboardButton("Очистити кошик❌", callback_data="clear_cart"))

    # Відправка повідомлення з кошиком та кнопкою
    bot.send_message(chat_id, response, reply_markup=inline_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'clear_cart')
def clear_cart_handler(call):
    chat_id = call.message.chat.id
    user_cart[chat_id] = []  # Очищаємо кошик
    bot.send_message(chat_id, "Ваш кошик очищено.")
    show_cart(call.message)


@bot.callback_query_handler(func=lambda call: call.data == 'checkout')
def checkout_handler(call):
    chat_id = call.message.chat.id

    # Перевіряємо, чи є дані користувача в базі
    user_data = get_user_data(chat_id)
    if user_data:
        # Формуємо текст для підтвердження
        name, phone, city, warehouse = user_data
        user_order_data[chat_id] = {
            "name": name,
            "phone": phone,
            "city": city,
            "warehouse": warehouse
        }
        confirm_message = (f"Ваші дані:\n"
                           f"ПІБ: {name}\n"
                           f"Телефон: {phone}\n"
                           f"Місто: {city}\n"
                           f"Відділення Нової Пошти: {warehouse}\n\n"
                           f"Підтвердити чи змінити?")

        # Клавіатура для підтвердження або зміни
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(types.InlineKeyboardButton("Підтвердити ✅", callback_data='confirm_user_data'))
        inline_markup.add(types.InlineKeyboardButton("Змінити ✏️", callback_data='edit_user_data'))
        bot.send_message(chat_id, confirm_message, reply_markup=inline_markup)
    else:
        # Якщо даних немає, починаємо збір нової інформації
        bot.send_message(chat_id, "Будь ласка, введіть дані для відправки🛍")
        bot.send_message(chat_id, "Введіть ваш ПІБ:")
        bot.register_next_step_handler(message=call.message, callback=process_name)


def process_name(message):
    chat_id = message.chat.id
    if chat_id not in user_order_data:
        user_order_data[chat_id] = {}

    # Оновлюємо або додаємо нове значення ПІБ
    user_order_data[chat_id]["name"] = message.text

    # Створення кнопки для надсилання контакту
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    contact_button = KeyboardButton("Надіслати свій контакт 📱", request_contact=True)
    markup.add(contact_button)

    bot.send_message(chat_id, "Надішліть ваш номер телефону⤵️", reply_markup=markup)
    bot.register_next_step_handler(message=message, callback=process_phone)


def process_phone(message):
    chat_id = message.chat.id
    if message.contact:
        user_order_data[chat_id]["phone"] = message.contact.phone_number
        bot.send_message(chat_id, "Введіть ваше місто:")
        bot.register_next_step_handler(message=message, callback=process_city)
    else:
        bot.send_message(chat_id, "Будь ласка, скористайтесь кнопкою для надсилання контакту.")
        process_name(message)  # Повертаємось до попереднього кроку


def process_city(message):
    chat_id = message.chat.id
    user_order_data[chat_id]["city"] = message.text
    bot.send_message(chat_id, "Введіть номер відділення Нової Пошти:")
    bot.register_next_step_handler(message=message, callback=process_warehouse)


def process_warehouse(message):
    chat_id = message.chat.id
    user_order_data[chat_id]["warehouse"] = message.text

    # Формування тексту для підтвердження замовлення
    order_summary = f"Ваше замовлення:\n\n"
    total_price = 0

    # Перевіряємо товари у кошику
    for item_id in user_cart.get(chat_id, []):
        try:
            connection = create_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT name, price FROM toys WHERE id = ?", (item_id,))
            toy_data = cursor.fetchone()
            connection.close()

            if toy_data:
                name, price = toy_data
                name = name.replace("\n", " ")  # Видалення переносів рядків
                order_summary += f"✅ {name} - {price} грн\n"
                total_price += price
        except Exception as e:
            bot.send_message(chat_id, f"Помилка отримання даних для товару: {e}")
            continue

    if total_price == 0:
        order_summary += "Кошик порожній. Будь ласка, додайте товари до кошика."
    else:
        order_summary += f"\nЗагальна сума: {total_price} грн\n\n"

    order_summary += f"ПІБ: {user_order_data[chat_id]['name']}\n"
    order_summary += f"Телефон: {user_order_data[chat_id]['phone']}\n"
    order_summary += f"Місто: {user_order_data[chat_id]['city']}\n"
    order_summary += f"Відділення Нової Пошти: {user_order_data[chat_id]['warehouse']}\n"

    # Клавіатура для підтвердження замовлення
    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(types.InlineKeyboardButton("Підтвердити замовлення ✅", callback_data='confirm_order'))
    inline_markup.add(types.InlineKeyboardButton("Скасувати ❌", callback_data='cancel_order'))

    bot.send_message(chat_id, order_summary, reply_markup=inline_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_user_data')
def confirm_user_data_handler(call):
    chat_id = call.message.chat.id

    # Підтвердження даних користувача
    bot.send_message(chat_id, "Ваші дані підтверджені ✅")

    # Переходимо до оформлення замовлення
    confirm_order_handler(call)


@bot.callback_query_handler(func=lambda call: call.data == 'edit_user_data')
def edit_user_data_handler(call):
    chat_id = call.message.chat.id

    # Пропонуємо змінити дані
    bot.send_message(chat_id, "Давайте оновимо ваші дані 🛠️")
    bot.send_message(chat_id, "Введіть ваш ПІБ:")
    bot.register_next_step_handler_by_chat_id(chat_id, process_name)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_order')
def confirm_order_handler(call):
    chat_id = call.message.chat.id

    # Формування тексту замовлення для адміністратора
    order_summary = f"Нове замовлення:\n\n"
    total_price = 0

    for item_id in user_cart[chat_id]:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT name, price FROM toys WHERE id = ?", (item_id,))
        toy_data = cursor.fetchone()
        connection.close()

        if toy_data:
            name, price = toy_data
            name = name.replace("\n", " ")
            order_summary += f"✅ {name} - {price} грн\n"
            total_price += price

    order_summary += f"\nЗагальна сума: {total_price} грн\n\n"
    order_summary += f"ПІБ: {user_order_data[chat_id]['name']}\n"
    order_summary += f"Телефон: {user_order_data[chat_id]['phone']}\n"
    order_summary += f"Місто: {user_order_data[chat_id]['city']}\n"
    order_summary += f"Відділення Нової Пошти: {user_order_data[chat_id]['warehouse']}\n"

    # Повідомлення користувачу
    bot.send_message(chat_id, "Ваше замовлення успішно оформлене✅\n\nМи зв'яжемося з вами для уточнення деталей\nДякуємо❤️")

    # Надсилання адміністратору
    bot.send_message(ADMIN_ID, order_summary)

    # Очищення кошика після підтвердження замовлення
    user_cart[chat_id] = []

    # Повертаємося до головного меню
    show_main_menu(call.message)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_order')
def cancel_order_handler(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Замовлення скасовано❌\nВи можете продовжити покупки")
    # Очищення тимчасових даних
    user_order_data.pop(chat_id, None)
    bot.delete_message(chat_id, call.message.message_id)
    # Повертаємося до головного меню
    show_main_menu(call.message)


# Запуск бота
bot.polling(none_stop=True)

