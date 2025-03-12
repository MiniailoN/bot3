import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import qrcode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging


API_TOKEN = '7871534369:AAEAxOCyulIgaSmqQQsV__CFn8RWTdBOePw'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class QRState(StatesGroup):
    type = State()
    data = State()
    exp = State()
    name = State()

def create_db():
    conn = sqlite3.connect('qr_codes.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS qr_codes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  qr_name TEXT,
                  qr_data TEXT,
                  expiration_date TEXT)''')
    conn.commit()
    conn.close()

create_db()

def type_kb():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="Текст", callback_data="type_text"))
    builder.add(types.InlineKeyboardButton(text="Ссылка", callback_data="type_url"))
    return builder.as_markup()

def exp_kb():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="1 день", callback_data="exp_1"))
    builder.add(types.InlineKeyboardButton(text="7 дней", callback_data="exp_7"))
    builder.add(types.InlineKeyboardButton(text="30 дней", callback_data="exp_30"))
    return builder.as_markup()

def start_kb():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="Создать QR-код", callback_data="create_qr"))
    builder.add(types.InlineKeyboardButton(text="Выбрать из уже созданных", callback_data="select_qr"))
    return builder.as_markup()

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await msg.answer("Что вы хотите сделать?", reply_markup=start_kb())

@dp.callback_query(F.data == "create_qr")
async def create_qr(query: types.CallbackQuery, state: FSMContext):
    await query.message.answer("Выберите тип данных для создания QR-кода:", reply_markup=type_kb())
    await state.set_state(QRState.type)

@dp.callback_query(F.data == "select_qr")
async def select_qr(query: types.CallbackQuery, state: FSMContext):
    conn = sqlite3.connect('qr_codes.db')
    c = conn.cursor()
    c.execute("SELECT qr_name FROM qr_codes WHERE user_id = ?", (query.from_user.id,))
    qr_codes = c.fetchall()
    conn.close()

    if qr_codes:
        builder = InlineKeyboardBuilder()
        for qr in qr_codes:
            builder.add(types.InlineKeyboardButton(text=qr[0], callback_data=f"select_{qr[0]}"))
        await query.message.answer("Выберите QR-код:", reply_markup=builder.as_markup())
    else:
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(text="Создать QR-код", callback_data="create_qr"))
        await query.message.answer("К сожалению, вы еще не создали QR-код.", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("select_"))
async def selected_qr(query: types.CallbackQuery, state: FSMContext):
    qr_name = query.data.split("_")[1]
    conn = sqlite3.connect('qr_codes.db')
    c = conn.cursor()
    c.execute("SELECT qr_data FROM qr_codes WHERE user_id = ? AND qr_name = ?", (query.from_user.id, qr_name))
    qr_data = c.fetchone()
    conn.close()

    if qr_data:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data[0])
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        img_path = f"{qr_name}.png"
        img.save(img_path)

        with open(img_path, "rb") as file:
            photo = BufferedInputFile(file.read(), filename=img_path)

        kb = InlineKeyboardBuilder()
        kb.add(types.InlineKeyboardButton(text="Создать новый QR-код", callback_data="create_qr"))
        kb.add(types.InlineKeyboardButton(text="Вывести из уже созданных", callback_data="select_qr"))

        await query.message.answer_photo(photo, caption=f"Ваш QR-код '{qr_name}' готов!", reply_markup=kb.as_markup())

        os.remove(img_path)
    else:
        await query.message.answer("Ошибка: QR-код не найден.")

@dp.callback_query(F.data.startswith("type_"))
async def type(query: types.CallbackQuery, state: FSMContext):
    data_type = query.data.split("_")[1]
    await state.update_data({"type": data_type})  
    await query.message.answer(f"Вы выбрали тип данных: {data_type}. Теперь введите данные:")
    await state.set_state(QRState.data)

@dp.message(QRState.data)
async def data(msg: types.Message, state: FSMContext):
    await state.update_data({"data": msg.text})  
    await msg.answer("Теперь выберите срок хранения QR-кода:", reply_markup=exp_kb())
    await state.set_state(QRState.exp)

@dp.callback_query(F.data.startswith("exp_"))
async def exp(query: types.CallbackQuery, state: FSMContext):
    days = int(query.data.split("_")[1])
    exp_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    await state.update_data({"exp": exp_date})  
    await query.message.answer(f"Срок хранения установлен на {days} дней. Теперь введите название для QR-кода:")
    await state.set_state(QRState.name)

@dp.message(QRState.name)
async def name(msg: types.Message, state: FSMContext):
    user_data = await state.get_data()
    qr_name = msg.text
    qr_data = user_data.get("data", "")
    exp_date = user_data.get("exp", "")

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_path = f"{qr_name}.png"
    img.save(img_path)

    with open(img_path, "rb") as file:
        photo = BufferedInputFile(file.read(), filename=img_path)

    conn = sqlite3.connect('qr_codes.db')
    c = conn.cursor()
    c.execute("INSERT INTO qr_codes (user_id, qr_name, qr_data, expiration_date) VALUES (?, ?, ?, ?)",
              (msg.from_user.id, qr_name, qr_data, exp_date))
    conn.commit()
    conn.close()

    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Создать новый QR-код", callback_data="create_qr"))
    kb.add(types.InlineKeyboardButton(text="Вывести из уже созданных", callback_data="select_qr"))

    await msg.answer_photo(photo, caption=f"Ваш QR-код '{qr_name}' готов!", reply_markup=kb.as_markup())

    os.remove(img_path)

    await state.clear()

if __name__ == '__main__':
    dp.run_polling(bot)