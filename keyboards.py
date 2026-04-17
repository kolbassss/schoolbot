from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_keyboard(mode="school", context_on=True):
    mode_icon = "📚" if mode == "school" else "💬"
    context_icon = "✅" if context_on else "❌"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 поиск")],
            [KeyboardButton(text="🔔 звонки"), KeyboardButton(text="📍 адрес")],
            [
                KeyboardButton(text=f"🔄 режим: {mode_icon}"),
                KeyboardButton(text=f"🔄 контекст: {context_icon}")
            ],
            [KeyboardButton(text="👤 профиль")]
        ],
        resize_keyboard=True
    )