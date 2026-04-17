from aiogram import Router, F, types
from aiogram.filters import Command
from keyboards import get_keyboard
from utils import log
from config import LIMITS
import engine

router = Router()

@router.message(Command("start"))
async def start_cmd(msg: types.Message):
    session = engine.get_session(msg.from_user.id)
    if session:
        kb = get_keyboard(session.get("mode", "school"), session.get("context_on", True))
        await msg.answer(f"вы уже в системе.", reply_markup=kb)
    else:
        await msg.answer("🔒 введите пароль для входа:")

@router.message(F.text == "👤 профиль")
async def profile_cmd(msg: types.Message):
    session = engine.get_session(msg.from_user.id)
    if not session:
        await msg.answer("введите пароль для входа")
        return
    limit = LIMITS.get(session['role'], 5)
    used = session['queries_today']
    left_str = "∞" if limit > 9999 else str(limit - used)
    mode_str = "📚 Школа" if session.get('mode') == 'school' else "💬 Чат"
    ctx_status = "✅ Вкл" if session.get('context_on') else "❌ Выкл"
    
    text = (
        f"👤 **ваш профиль**\nРоль доступа: `{session['role']}`\n"
        f"режим: {mode_str}\n"
        f"контекст: {ctx_status}\n"
        f"запросов сегодня: {used}\nОсталось: {left_str}"
    )
    await msg.answer(text, parse_mode="Markdown")

@router.message(F.text.startswith("🔄 режим:"))
async def toggle_mode(msg: types.Message):
    session = engine.get_session(msg.from_user.id)
    if not session:
        await msg.answer("сначала введите пароль!")
        return
    current_mode = session.get("mode", "school")
    if current_mode == "school":
        session["mode"] = "default ai"
        new_text = "режим переключен: 💬 ПРОСТО ЧАТ"
    else:
        session["mode"] = "school"
        new_text = "режим переключен: 📚 ШКОЛА"
    
    log(f"mode change to {session['mode']} for user {msg.from_user.id}")
    kb = get_keyboard(session["mode"], session.get("context_on", True))
    await msg.answer(new_text, reply_markup=kb)

@router.message(F.text.startswith("🔄 Контекст:"))
async def toggle_context(msg: types.Message):
    session = engine.get_session(msg.from_user.id)
    if not session:
        await msg.answer("сначала введите пароль!")
        return
    
    session["context_on"] = not session.get("context_on", True)
    status_text = "ВКЛЮЧЕН ✅" if session["context_on"] else "ВЫКЛЮЧЕН ❌"
    
    log(f"context toggle to {session['context_on']} for user {msg.from_user.id}")
    kb = get_keyboard(session.get("mode", "school"), session["context_on"])
    await msg.answer(f"контекст (память) теперь: {status_text}", reply_markup=kb)

@router.message(F.text == "🔍 Поиск")
async def search_button(msg: types.Message):
    session = engine.get_session(msg.from_user.id)
    if not session: await msg.answer("сначала введите пароль!")
    else: await msg.answer("пишите вопрос 👇")

@router.message(F.text == "📍 Адрес")
async def address_btn(msg: types.Message):
    text = (
        "🏫 **адрес школы:**\n"
        "г. Иркутск, ул. Карла Либкнехта, д. 131\n\n"
        "📞 **Телефон:** +7 (3952) 29-10-44\n"
        "📧 **Email:** school14@irkutsk.ru"
    )
    await msg.answer(text, parse_mode="Markdown")

@router.message(F.text == "🔔 Звонки")
async def bells_btn(msg: types.Message):
    text = (
        "🔔 **РАСПИСАНИЕ ЗВОНКОВ** 🔔\n\n"
        "🌅 **1 СМЕНА**\n"
        "1 урок: 08:00 – 08:40  (перемена 15 мин)\n"
        "2 урок: 08:55 – 09:35  (перемена 15 мин)\n"
        "3 урок: 09:50 – 10:30  (перемена 15 мин)\n"
        "4 урок: 10:45 – 11:25  (перемена 15 мин)\n"
        "5 урок: 11:40 – 12:20  (перемена 5 мин)\n"
        "6 урок: 12:25 – 13:05  (перемена 5 мин)\n"
        "7 урок: 13:10 – 13:50\n\n"
        "🌇 **2 СМЕНА**\n"
        "1 урок: 14:00 – 14:40  (перемена 15 мин)\n"
        "2 урок: 14:55 – 15:35  (перемена 15 мин)\n"
        "3 урок: 15:50 – 16:30  (перемена 15 мин)\n"
        "4 урок: 16:45 – 17:25  (перемена 15 мин)\n"
        "5 урок: 17:40 – 18:20  (перемена 5 мин)\n"
        "6 урок: 18:25 – 19:05  (перемена 5 мин)\n"
        "7 урок: 19:10 – 19:50"
    )
    await msg.answer(text, parse_mode="Markdown")

@router.message(F.text)
async def message_handler(msg: types.Message):
    user_id = msg.from_user.id
    text = msg.text.strip()
    session = engine.get_session(user_id)
    
    log(f"user send message {user_id}")

    if not session:
        if text in engine.valid_users:
            role = engine.valid_users[text]
            engine.create_session(user_id, text, role)
            kb = get_keyboard("school", True)
            await msg.answer(f"✅ вход выполнен", reply_markup=kb)
            return
        else:
            await msg.answer("⛔ неверный пароль")
            return

    limit = LIMITS.get(session['role'], 5)
    if session['queries_today'] >= limit:
        log(f" limit is full for {user_id}")
        await msg.answer("🛑 лимит запросов на сегодня исчерпан")
        return

    placeholder_message = await msg.answer("⏳ _Думаю..._", parse_mode="Markdown")
    answer = await engine.stream_answer(text, session, placeholder_message, user_id)
    
    session['queries_today'] += 1
    
    session['history'].append((text, answer))
    if len(session['history']) > 3:
        session['history'].pop(0)
        log(f"sdvig for user {user_id}")
    
    log(f"len of history context in user chat: {len(session['history'])} for {user_id}")