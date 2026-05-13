import asyncio
import sqlite3
import uuid
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = "8591288402:AAFDHGwmKBw0VFz2N_X0QTq1trlDAsP-vmM"
MAX_STREAKS_PER_USER = 3

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = sqlite3.connect("streak.db")
db.row_factory = sqlite3.Row
cursor = db.cursor()


def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pairs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1 INTEGER NOT NULL,
        user2 INTEGER NOT NULL,
        user1_name TEXT NOT NULL,
        user2_name TEXT NOT NULL,
        streak INTEGER NOT NULL DEFAULT 1,
        last_day TEXT NOT NULL,
        UNIQUE(user1, user2)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invites(
        code TEXT PRIMARY KEY,
        inviter INTEGER NOT NULL,
        inviter_name TEXT NOT NULL
    )
    """)

    db.commit()


init_db()


def today_str() -> str:
    return date.today().isoformat()


def display_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    if user.full_name:
        return user.full_name
    return str(user.id)


def normalize_pair(user1: int, user2: int, user1_name: str, user2_name: str):
    if user1 < user2:
        return user1, user2, user1_name, user2_name
    return user2, user1, user2_name, user1_name


def create_invite(inviter: int, inviter_name: str) -> str:
    code = str(uuid.uuid4())[:8]
    cursor.execute(
        "INSERT INTO invites(code, inviter, inviter_name) VALUES(?, ?, ?)",
        (code, inviter, inviter_name)
    )
    db.commit()
    return code


def get_invite(code: str):
    cursor.execute("SELECT * FROM invites WHERE code=?", (code,))
    return cursor.fetchone()


def delete_invite(code: str):
    cursor.execute("DELETE FROM invites WHERE code=?", (code,))
    db.commit()


def get_user_pairs(user_id: int):
    cursor.execute(
        "SELECT * FROM pairs WHERE user1=? OR user2=? ORDER BY id DESC",
        (user_id, user_id)
    )
    return cursor.fetchall()


def get_pair_by_id(pair_id: int):
    cursor.execute("SELECT * FROM pairs WHERE id=?", (pair_id,))
    return cursor.fetchone()


def pair_exists_between(user1: int, user2: int):
    cursor.execute(
        "SELECT * FROM pairs WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)",
        (user1, user2, user2, user1)
    )
    return cursor.fetchone()


def count_user_pairs(user_id: int) -> int:
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM pairs WHERE user1=? OR user2=?",
        (user_id, user_id)
    )
    row = cursor.fetchone()
    return row["cnt"]


def create_pair(inviter_id: int, invited_id: int, inviter_name: str, invited_name: str):
    u1, u2, n1, n2 = normalize_pair(inviter_id, invited_id, inviter_name, invited_name)

    if pair_exists_between(u1, u2):
        return False, "already_exists"

    if count_user_pairs(inviter_id) >= MAX_STREAKS_PER_USER:
        return False, "inviter_limit"

    if count_user_pairs(invited_id) >= MAX_STREAKS_PER_USER:
        return False, "invited_limit"

    cursor.execute(
        """
        INSERT INTO pairs(user1, user2, user1_name, user2_name, streak, last_day)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (u1, u2, n1, n2, 1, today_str())
    )
    db.commit()
    return True, "ok"


def delete_pair(pair_id: int):
    cursor.execute("DELETE FROM pairs WHERE id=?", (pair_id,))
    deleted = cursor.rowcount
    db.commit()
    return deleted > 0


def delete_pair_for_user(user_id: int):
    cursor.execute(
        "DELETE FROM pairs WHERE user1=? OR user2=?",
        (user_id, user_id)
    )
    deleted = cursor.rowcount
    db.commit()
    return deleted > 0


def get_partner_name(pair, current_user_id: int) -> str:
    if current_user_id == pair["user1"]:
        return pair["user2_name"]
    return pair["user1_name"]


def user_in_pair(pair, user_id: int) -> bool:
    return pair["user1"] == user_id or pair["user2"] == user_id


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔥 Создать приглашение")],
            [KeyboardButton(text="👥 Огоньки")],
            [KeyboardButton(text="✅ Отметиться")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="💔 Удалить огонёк")]
        ],
        resize_keyboard=True
    )

def build_pairs_inline_keyboard(user_id: int, action: str):
    pairs = get_user_pairs(user_id)

    if not pairs:
        return None

    rows = []
    for pair in pairs:
        partner_name = get_partner_name(pair, user_id)
        rows.append([
            InlineKeyboardButton(
                text=f"{partner_name} • 🔥 {pair['streak']}",
                callback_data=f"{action}:{pair['id']}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
async def start_handler(message: Message):
    try:
        text = message.text or ""

        if "invite_" in text:
            code = text.split("invite_")[1].strip()
            invite = get_invite(code)

            if not invite:
                await message.answer("Приглашение не найдено.")
                return

            inviter = invite["inviter"]
            inviter_name = invite["inviter_name"]

            if inviter == message.from_user.id:
                await message.answer("Нельзя принять своё приглашение.")
                return

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔥 Принять", callback_data=f"accept:{code}")],
                    [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{code}")]
                ]
            )

            await message.answer(
                f"{inviter_name} приглашает тебя начать огонёк 🔥",
                reply_markup=kb
            )
            return

        await message.answer(
            "🔥 Бот огоньков\n\n"
            f"У тебя может быть до {MAX_STREAKS_PER_USER} огоньков одновременно.",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print("Ошибка в start_handler:", e)
        await message.answer("Произошла ошибка в /start.")

@dp.message(F.text == "/menu")
async def menu_handler(message: Message):
    await message.answer(
        "Обновляю меню:",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "🔥 Создать приглашение")
async def invite_handler(message: Message):
    try:
        if count_user_pairs(message.from_user.id) >= MAX_STREAKS_PER_USER:
            await message.answer(
                f"У тебя уже максимум огоньков: {MAX_STREAKS_PER_USER}."
            )
            return

        inviter_name = display_name(message.from_user)
        code = create_invite(message.from_user.id, inviter_name)

        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=invite_{code}"

        await message.answer(
            "Отправь эту ссылку другу:\n\n"
            f"{link}"
        )
    except Exception as e:
        print("Ошибка в invite_handler:", e)
        await message.answer("Не удалось создать приглашение.")


@dp.message(F.text.func(lambda text: text and "огоньк" in text.lower()))
async def my_pairs_handler(message: Message):
    try:
        pairs = get_user_pairs(message.from_user.id)

        if not pairs:
            await message.answer("У тебя пока нет активных огоньков.")
            return

        lines = ["👥 Твои огоньки:\n"]
        for i, pair in enumerate(pairs, start=1):
            partner_name = get_partner_name(pair, message.from_user.id)
            lines.append(
                f"{i}. {partner_name} — 🔥 {pair['streak']} дней — 📅 {pair['last_day']}"
            )

        await message.answer("\n".join(lines))
    except Exception as e:
        print("Ошибка в my_pairs_handler:", e)
        await message.answer("Не удалось показать список огоньков.")

@dp.message(F.text == "/fires")
async def my_pairs_command_handler(message: Message):
    try:
        pairs = get_user_pairs(message.from_user.id)

        if not pairs:
            await message.answer("У тебя пока нет активных огоньков.")
            return

        lines = ["👥 Твои огоньки:\n"]
        for i, pair in enumerate(pairs, start=1):
            partner_name = get_partner_name(pair, message.from_user.id)
            lines.append(
                f"{i}. {partner_name} — 🔥 {pair['streak']} дней — 📅 {pair['last_day']}"
            )

        await message.answer("\n".join(lines))
    except Exception as e:
        print("Ошибка в my_pairs_command_handler:", e)
        await message.answer("Не удалось показать список огоньков.")

@dp.message(F.text == "📊 Статистика")
async def stats_handler(message: Message):
    try:
        pairs = get_user_pairs(message.from_user.id)

        if not pairs:
            await message.answer("У тебя нет активных огоньков.")
            return

        kb = build_pairs_inline_keyboard(message.from_user.id, "stats")
        await message.answer(
            "Выбери огонёк для просмотра статистики:",
            reply_markup=kb
        )
    except Exception as e:
        print("Ошибка в stats_handler:", e)
        await message.answer("Не удалось открыть статистику.")


@dp.callback_query(F.data.startswith("stats:"))
async def stats_pair_handler(callback: CallbackQuery):
    try:
        pair_id = int(callback.data.split(":", 1)[1])
        pair = get_pair_by_id(pair_id)

        if not pair or not user_in_pair(pair, callback.from_user.id):
            await callback.answer("Огонёк не найден", show_alert=True)
            return

        partner_name = get_partner_name(pair, callback.from_user.id)

        await callback.message.edit_text(
            f"📊 Статистика\n"
            f"👤 Пара: {partner_name}\n"
            f"🔥 Текущий streak: {pair['streak']} дней\n"
            f"📅 Последняя активность: {pair['last_day']}"
        )
        await callback.answer()
    except Exception as e:
        print("Ошибка в stats_pair_handler:", e)
        await callback.answer("Ошибка статистики", show_alert=True)


@dp.message(F.text == "✅ Отметиться")
async def checkin_handler(message: Message):
    try:
        pairs = get_user_pairs(message.from_user.id)

        if not pairs:
            await message.answer("У тебя нет активных огоньков.")
            return

        kb = build_pairs_inline_keyboard(message.from_user.id, "checkin")
        await message.answer(
            "Выбери, для какого огонька отметить активность:",
            reply_markup=kb
        )
    except Exception as e:
        print("Ошибка в checkin_handler:", e)
        await message.answer("Не удалось открыть выбор огонька.")


@dp.callback_query(F.data.startswith("checkin:"))
async def checkin_pair_handler(callback: CallbackQuery):
    try:
        pair_id = int(callback.data.split(":", 1)[1])
        pair = get_pair_by_id(pair_id)

        if not pair or not user_in_pair(pair, callback.from_user.id):
            await callback.answer("Огонёк не найден", show_alert=True)
            return

        today = today_str()

        if pair["last_day"] != today:
            cursor.execute(
                "UPDATE pairs SET streak = streak + 1, last_day=? WHERE id=?",
                (today, pair_id)
            )
            db.commit()
            pair = get_pair_by_id(pair_id)

            await callback.message.edit_text(
                f"✅ Отметка засчитана!\n"
                f"👤 {get_partner_name(pair, callback.from_user.id)}\n"
                f"🔥 Огонёк: {pair['streak']} дней"
            )
        else:
            await callback.message.edit_text(
                f"✅ Сегодня уже отмечено.\n"
                f"👤 {get_partner_name(pair, callback.from_user.id)}\n"
                f"🔥 Огонёк: {pair['streak']} дней"
            )

        await callback.answer()
    except Exception as e:
        print("Ошибка в checkin_pair_handler:", e)
        await callback.answer("Ошибка отметки", show_alert=True)


@dp.message(F.text == "💔 Удалить огонёк")
async def delete_handler(message: Message):
    try:
        pairs = get_user_pairs(message.from_user.id)

        if not pairs:
            await message.answer("У тебя нет активных огоньков.")
            return

        kb = build_pairs_inline_keyboard(message.from_user.id, "deletepair")
        await message.answer(
            "Выбери, какой огонёк удалить:",
            reply_markup=kb
        )
    except Exception as e:
        print("Ошибка в delete_handler:", e)
        await message.answer("Не удалось открыть удаление.")


@dp.callback_query(F.data.startswith("deletepair:"))
async def delete_pair_handler(callback: CallbackQuery):
    try:
        pair_id = int(callback.data.split(":", 1)[1])
        pair = get_pair_by_id(pair_id)

        if not pair or not user_in_pair(pair, callback.from_user.id):
            await callback.answer("Огонёк не найден", show_alert=True)
            return

        partner_name = get_partner_name(pair, callback.from_user.id)
        delete_pair(pair_id)

        await callback.message.edit_text(
            f"💔 Огонёк с {partner_name} удалён."
        )
        await callback.answer()
    except Exception as e:
        print("Ошибка в delete_pair_handler:", e)
        await callback.answer("Ошибка удаления", show_alert=True)


@dp.callback_query(F.data.startswith("accept:"))
async def accept_handler(callback: CallbackQuery):
    try:
        code = callback.data.split(":", 1)[1]
        invite = get_invite(code)

        if not invite:
            await callback.answer("Приглашение не найдено", show_alert=True)
            return

        inviter = invite["inviter"]
        inviter_name = invite["inviter_name"]
        invited_user = callback.from_user.id
        invited_name = display_name(callback.from_user)

        if inviter == invited_user:
            await callback.answer("Нельзя принять своё приглашение", show_alert=True)
            return

        created, reason = create_pair(inviter, invited_user, inviter_name, invited_name)
        delete_invite(code)

        if not created:
            if reason == "already_exists":
                await callback.message.edit_text("Такой огонёк уже существует.")
            elif reason == "inviter_limit":
                await callback.message.edit_text("У пригласившего уже максимум огоньков.")
            elif reason == "invited_limit":
                await callback.message.edit_text("У тебя уже максимум огоньков.")
            else:
                await callback.message.edit_text("Не удалось создать огонёк.")
            return

        await callback.message.edit_text(
            f"Огонёк создан 🔥\n\n"
            f"Пара: {inviter_name} + {invited_name}"
        )
        await callback.answer("Приглашение принято")

        try:
            await bot.send_message(inviter, f"🔥 {invited_name} принял(а) приглашение!")
        except Exception as e:
            print("Ошибка отправки сообщения пригласившему:", e)

    except Exception as e:
        print("Ошибка в accept_handler:", e)
        await callback.answer("Ошибка при принятии приглашения", show_alert=True)


@dp.callback_query(F.data.startswith("decline:"))
async def decline_handler(callback: CallbackQuery):
    try:
        code = callback.data.split(":", 1)[1]
        delete_invite(code)

        await callback.message.edit_text("Приглашение отклонено ❌")
        await callback.answer("Отклонено")
    except Exception as e:
        print("Ошибка в decline_handler:", e)
        await callback.answer("Ошибка при отклонении", show_alert=True)


async def reminder():
    try:
        cursor.execute("SELECT * FROM pairs")
        rows = cursor.fetchall()

        for pair in rows:
            try:
                await bot.send_message(
                    pair["user1"],
                    f"⚠️ Не забудь отметить огонёк с {pair['user2_name']}!"
                )
            except Exception as e:
                print("Ошибка reminder user1:", e)

            try:
                await bot.send_message(
                    pair["user2"],
                    f"⚠️ Не забудь отметить огонёк с {pair['user1_name']}!"
                )
            except Exception as e:
                print("Ошибка reminder user2:", e)
    except Exception as e:
        print("Ошибка в reminder:", e)


async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(reminder, "cron", hour=21, minute=0)
    scheduler.start()

    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())