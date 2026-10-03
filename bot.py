# bot.py — Havola-sahifa buyurtma boti, kengaytirilgan versiya (aiogram 3)
# O'rnatish:  pip install aiogram
# Ishga tushirish:  python bot.py
#
# Mijoz:  namunalar, narxlar, savol-javob, buyurtma berish, buyurtmalarim, savol berish
# Admin:  /admin  — buyurtmalar, holat o'zgartirish, javob yozish, statistika, xabar tarqatish
import asyncio
import html
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ====== SOZLAMALAR: o'zingiznikiga almashtiring ======
BOT_TOKEN = "8933220717:AAEHLVZJtaweEkaYRq4Dza8Rn5hFAQgIN2Q" 
ADMIN_ID = 5550228074 
SAMPLES_URL = "https://iymona-s-logo.onrender.com" 
CONTACT_TG = "@Iymane011"
CONTACT_IG = "https://www.instagram.com/iyman01114"
CONTACT_PHONE = "+998 99 610 16 48"

PLANS = {
    "basic": ("Oddiy", "100 000 so'mdan", ["4 tagacha tugma", "Ism va tavsif", "Rang tanlash", "Tayyor havola"]),
    "custom": ("Shaxsiy dizayn", "250 000 so'mdan", ["Logotip va brend ranglari", "Stikerlar va bezak", "Hosting va havolani joylash", "1 marta bepul o'zgartirish"]),
    "premium": ("Premium", "500 000 so'mdan", ["8 va undan ko'p tugma", "Bosilishlar hisobi", "O'z domeningiz", "1 oy qo'llab-quvvatlash"]),
}

# Savol-javob: o'zingizga mos qilib o'zgartiring
FAQ = [
    ("Qancha vaqtda tayyor bo'ladi?", "Odatda 1 kun ichida."),
    ("Logotipim yo'q bo'lsa-chi?", "Muammo emas, brend nomingiz bilan oddiy belgi qo'yamiz."),
    ("Keyin o'zgartirsam bo'ladimi?", "Shaxsiy dizayn tarifida 1 marta bepul o'zgartirish bor, keyingisi kelishuv bo'yicha."),
    ("To'lov qanday?", "To'lov usulini buyurtma tasdiqlanganda kelishamiz."),
]

STATUS = {"new": "🆕 Yangi", "work": "🛠 Jarayonda", "done": "✅ Tayyor", "cancel": "❌ Bekor qilingan"}
NOTIFY = {
    "work": "🛠 Buyurtmangiz #{id} ustida ish boshlandi.",
    "done": "✅ Buyurtmangiz #{id} tayyor! Tez orada siz bilan bog'lanamiz.",
    "cancel": "❌ Buyurtmangiz #{id} bekor qilindi. Savolingiz bo'lsa, yozing.",
}

# ---------------- Ma'lumotlar bazasi (SQLite, fayl: bot.db) ----------------
DB = sqlite3.connect("bot.db", check_same_thread=False)
DB.row_factory = sqlite3.Row
DB.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan TEXT, brand TEXT, bio TEXT, links TEXT,
  logo TEXT, logo_kind TEXT, colors TEXT, phone TEXT, status TEXT DEFAULT 'new', created TEXT);
""")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def db_all(sql, args=()):
    return DB.execute(sql, args).fetchall()


def db_one(sql, args=()):
    return DB.execute(sql, args).fetchone()


def db_run(sql, args=()):
    cur = DB.execute(sql, args)
    DB.commit()
    return cur.lastrowid


def esc(x):
    return html.escape(str(x or ""))


# ---------------- Klaviaturalar ----------------
def kb(rows, adjust=(1,)):
    b = InlineKeyboardBuilder()
    for text, data in rows:
        b.button(text=text, callback_data=data)
    b.adjust(*adjust)
    return b.as_markup()


def menu_kb():
    return kb([("🌸 Namunalar", "samples"), ("💰 Narxlar", "prices"),
               ("📝 Buyurtma berish", "order"), ("📦 Buyurtmalarim", "my"),
               ("❓ Savol-javob", "faq"), ("💬 Savol berish", "ask"),
               ("📞 Aloqa", "contact")], (2, 2, 2, 1))


def admin_order_kb(order_id, user_id):
    return kb([("🛠 Jarayonda", f"st:{order_id}:work"), ("✅ Tayyor", f"st:{order_id}:done"),
               ("❌ Bekor", f"st:{order_id}:cancel"), ("↩️ Javob yozish", f"reply:{user_id}")], (3, 1))


class Order(StatesGroup):
    plan = State(); brand = State(); bio = State(); links = State()
    logo = State(); colors = State(); phone = State(); confirm = State()


class Ask(StatesGroup):
    text = State()


class Reply(StatesGroup):
    text = State()


dp = Dispatcher(storage=MemoryStorage())
is_admin = F.from_user.id == ADMIN_ID


def order_text(o):
    return (f"<b>Tarif:</b> {esc(o['plan'])}\n<b>Brend:</b> {esc(o['brand'])}\n<b>Tavsif:</b> {esc(o['bio'])}\n"
            f"<b>Havolalar:</b>\n{esc(o['links'])}\n<b>Logotip:</b> {'bor' if o['logo'] else 'yoq'}\n"
            f"<b>Ranglar:</b> {esc(o['colors'])}\n<b>Telefon:</b> {esc(o['phone'])}")


def who(u):
    return f"@{u.username}" if u.username else f'<a href="tg://user?id={u.id}">{esc(u.full_name)}</a>'


# ---------------- Asosiy menyu ----------------
@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    db_run("INSERT OR IGNORE INTO users(id,username,full_name,created) VALUES(?,?,?,?)",
           (m.from_user.id, m.from_user.username, m.from_user.full_name, now()))
    await m.answer("Salom! 🌸\n\nInstagram uchun <b>havola-sahifa</b> yasab beramiz: "
                   "bitta havola — barcha tugmalaringiz. 1 kunda tayyor.", reply_markup=menu_kb())


@dp.callback_query(F.data == "samples")
async def samples(c: CallbackQuery):
    await c.message.answer(f"Namunalarimiz:\n{SAMPLES_URL}", reply_markup=menu_kb())
    await c.answer()


@dp.callback_query(F.data == "prices")
async def prices(c: CallbackQuery):
    t = "\n\n".join(f"<b>{n}</b> — {p}\n" + "\n".join(f"  • {f}" for f in fs) for n, p, fs in PLANS.values())
    await c.message.answer(t, reply_markup=menu_kb())
    await c.answer()


@dp.callback_query(F.data == "faq")
async def faq(c: CallbackQuery):
    t = "\n\n".join(f"<b>{q}</b>\n{a}" for q, a in FAQ)
    await c.message.answer(t, reply_markup=menu_kb())
    await c.answer()


@dp.callback_query(F.data == "contact")
async def contact(c: CallbackQuery):
    await c.message.answer(f"Telegram: {CONTACT_TG}\nInstagram: {CONTACT_IG}\nTelefon: {CONTACT_PHONE}",
                           reply_markup=menu_kb())
    await c.answer()


@dp.callback_query(F.data == "my")
async def my_orders(c: CallbackQuery):
    rows = db_all("SELECT id,brand,plan,status,created FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5",
                  (c.from_user.id,))
    if not rows:
        t = "Sizda hali buyurtma yo'q."
    else:
        t = "<b>Oxirgi buyurtmalaringiz:</b>\n\n" + "\n".join(
            f"#{r['id']} · {esc(r['brand'])} · {esc(r['plan'])}\n   {STATUS[r['status']]} · {r['created']}" for r in rows)
    await c.message.answer(t, reply_markup=menu_kb())
    await c.answer()


@dp.message(Command("cancel"))
@dp.callback_query(F.data == "cancel")
async def cancel(event, state: FSMContext):
    await state.clear()
    msg = event.message if isinstance(event, CallbackQuery) else event
    await msg.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await msg.answer("Menyu:", reply_markup=menu_kb())
    if isinstance(event, CallbackQuery):
        await event.answer()


# ---------------- Savol berish (mijoz -> admin) ----------------
@dp.callback_query(F.data == "ask")
async def ask_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(Ask.text)
    await c.message.answer("Savolingizni yozing, tez orada javob beramiz. (Bekor qilish: /cancel)")
    await c.answer()


@dp.message(Ask.text, F.text)
async def ask_send(m: Message, state: FSMContext, bot: Bot):
    await bot.send_message(ADMIN_ID, f"💬 <b>Yangi savol</b>\nMijoz: {who(m.from_user)}\n\n{esc(m.text)}",
                           reply_markup=kb([("↩️ Javob yozish", f"reply:{m.from_user.id}")]))
    await state.clear()
    await m.answer("Savolingiz yuborildi 💗", reply_markup=menu_kb())


# ---------------- Admin: javob yozish va holat o'zgartirish ----------------
@dp.callback_query(is_admin, F.data.startswith("reply:"))
async def reply_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(Reply.text)
    await state.update_data(target=int(c.data.split(":")[1]))
    await c.message.answer("Mijozga javobingizni yozing (bekor qilish: /cancel):")
    await c.answer()


@dp.message(is_admin, Reply.text, F.text)
async def reply_send(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    try:
        await bot.send_message(d["target"], f"💬 <b>Javob:</b>\n{esc(m.text)}")
        await m.answer("Yuborildi ✅")
    except Exception as e:
        await m.answer(f"Yuborib bo'lmadi: {esc(e)}")
    await state.clear()


@dp.callback_query(is_admin, F.data.startswith("st:"))
async def set_status(c: CallbackQuery, bot: Bot):
    _, oid, st = c.data.split(":")
    o = db_one("SELECT user_id FROM orders WHERE id=?", (oid,))
    if not o:
        return await c.answer("Buyurtma topilmadi", show_alert=True)
    db_run("UPDATE orders SET status=? WHERE id=?", (st, oid))
    try:
        await bot.send_message(o["user_id"], NOTIFY[st].format(id=oid))
    except Exception:
        pass
    await c.answer(f"#{oid}: {STATUS[st]}")
    await c.message.reply(f"Buyurtma #{oid} holati: {STATUS[st]}")


# ---------------- Admin buyruqlari ----------------
@dp.message(is_admin, Command("admin"))
async def admin_help(m: Message):
    await m.answer("<b>Admin buyruqlari:</b>\n/orders — oxirgi 10 buyurtma\n/order 5 — #5 buyurtma\n"
                   "/stats — statistika\n/broadcast matn — hammaga xabar yuborish")


@dp.message(is_admin, Command("orders"))
async def orders_list(m: Message):
    rows = db_all("SELECT id,brand,status,created FROM orders ORDER BY id DESC LIMIT 10")
    t = "\n".join(f"#{r['id']} · {esc(r['brand'])} · {STATUS[r['status']]} · {r['created']}" for r in rows)
    await m.answer(t or "Buyurtmalar yo'q.")


@dp.message(is_admin, Command("order"))
async def order_show(m: Message, command: CommandObject):
    if not command.args or not command.args.strip().isdigit():
        return await m.answer("Misol: /order 5")
    o = db_one("SELECT * FROM orders WHERE id=?", (int(command.args),))
    if not o:
        return await m.answer("Topilmadi.")
    await m.answer(f"<b>Buyurtma #{o['id']}</b> · {STATUS[o['status']]}\n\n{order_text(o)}",
                   reply_markup=admin_order_kb(o["id"], o["user_id"]))


@dp.message(is_admin, Command("stats"))
async def stats(m: Message):
    users = db_one("SELECT COUNT(*) c FROM users")["c"]
    by = {r["status"]: r["c"] for r in db_all("SELECT status, COUNT(*) c FROM orders GROUP BY status")}
    t = f"👥 Foydalanuvchilar: {users}\n📦 Buyurtmalar: {sum(by.values())}\n" + "\n".join(
        f"{STATUS[k]}: {by.get(k, 0)}" for k in STATUS)
    await m.answer(t)


@dp.message(is_admin, Command("broadcast"))
async def broadcast(m: Message, command: CommandObject, bot: Bot):
    if not command.args:
        return await m.answer("Misol: /broadcast Yangi aksiya! 🌸")
    ok = bad = 0
    for r in db_all("SELECT id FROM users"):
        try:
            await bot.send_message(r["id"], command.args)
            ok += 1
        except Exception:
            bad += 1
        await asyncio.sleep(0.05)
    await m.answer(f"Yuborildi: {ok}, yuborilmadi: {bad}")


# ---------------- Buyurtma jarayoni ----------------
@dp.callback_query(F.data == "order")
async def order_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(Order.plan)
    rows = [(f"{n} — {p}", f"plan:{k}") for k, (n, p, _) in PLANS.items()] + [("❌ Bekor qilish", "cancel")]
    await c.message.answer("Qaysi tarifni tanlaysiz?", reply_markup=kb(rows))
    await c.answer()


@dp.callback_query(Order.plan, F.data.startswith("plan:"))
async def got_plan(c: CallbackQuery, state: FSMContext):
    await state.update_data(plan=PLANS[c.data.split(":", 1)[1]][0])
    await state.set_state(Order.brand)
    await c.message.answer("Brend (do'kon) nomi qanday? Masalan: <i>Dila_Shopping</i>")
    await c.answer()


@dp.message(Order.brand, F.text)
async def got_brand(m: Message, state: FSMContext):
    await state.update_data(brand=m.text.strip())
    await state.set_state(Order.bio)
    await m.answer("Qisqa tavsif yozing. Masalan: <i>Amerikadan original kosmetikalar</i>")


@dp.message(Order.bio, F.text)
async def got_bio(m: Message, state: FSMContext):
    await state.update_data(bio=m.text.strip())
    await state.set_state(Order.links)
    await m.answer("Sahifangizda qaysi tugmalar bo'lsin? 🌸):\n"
                   "<i>Telegram kanal: https://t.me/...\nInstagram: https://instagram.com/...\nTelefon: +998...</i>")


@dp.message(Order.links, F.text)
async def got_links(m: Message, state: FSMContext):
    await state.update_data(links=m.text.strip())
    await state.set_state(Order.logo)
    await m.answer("Logotipingizni rasm qilib yuboring.", reply_markup=kb([("O'tkazib yuborish", "skip_logo")]))


async def ask_colors(m: Message, state: FSMContext):
    await state.set_state(Order.colors)
    await m.answer("Qaysi ranglarni xohlaysiz? Masalan: <i>pushti va jigarrang</i>",
                   reply_markup=kb([("O'tkazib yuborish", "skip_colors")]))


@dp.message(Order.logo, F.photo)
async def logo_photo(m: Message, state: FSMContext):
    await state.update_data(logo=m.photo[-1].file_id, logo_kind="photo")
    await ask_colors(m, state)


@dp.message(Order.logo, F.document)
async def logo_doc(m: Message, state: FSMContext):
    await state.update_data(logo=m.document.file_id, logo_kind="document")
    await ask_colors(m, state)


@dp.callback_query(Order.logo, F.data == "skip_logo")
async def skip_logo(c: CallbackQuery, state: FSMContext):
    await state.update_data(logo=None, logo_kind=None)
    await ask_colors(c.message, state)
    await c.answer()


async def ask_phone(m: Message, state: FSMContext):
    await state.set_state(Order.phone)
    k = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)]],
                            resize_keyboard=True, one_time_keyboard=True)
    await m.answer("Siz bilan bog'lanish uchun telefon raqamingiz?", reply_markup=k)


@dp.message(Order.colors, F.text)
async def got_colors(m: Message, state: FSMContext):
    await state.update_data(colors=m.text.strip())
    await ask_phone(m, state)


@dp.callback_query(Order.colors, F.data == "skip_colors")
async def skip_colors(c: CallbackQuery, state: FSMContext):
    await state.update_data(colors="Tanlanmagan")
    await ask_phone(c.message, state)
    await c.answer()


async def finish(m: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    await state.set_state(Order.confirm)
    d = await state.get_data()
    await m.answer("Buyurtmangizni tekshiring:", reply_markup=ReplyKeyboardRemove())
    await m.answer(order_text(d), reply_markup=kb([("✅ Yuborish", "send"), ("❌ Bekor qilish", "cancel")], (2,)))


@dp.message(Order.phone, F.contact)
async def phone_contact(m: Message, state: FSMContext):
    await finish(m, state, m.contact.phone_number)


@dp.message(Order.phone, F.text)
async def phone_text(m: Message, state: FSMContext):
    await finish(m, state, m.text.strip())


@dp.callback_query(Order.confirm, F.data == "send")
async def send_order(c: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    u = c.from_user
    oid = db_run("INSERT INTO orders(user_id,plan,brand,bio,links,logo,logo_kind,colors,phone,created) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (u.id, d["plan"], d["brand"], d["bio"], d["links"], d.get("logo"), d.get("logo_kind"),
                  d["colors"], d["phone"], now()))
    if d.get("logo"):
        send = bot.send_photo if d.get("logo_kind") == "photo" else bot.send_document
        await send(ADMIN_ID, d["logo"])
    await bot.send_message(ADMIN_ID, f"🆕 <b>Yangi buyurtma #{oid}</b>\nMijoz: {who(u)}\n\n{order_text(d)}",
                           reply_markup=admin_order_kb(oid, u.id))
    await state.clear()
    await c.message.answer(f"Rahmat! 💗 Buyurtmangiz #{oid} qabul qilindi, tez orada bog'lanamiz.\n"
                           "Holatini «📦 Buyurtmalarim» bo'limida ko'rishingiz mumkin.", reply_markup=menu_kb())
    await c.answer()


# Hech qaysi holatda bo'lmagan boshqa xabarlar -> menyu
@dp.message(StateFilter(None))
async def fallback(m: Message):
    await m.answer("Quyidagilardan birini tanlang:", reply_markup=menu_kb())
# ---------------- Webhook (Render uchun) ----------------
import os
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://dila-shoping-bot-1.onrender.com" + WEBHOOK_PATH

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    logging.info("Webhook o'rnatildi: %s", WEBHOOK_URL)


async def health(request):
    return web.Response(text="ok")


def main():
    logging.basicConfig(level=logging.INFO)
    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    main()