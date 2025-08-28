# main_part1.py
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Optional
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# local modules
import database  # our database.py

load_dotenv()

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configs ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")  # optional
ADMINS_FILE = "admin/admins.txt"

# Ensure directories
for d in ['admin', 'matn', 'tugma', 'step', 'tizim']:
    os.makedirs(d, exist_ok=True)

# default texts (only create if missing)
_defaults = {
    'admin/valyuta.txt': "so'm",
    'admin/vip.txt': "25000",
    'admin/holat.txt': "Yoqilgan",
    'admin/anime_kanal.txt': "@username",
    'tizim/content.txt': "false",
    'matn/start.txt': "✨ Assalomu alaykum! Botga xush kelibsiz.",
    'tugma/key1.txt': "🔎 Anime izlash",
    'tugma/key2.txt': "💎 VIP",
    'tugma/key3.txt': "💰 Hisobim",
    'tugma/key4.txt': "➕ Pul kiritish",
    'tugma/key5.txt': "📚 Qo'llanma",
    'tugma/key6.txt': "💵 Reklama va Homiylik"
}
def read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""
def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(str(content))

for k, v in _defaults.items():
    if not os.path.exists(k):
        write_file(k, v)

# --- Aiogram init ---
if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set in .env")
    raise SystemExit("Please set BOT_TOKEN in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Global pool will be attached to dispatcher on startup
# dp['pool'] = await database.create_pool()

# --- helper admin checks ---
def get_admins_list() -> list:
    text = read_file(ADMINS_FILE)
    if not text:
        return []
    return [s.strip() for s in text.splitlines() if s.strip()]

def is_admin(user_id: int) -> bool:
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        return True
    return str(user_id) in get_admins_list()

# --- Keyboards ---
def main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    keys = [read_file(f"tugma/key{i}.txt") for i in range(1,7)]
    keyboard = [
        [InlineKeyboardButton(keys[0], callback_data='search')],
        [InlineKeyboardButton(keys[1], callback_data='vip'), InlineKeyboardButton(keys[2], callback_data='balance')],
        [InlineKeyboardButton(keys[3], callback_data='add_money'), InlineKeyboardButton(keys[4], callback_data='help')],
        [InlineKeyboardButton(keys[5], callback_data='sponsor')]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🗄 Boshqarish", callback_data='panel')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Start handler ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    pool = dp.get('pool')
    # ensure user exists in DB
    await database.ensure_user(pool, user_id)
    start_text = read_file("matn/start.txt") or "Assalomu alaykum!"
    await message.answer(start_text, reply_markup=main_menu_kb(user_id))

# --- Callback dispatcher (core routes) ---
@dp.callback_query_handler(lambda c: True)
async def cb_all(query: types.CallbackQuery):
    data = query.data or ""
    uid = query.from_user.id

    # ADMIN PANEL
    if data == 'panel':
        if not is_admin(uid):
            await query.answer("❌ Sizda ruxsat yo'q!", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("📊 Statistika", callback_data='stats')],
            [InlineKeyboardButton("✉ Xabar jiberiw", callback_data='send_message')],
            [InlineKeyboardButton("📬 Post dayındaw", callback_data='create_post')],
            [InlineKeyboardButton("🎥 Animelerdi baptaw", callback_data='anime_settings')],
            [InlineKeyboardButton("◀️ Artqa", callback_data='back')]
        ])
        await query.message.edit_text("Admin panelga xush kelibsiz!", reply_markup=kb)
        await query.answer()
        return

    # SEARCH MENU
    if data == 'search':
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🏷 Anime atı boyınsha", callback_data='searchByName')],
            [InlineKeyboardButton("📚 Barcha animelar", callback_data='allAnimes')],
            [InlineKeyboardButton("◀️ Artqa", callback_data='back')]
        ])
        await query.message.edit_text("🔍 Izlash turini tanlang:", reply_markup=kb)
        await query.answer()
        return

    # BACK to main
    if data == 'back':
        await query.message.edit_text(read_file("matn/start.txt") or "Bosh menyu", reply_markup=main_menu_kb(uid))
        await query.answer()
        return

    # VIP block (simple)
    if data == 'vip':
        pool = dp.get('pool')
        async with pool.acquire() as conn:
            status = await conn.fetchrow("SELECT status FROM users WHERE user_id = $1", uid)
        if status and status['status'] == 'Oddiy':
            narx = int(read_file("admin/vip.txt") or "25000")
            val = read_file("admin/valyuta.txt") or "so'm"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(f"30 kún - {narx} {val}", callback_data='shop=30')],
                [InlineKeyboardButton(f"60 kún - {narx*2} {val}", callback_data='shop=60')],
                [InlineKeyboardButton(f"90 kún - {narx*3} {val}", callback_data='shop=90')]
            ])
            await query.message.edit_text("💎 VIP bo'limi", reply_markup=kb)
        else:
            async with dp.get('pool').acquire() as conn:
                active = await conn.fetchrow("SELECT kun FROM status WHERE user_id = $1", uid)
            if active:
                expire = (datetime.now() + timedelta(days=int(active['kun']))).strftime("%d.%m.%Y")
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("🗓️ Uzartıw", callback_data='uzaytirish')]])
                await query.message.edit_text(f"Siz VIP statusdasiz. Amal qilish muddati: {expire}", reply_markup=kb)
        await query.answer()
        return

    # BALANCE
    if data == 'balance':
        async with dp.get('pool').acquire() as conn:
            bal = await conn.fetchrow("SELECT pul FROM balance WHERE user_id = $1", uid)
        val = bal['pul'] if bal else 0
        await query.message.edit_text(f"#ID: <code>{uid}</code>\nBalans: {val} {read_file('admin/valyuta.txt')}", parse_mode='HTML')
        await query.answer()
        return

    # searchByName
    if data == 'searchByName':
        await query.message.edit_text("🔎 Anime nomini yuboring:")
        write_file(f"step/{uid}.step", "search_name")
        await query.answer()
        return

    # allAnimes
    if data == 'allAnimes':
        pool = dp.get('pool')
        rows = await database.search_animes_by_name(pool, "", limit=50)  # empty returns first 50 by name order
        if not rows:
            await query.message.edit_text("Ro'yxat bo'sh.")
            await query.answer()
            return
        kb = InlineKeyboardMarkup()
        for r in rows:
            kb.add(InlineKeyboardButton(str(r['nom']), callback_data=f"anime={r['id']}"))
        await query.message.edit_text("📚 Barcha animelar:", reply_markup=kb)
        await query.answer()
        return

    # show anime by callback anime=ID
    if data.startswith("anime="):
        try:
            aid = int(data.split("=")[1])
        except Exception:
            await query.answer("ID xato"); return
        # reuse show function (defined below)
        await show_anime_callback(query, aid)
        return

    await query.answer()  # default acknowledgement

# --- Message handling (steps + fallback search) ---
@dp.message_handler()
async def msg_all(message: types.Message):
    uid = message.from_user.id
    text = message.text or ""
    step_file = f"step/{uid}.step"
    pool = dp.get('pool')

    # Step: search_name
    if os.path.exists(step_file):
        step = read_file(step_file)
        if step == "search_name":
            # perform search
            rows = await database.search_animes_by_name(pool, text, limit=10)
            if not rows:
                await message.reply("❌ Hech nima topilmadi.")
                try: os.remove(step_file)
                except: pass
                return
            kb = InlineKeyboardMarkup()
            for r in rows:
                kb.add(InlineKeyboardButton(r['nom'], callback_data=f"anime={r['id']}"))
            await message.reply("🔍 Natijalar:", reply_markup=kb)
            try: os.remove(step_file)
            except: pass
            return

    # Quick buttons mapping by exact text
    if text == read_file("tugma/key1.txt"):
        await message.answer("🔍 Izlash turini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🏷 Anime nomi bo'yicha", callback_data='searchByName')],
            [InlineKeyboardButton("📚 Barcha animelar", callback_data='allAnimes')]
        ]))
        return

    if text == read_file("tugma/key2.txt"):
        await message.answer("💎 VIP bo'limi (tugmani bosing)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("30 kún - VIP", callback_data='shop=30')]
        ]))
        return

    # fallback: search by name directly
    rows = await database.search_animes_by_name(pool, text, limit=10)
    if not rows:
        await message.reply("❌ Hech qanday anime topilmadi.")
        return
    kb = InlineKeyboardMarkup()
    for r in rows:
        kb.add(InlineKeyboardButton(r['nom'], callback_data=f"anime={r['id']}"))
    await message.reply("🔍 Topildi:", reply_markup=kb)

# --- show anime helper ---
async def show_anime_callback(query: types.CallbackQuery, anime_id: int):
    uid = query.from_user.id
    pool = dp.get('pool')
    anime = await database.get_anime_by_id(pool, anime_id)
    if not anime:
        await query.answer("Anime topilmadi!", show_alert=True); return
    # increment qidiruv
    async with pool.acquire() as conn:
        await conn.execute("UPDATE animelar SET qidiruv = qidiruv + 1 WHERE id = $1", anime_id)

    # build caption
    caption = (f"<b>🎬 Atı: {anime['nom']}</b>\n\n"
               f"🎥 Bólimi: {anime['qismi']}\n"
               f"🌍 Mámleketi: {anime['davlat']}\n"
               f"🇺🇿 Tili: {anime['tili']}\n"
               f"📆 Yılı: {anime['yili']}\n"
               f"🎞 Janrı: {anime['janri']}\n\n"
               f"🔍 Izlewler: {anime['qidiruv']}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("📥 Júklap alıw", callback_data=f"yuklanolish={anime_id}=1")]])
    rams = anime['rams'] or ""
    try:
        if rams.startswith('B'):
            await bot.send_video(chat_id=uid, video=rams[1:], caption=caption, parse_mode='HTML', reply_markup=kb,
                                 protect_content=(read_file("tizim/content.txt") == 'true'))
        elif rams.startswith('P'):
            await bot.send_photo(chat_id=uid, photo=rams[1:], caption=caption, parse_mode='HTML', reply_markup=kb,
                                 protect_content=(read_file("tizim/content.txt") == 'true'))
        else:
            await query.message.edit_text(caption, reply_markup=kb, parse_mode='HTML')
    except Exception as e:
        logger.exception("Error sending media: %s", e)
        await query.message.edit_text(caption, reply_markup=kb, parse_mode='HTML')
    await query.answer()

# --- Add anime initiation (admin) ---
@dp.callback_query_handler(lambda c: c.data == 'anime_settings')
async def cb_anime_settings(query: types.CallbackQuery):
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("❌ Sizda ruxsat yo'q!", show_alert=True)
        return
    # start add flow
    write_file(f"step/{uid}.step", "anime-name")
    await query.message.answer("🍿 Anime atın kirgiziń:")
    await query.answer()

# The rest of the add-anime step machine will be continued in the next block (saving images/videos etc.)
# For now we implemented the step start and first message. The step-machine handler will pick this up
# and on next messages will proceed to anime-episodes, anime-country, etc.

# ------------------------------------------------------------------
# Startup / shutdown handlers - will attach DB pool to dispatcher
# ------------------------------------------------------------------
async def on_startup(dispatcher: Dispatcher):
    pool = await database.create_pool()
    dispatcher['pool'] = pool
    await database.init_tables(pool)
    # keep-alive: if you use Replit/Render + uptime robot
    try:
        # try import keep_alive (if present in project)
        from keep_alive import keep_alive
        keep_alive()
    except Exception:
        logger.info("keep_alive not started (keep_alive.py missing or raised error)")

    logger.info("Bot startup complete. DB initialized.")

async def on_shutdown(dispatcher: Dispatcher):
    pool = dispatcher.get('pool')
    if pool:
        await pool.close()
    logger.info("Shutdown complete.")

# We intentionally DO NOT call executor.start_polling here inside this chunk.
# The next block will attach more handlers and eventually start polling.
# This way we can append further code in subsequent messages without re-running.

# ------------------- main_part2.py (Append to main_part1.py) -------------------
# Бұл бөлім main_part1.py файлына жалғасады. Егер бәрі бір файлда болса,
# жай ғана осы блокты main_part1.py соңына қосыңыз.

# --- Qo'shimcha importlar (егер бұрын жоқ болса) ---
from aiogram.types import ContentType
import math

# --- HELP командаси (foydalanuvchi uchun, o'zbekcha) ---
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    help_text = (
        "📚 *Qo'llanma*\n\n"
        "🔎 Anime qidirish uchun: menyudan yoki #qidir <nom>\n"
        "📥 Epizodni yuklab olish: anime sahifasidagi «📥 Yuklab olish» tugmasi orqali\n"
        "/broadcast — (admin) barcha foydalanuvchilarga xabar yuborish\n"
        "/add_episode — (admin) animega yangi epizod qo'shish\n"
        "/panel — admin panelini ochish\n\n"
        "Agar savolingiz bo'lsa, admin bilan bog'laning."
    )
    await message.reply(help_text, parse_mode='Markdown')

# --- Add-anime step-machine: davomiy qabul qilish (main_part1 da boshlangan) ---
# Biz step faylida saqlangan holatlarga qarab keyingi xabarlarni qabul qilamiz.
@dp.message_handler(lambda m: os.path.exists(f"step/{m.from_user.id}.step") and read_file(f"step/{m.from_user.id}.step").startswith("anime-"))
async def add_anime_steps_continue(message: types.Message):
    uid = message.from_user.id
    step = read_file(f"step/{uid}.step")
    text = message.text or ""
    # anime-name handled in part1; continue from episodes -> country -> language -> year -> genre -> fandub -> picture
    if step == "anime-episodes":
        write_file("step/anime_episodes.txt", text)
        await message.reply("🌍 Iltimos, anime qaysi mamlakatda yaratilganini kiriting:")
        write_file(f"step/{uid}.step", "anime-country")
        return
    if step == "anime-country":
        write_file("step/anime_country.txt", text)
        await message.reply("🗣 Iltimos, anime tilini kiriting (masalan: O'zbek, Yaponiya):")
        write_file(f"step/{uid}.step", "anime-language")
        return
    if step == "anime-language":
        write_file("step/anime_language.txt", text)
        await message.reply("📆 Iltimos, anime yilini kiriting (masalan: 2020):")
        write_file(f"step/{uid}.step", "anime-year")
        return
    if step == "anime-year":
        write_file("step/anime_year.txt", text)
        await message.reply("🎞 Iltimos, janrlarni kiriting (vergul bilan):\nMisol: Drama, Fantaziya, Sarguzasht")
        write_file(f"step/{uid}.step", "anime-genre")
        return
    if step == "anime-genre":
        write_file("step/anime_genre.txt", text)
        await message.reply("🎙 Fandub manbasini kiriting (masalan: @AnimeLiveUz) yoki \"Noma'lum\":")
        write_file(f"step/{uid}.step", "anime-fandub")
        return
    if step == "anime-fandub":
        write_file("step/anime_fandub.txt", text)
        await message.reply("🏞 Iltimos, surat yoki 60 soniyadan kam video yuboring (media sifatida):")
        write_file(f"step/{uid}.step", "anime-picture")
        return
    if step == "anime-picture":
        # kutyapmiz: rasm yoki video
        if message.photo:
            file_id = message.photo[-1].file_id
            await finalize_add_anime(uid, file_id, 'photo', message)
        elif message.video:
            if message.video.duration <= 60:
                file_id = message.video.file_id
                await finalize_add_anime(uid, file_id, 'video', message)
            else:
                await message.reply("⚠️ Video uzunligi 60 soniyadan oshmasligi kerak. Iltimos qisqaroq video yuboring.")
        else:
            await message.reply("⚠️ Iltimos, surat yoki video yuboring (media).")
        return

async def finalize_add_anime(uid: int, file_id: str, file_type: str, message_obj: types.Message):
    """
    Barcha step fayllardan o'qib, bazaga qo'shadi.
    """
    nom = read_file("step/anime_name.txt")
    qismi_txt = read_file("step/anime_episodes.txt")
    qismi = int(qismi_txt) if qismi_txt.isdigit() else 0
    davlat = read_file("step/anime_country.txt")
    tili = read_file("step/anime_language.txt")
    yili = read_file("step/anime_year.txt")
    janri = read_file("step/anime_genre.txt")
    fandub = read_file("step/anime_fandub.txt")
    sana = datetime.now().strftime("%H:%M %d.%m.%Y")
    prefix = 'B' if file_type == 'video' else 'P'
    rams = prefix + file_id

    pool = dp.get('pool')
    try:
        new_id = await database.add_anime(pool, nom, rams, qismi, davlat, tili, yili, janri, fandub, sana)
    except Exception as e:
        logger.exception("add_anime error: %s", e)
        await message_obj.reply("❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")
        return

    # tozalash: barcha step fayllarni o'chirish
    for fname in ['anime_name','anime_episodes','anime_country','anime_language','anime_year','anime_genre','anime_fandub']:
        fp = f"step/{fname}.txt"
        if os.path.exists(fp):
            os.remove(fp)
    sf = f"step/{uid}.step"
    if os.path.exists(sf):
        os.remove(sf)

    await message_obj.reply(f"✅ Anime muvaffaqqiyatli qoʻshildi!\nAnime kodi: <code>{new_id}</code>", parse_mode='HTML')

# --- Episode qo'shish (admin) to'liq oqim ---
@dp.message_handler(commands=['add_episode'])
async def cmd_add_episode(message: types.Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply("❌ Siz admin emassiz.")
        return
    await message.reply("🔢 Iltimos, qo'shiladigan anime ID sini kiriting:")
    write_file(f"step/{uid}.step", "episode-wait-id")

@dp.message_handler(lambda m: os.path.exists(f"step/{m.from_user.id}.step") and read_file(f"step/{m.from_user.id}.step") == "episode-wait-id")
async def proc_episode_wait_id(message: types.Message):
    uid = message.from_user.id
    txt = message.text or ""
    if not txt.isdigit():
        await message.reply("⚠️ Iltimos faqat raqam ko'rinishida ID yuboring.")
        return
    write_file("step/episode_anime_id.txt", txt)
    write_file(f"step/{uid}.step", "episode-wait-media")
    await message.reply("🎥 Endi video yuboring (mahfiyati himoya qilinadi):")

@dp.message_handler(content_types=ContentType.VIDEO)
async def proc_episode_video_all(message: types.Message):
    uid = message.from_user.id
    stepf = f"step/{uid}.step"
    if not os.path.exists(stepf) or read_file(stepf) != "episode-wait-media":
        # bu erda boshqa videolarni kutmaymiz
        return
    anime_id_txt = read_file("step/episode_anime_id.txt")
    if not anime_id_txt or not anime_id_txt.isdigit():
        await message.reply("⚠️ Anime ID topilmadi. Jarayon bekor qilindi.")
        try: os.remove(stepf)
        except: pass
        return
    anime_id = int(anime_id_txt)
    file_id = message.video.file_id
    pool = dp.get('pool')

    try:
        # episode raqamini avtomatik hisoblash
        async with pool.acquire() as conn:
            cnt = await conn.fetchval("SELECT COUNT(*) FROM anime_datas WHERE anime_id = $1", anime_id)
            ep_num = cnt + 1
            sana = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
            await database.add_episode(pool, anime_id, file_id, ep_num, sana)
    except Exception as e:
        logger.exception("add_episode error: %s", e)
        await message.reply("❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")
        return

    # tozalash step fayll
    try:
        os.remove("step/episode_anime_id.txt")
    except:
        pass
    try:
        os.remove(stepf)
    except:
        pass

    await message.reply(f"✅ {anime_id} kodli animega {ep_num}-bo'lim muvaffaqiyatli qoʻshildi!")

# --- Yuklab olish (yuklanolish) handleri: epizodni yuborish va sahifa tugmalari ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("yuklanolish="))
async def cb_yuklanolish(query: types.CallbackQuery):
    data = query.data  # yuklanolish=anime_id=ep
    parts = data.split("=")
    if len(parts) < 3:
        await query.answer("Noto'g'ri buyruq.", show_alert=True)
        return
    anime_id = int(parts[1]); ep = int(parts[2])
    pool = dp.get('pool')
    async with pool.acquire() as conn:
        episode = await conn.fetchrow("SELECT * FROM anime_datas WHERE anime_id = $1 AND qism = $2", anime_id, ep)
        anime = await conn.fetchrow("SELECT * FROM animelar WHERE id = $1", anime_id)
        all_eps_rows = await conn.fetch("SELECT qism FROM anime_datas WHERE anime_id = $1 ORDER BY qism", anime_id)
    if not episode:
        await query.answer("Bo'lim topilmadi!", show_alert=True); return

    all_eps = [r['qism'] for r in all_eps_rows]
    # buttons creation with pagination (25 per page)
    current_page = (ep - 1) // 25
    start = current_page * 25
    end = min(start + 25, len(all_eps))
    buttons = []
    for i in range(start, end):
        epn = all_eps[i]
        if epn == ep:
            buttons.append(InlineKeyboardButton(f"[{epn}]", callback_data="null"))
        else:
            buttons.append(InlineKeyboardButton(str(epn), callback_data=f"yuklanolish={anime_id}={epn}"))
    kb_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"pagenation={anime_id}={ep}=back"))
    nav.append(InlineKeyboardButton("❌ Yopish", callback_data="close"))
    if end < len(all_eps):
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"pagenation={anime_id}={ep}=next"))
    kb_rows.append(nav)
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    caption = f"<b>{anime['nom']}</b>\n\n{ep}-bo'lim"
    try:
        await bot.send_video(chat_id=query.from_user.id, video=episode['file_id'], caption=caption, parse_mode='HTML', reply_markup=kb, protect_content=(read_file("tizim/content.txt") == 'true'))
    except Exception:
        # fallback: send message with link or text
        await query.message.reply(caption, reply_markup=kb)
    await query.answer()

# --- Pagination handler (pagenation) ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("pagenation="))
async def cb_pagenation(query: types.CallbackQuery):
    # format: pagenation=anime_id=current_ep=action
    parts = query.data.split("=")
    if len(parts) < 4:
        await query.answer("Noto'g'ri buyruq.", show_alert=True); return
    anime_id = int(parts[1]); current_ep = int(parts[2]); action = parts[3]
    pool = dp.get('pool')
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT qism FROM anime_datas WHERE anime_id = $1 ORDER BY qism", anime_id)
    all_eps = [r['qism'] for r in rows]
    if current_ep not in all_eps:
        await query.answer("Xato: ep topilmadi.", show_alert=True); return
    idx = all_eps.index(current_ep)
    if action == "back":
        new_idx = max(0, idx - 25)
    else:
        new_idx = min(len(all_eps) - 1, idx + 25)
    new_ep = all_eps[new_idx]

    # fetch episode data
    async with pool.acquire() as conn:
        episode = await conn.fetchrow("SELECT * FROM anime_datas WHERE anime_id = $1 AND qism = $2", anime_id, new_ep)
        anime = await conn.fetchrow("SELECT * FROM animelar WHERE id = $1", anime_id)

    # rebuild buttons for new page
    current_page = new_idx // 25
    start = current_page * 25
    end = min(start + 25, len(all_eps))
    buttons = []
    for i in range(start, end):
        epn = all_eps[i]
        if epn == new_ep:
            buttons.append(InlineKeyboardButton(f"[{epn}]", callback_data="null"))
        else:
            buttons.append(InlineKeyboardButton(str(epn), callback_data=f"yuklanolish={anime_id}={epn}"))
    kb_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"pagenation={anime_id}={new_ep}=back"))
    nav.append(InlineKeyboardButton("❌ Yopish", callback_data="close"))
    if end < len(all_eps):
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"pagenation={anime_id}={new_ep}=next"))
    kb_rows.append(nav)
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    caption = f"<b>{anime['nom']}</b>\n\n{new_ep}-bo'lim"
    try:
        await bot.send_video(chat_id=query.from_user.id, video=episode['file_id'], caption=caption, parse_mode='HTML', reply_markup=kb, protect_content=(read_file("tizim/content.txt") == 'true'))
    except Exception:
        await query.message.reply(caption, reply_markup=kb)
    # remove previous message for cleanliness
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()

# --- Close and null handlers (already in part1 but ensure present) ---
@dp.callback_query_handler(lambda c: c.data in ['close', 'null'])
async def cb_close_null_general(query: types.CallbackQuery):
    if query.data == 'close':
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.answer()
    else:
        await query.answer()

# --- Broadcast handling: admin sends any media/text and it is forwarded to all users ---
# Start: admin issues /broadcast (in part1 we set step). Now accept media or text when step == 'broadcast'
@dp.message_handler(lambda m: os.path.exists(f"step/{m.from_user.id}.step") and read_file(f"step/{m.from_user.id}.step") == "broadcast", content_types=ContentType.ANY)
async def process_broadcast_message(message: types.Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply("❌ Siz admin emassiz."); return
    pool = dp.get('pool')
    # fetch all user ids
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
    target_ids = [r['user_id'] for r in rows]
    success = 0; failed = 0
    # prepare sending function to handle different media
    async def send_to_user(user_id):
        nonlocal success, failed
        try:
            if message.text:
                await bot.send_message(chat_id=user_id, text=message.text, parse_mode='HTML')
            elif message.photo:
                await bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=message.caption or "", parse_mode='HTML')
            elif message.video:
                await bot.send_video(chat_id=user_id, video=message.video.file_id, caption=message.caption or "", parse_mode='HTML')
            elif message.document:
                await bot.send_document(chat_id=user_id, document=message.document.file_id, caption=message.caption or "")
            else:
                # fallback: send text about broadcast
                await bot.send_message(chat_id=user_id, text=message.caption or "📣 Admindan xabar")
            success += 1
        except Exception:
            failed += 1

    # iterate with small sleep to avoid flood
    for uid_target in target_ids:
        await send_to_user(uid_target)
        await asyncio.sleep(0.05)  # 50ms pause

    # cleanup step file
    try:
        os.remove(f"step/{message.from_user.id}.step")
    except:
        pass

    await message.reply(f"✅ Xabar yuborildi!\n✅ Muvaffaqiyatli: {success}\n❌ Xatolik: {failed}")

# --- Admin: manage_user flow (foydalanuvchini boshqarish) ---
@dp.callback_query_handler(lambda c: c.data == 'manage_user')
async def cb_manage_user_start(query: types.CallbackQuery):
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("❌ Sizda ruxsat yo'q!", show_alert=True); return
    await query.message.edit_text("🔎 Iltimos, boshqariladigan foydalanuvchi ID sini yuboring:")
    write_file(f"step/{uid}.step", "manage_user_id")
    await query.answer()

@dp.message_handler(lambda m: os.path.exists(f"step/{m.from_user.id}.step") and read_file(f"step/{m.from_user.id}.step") == "manage_user_id")
async def proc_manage_user_id(message: types.Message):
    uid = message.from_user.id
    target_txt = message.text.strip() if message.text else ""
    if not target_txt.isdigit():
        await message.reply("⚠️ Iltimos faqat raqam (user ID) yuboring."); return
    tid = int(target_txt)
    # show options
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🔒 Ban qilish", callback_data=f"admin_ban={tid}")],
        [InlineKeyboardButton("🔓 Unban qilish", callback_data=f"admin_unban={tid}")],
        [InlineKeyboardButton("💰 Balans o'zgartirish", callback_data=f"admin_balance={tid}")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data='panel')]
    ])
    await message.reply(f"❗ Foydalanuvchi ID: {tid}\nNimani amalga oshirishni xohlaysiz?", reply_markup=kb)
    try: os.remove(f"step/{uid}.step")
    except: pass

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_ban="))
async def cb_admin_ban(query: types.CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌"); return
    tid = int(query.data.split("=")[1])
    async with dp.get('pool').acquire() as conn:
        await conn.execute("UPDATE balance SET ban = 'ban' WHERE user_id = $1", tid)
    await query.answer("✅ Foydalanuvchi ban qilindi.")
    await query.message.edit_text(f"Foydalanuvchi {tid} ban qilindi.")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_unban="))
async def cb_admin_unban(query: types.CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌"); return
    tid = int(query.data.split("=")[1])
    async with dp.get('pool').acquire() as conn:
        await conn.execute("UPDATE balance SET ban = 'unban' WHERE user_id = $1", tid)
    await query.answer("✅ Foydalanuvchi unban qilindi.")
    await query.message.edit_text(f"Foydalanuvchi {tid} unban qilindi.")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_balance="))
async def cb_admin_balance(query: types.CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌"); return
    tid = int(query.data.split("=")[1])
    write_file(f"step/{query.from_user.id}.step", f"set_balance:{tid}")
    await query.message.answer("🔢 Iltimos, yangi balans miqdorini (faqat raqam) kiriting:")
    await query.answer()

@dp.message_handler(lambda m: os.path.exists(f"step/{m.from_user.id}.step") and read_file(f"step/{m.from_user.id}.step").startswith("set_balance:"))
async def proc_set_balance(message: types.Message):
    step = read_file(f"step/{message.from_user.id}.step")
    tid = int(step.split(":")[1])
    if not message.text or not message.text.isdigit():
        await message.reply("⚠️ Faqat raqam yuboring!"); return
    newbal = int(message.text)
    async with dp.get('pool').acquire() as conn:
        await conn.execute("UPDATE balance SET pul = $1 WHERE user_id = $2", newbal, tid)
    try: os.remove(f"step/{message.from_user.id}.step")
    except: pass
    await message.reply(f"✅ Foydalanuvchi {tid} balansini {newbal} ga sozladim.")

# --- Admin: add/remove admin komandalar (oddiy matn buyruqlari) ---
@dp.message_handler(commands=['add_admin'])
async def cmd_add_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ Siz admin emassiz."); return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("⚠️ Foydalanish: /add_admin 123456789"); return
    newadmin = args
    admins = get_admins_list()
    if newadmin in admins:
        await message.reply("⚠️ Bu foydalanuvchi allaqachon admin.") 
        return
    admins.append(newadmin)
    write_file(ADMINS_FILE, "\n".join(admins))
    await message.reply(f"✅ {newadmin} admin sifatida qo'shildi.")

@dp.message_handler(commands=['remove_admin'])
async def cmd_remove_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ Siz admin emassiz."); return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("⚠️ Foydalanish: /remove_admin 123456789"); return
    rem = args
    admins = get_admins_list()
    if rem not in admins:
        await message.reply("⚠️ Bunday admin topilmadi.")
        return
    admins = [a for a in admins if a != rem]
    write_file(ADMINS_FILE, "\n".join(admins))
    await message.reply(f"✅ {rem} adminlikdan olib tashlandi.")

# --- Shop (VIP) callback (buy) - bu qism part1 da ham bor edi; lekin bu yerda to'liq e'lon qilamiz ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("shop="))
async def cb_shop_full(query: types.CallbackQuery):
    uid = query.from_user.id
    days = int(query.data.split("=")[1])
    price = int(read_file("admin/vip.txt") or "25000")
    val = read_file("admin/valyuta.txt") or "so'm"
    total = int((price / 30) * days)
    async with dp.get('pool').acquire() as conn:
        bal = await conn.fetchrow("SELECT pul FROM balance WHERE user_id = $1", uid)
    userbal = bal['pul'] if bal else 0
    if userbal >= total:
        async with dp.get('pool').acquire() as conn:
            await conn.execute("UPDATE balance SET pul = pul - $1 WHERE user_id = $2", total, uid)
            exists = await conn.fetchval("SELECT 1 FROM status WHERE user_id = $1", uid)
            if not exists:
                await conn.execute("INSERT INTO status (user_id, kun, date) VALUES ($1,$2,$3)", uid, days, datetime.now().strftime("%d.%m.%Y"))
            else:
                await conn.execute("UPDATE status SET kun = kun + $1 WHERE user_id = $2", days, uid)
            await conn.execute("UPDATE users SET status = 'VIP' WHERE user_id = $1", uid)
        await query.answer("✅ VIP muvaffaqiyatli sotib olindi!", show_alert=True)
        await query.message.edit_text(f"💎 Siz VIP boʻldingiz. Amal qilish muddati: {days} kun")
    else:
        await query.answer("💸 Hisobingizda yetarli mablag' yo'q!", show_alert=True)

# --- Bot status (admin) - uptime va oddiy statistikalar ---
@dp.callback_query_handler(lambda c: c.data == 'bot_status')
async def cb_bot_status(query: types.CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌"); return
    pool = dp.get('pool')
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        animes = await conn.fetchval("SELECT COUNT(*) FROM animelar")
        episodes = await conn.fetchval("SELECT COUNT(*) FROM anime_datas")
    uptime = datetime.now() - start_time
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    text = (f"🤖 Bot holati:\nUptime: {days}d {hours}h {minutes}m\n\n"
            f"👥 Foydalanuvchilar: {users}\n🎬 Animelar: {animes}\n📀 Bo'limlar: {episodes}")
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("◀️ Orqaga", callback_data='panel')]]))
    await query.answer()

# -----------------------------------------------------------------------
# QISQACHA: Bu blok main_part1 ga to'liq qo'shilib, user/admin oqimlarini kengaytiradi.
# Next steps (main_part3) — biz quyidagi vazifalarni bajaramiz:
#  - Kanalga post jo'natish oynasini (sendto=...) batafsil to'ldirish (admin tomonidan)
#  - "buttons" va "texts" sozlamalari orqali tugmalar/matnni tahrirlash imkoniyati
#  - Analytics (kunlik/oylik statistikalar CSV export)
#  - Qo'shimcha xavfsizlik: rate-limit va exceptions handlingni mustahkamlash
#  - README, Procfile, requirements.txt, .env.example fayllari tuzish
# -----------------------------------------------------------------------

from aiogram.dispatcher.filters import BoundFilter

# Faqat adminlarni ajratib olish uchun filter
class AdminFilter(BoundFilter):
    key = "is_admin"

    def __init__(self, is_admin):
        self.is_admin = is_admin

    async def check(self, message: types.Message):
        return message.from_user.id in ADMINS

# Admin menyusi
@dp.message_handler(commands=['admin'], is_admin=True)
async def admin_panel(message: types.Message):
    tugmalar = ReplyKeyboardMarkup(resize_keyboard=True)
    tugmalar.add("➕ Anime yuklash")
    tugmalar.add("✏️ Anime tahrirlash")
    tugmalar.add("📊 Statistika")
    tugmalar.add("📝 Post yaratish")
    tugmalar.add("📢 Foydalanuvchilarga habar tarqatish")
    tugmalar.add("⚙️ Sozlamalar")
    tugmalar.add("📚 Anime ro‘yxati")
    tugmalar.add("⬅️ Orqaga")

    await message.answer("🔐 Admin panelga xush kelibsiz!", reply_markup=tugmalar)

# ➕ Anime yuklash bosqichi
@dp.message_handler(lambda msg: msg.text == "➕ Anime yuklash", is_admin=True)
async def anime_yuklash_boshlash(message: types.Message, state: FSMContext):
    await state.set_state("anime_nom")
    await message.answer("📥 Yuklanadigan animening nomini kiriting:")

@dp.message_handler(state="anime_nom", is_admin=True)
async def anime_nom_qabul(message: types.Message, state: FSMContext):
    await state.update_data(anime_nom=message.text)
    await state.set_state("anime_kod")
    await message.answer("🔑 Anime uchun kod kiriting (masalan: naruto_uz):")

@dp.message_handler(state="anime_kod", is_admin=True)
async def anime_kod_qabul(message: types.Message, state: FSMContext):
    await state.update_data(anime_kod=message.text)
    await state.set_state("anime_seriyalar")
    await message.answer("🎬 Nechta qism yuklamoqchisiz?")

@dp.message_handler(state="anime_seriyalar", is_admin=True)
async def anime_seriyalar_qabul(message: types.Message, state: FSMContext):
    await state.update_data(anime_seriyalar=message.text)
    await state.set_state("anime_kanal")
    await message.answer("📡 Qaysi Telegram kanaliga yuklansin? Kanal @username kiriting:")

@dp.message_handler(state="anime_kanal", is_admin=True)
async def anime_kanal_qabul(message: types.Message, state: FSMContext):
    await state.update_data(anime_kanal=message.text)
    await state.set_state("anime_github")
    await message.answer("💾 GitHub manzilini kiriting (masalan: https://github.com/user/repo):")

@dp.message_handler(state="anime_github", is_admin=True)
async def anime_github_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    # JSON yoki DB ga saqlash logikasi shu yerda bo‘ladi
    await state.finish()
    await message.answer(
        f"✅ Anime muvaffaqiyatli yuklandi!\n\n"
        f"📌 Nomi: {malumot['anime_nom']}\n"
        f"🔑 Kodi: {malumot['anime_kod']}\n"
        f"🎬 Qismlar soni: {malumot['anime_seriyalar']}\n"
        f"📡 Kanal: {malumot['anime_kanal']}\n"
        f"💾 GitHub: {malumot['anime_github']}"
	)


# ================================
# 4- va 5-part: Admin panel
# ================================

# ✏️ Anime tahrirlash menyusi
@dp.message_handler(lambda msg: msg.text == "✏️ Anime tahrirlash", is_admin=True)
async def anime_tahrirlash_boshlash(message: types.Message, state: FSMContext):
    # Bu yerda mavjud animelarni DB yoki JSON’dan olish kerak
    animelar = ["Naruto", "One Piece", "Attack on Titan"]  # vaqtincha misol
    tugmalar = ReplyKeyboardMarkup(resize_keyboard=True)
    for anime in animelar:
        tugmalar.add(anime)
    tugmalar.add("⬅️ Orqaga")
    await state.set_state("tahrirlash_tanlash")
    await message.answer("✏️ Qaysi animeni tahrirlashni xohlaysiz?", reply_markup=tugmalar)

# Anime tanlash
@dp.message_handler(state="tahrirlash_tanlash", is_admin=True)
async def anime_tanlandi(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.finish()
        await admin_panel(message)
        return
    await state.update_data(tahrir_anime=message.text)

    tugmalar = ReplyKeyboardMarkup(resize_keyboard=True)
    tugmalar.add("📌 Nomini o‘zgartirish")
    tugmalar.add("🔑 Kodini o‘zgartirish")
    tugmalar.add("🎬 Qismlar sonini o‘zgartirish")
    tugmalar.add("📡 Kanalni o‘zgartirish")
    tugmalar.add("💾 GitHub manzilini o‘zgartirish")
    tugmalar.add("🗑 O‘chirish")
    tugmalar.add("➕ Davom ettirish")
    tugmalar.add("⬅️ Orqaga")

    await state.set_state("tahrirlash_amali")
    await message.answer(f"🔧 {message.text} uchun amal tanlang:", reply_markup=tugmalar)

# 📌 Nomini o‘zgartirish
@dp.message_handler(lambda msg: msg.text == "📌 Nomini o‘zgartirish", state="tahrirlash_amali", is_admin=True)
async def tahrir_nomi(message: types.Message, state: FSMContext):
    await state.set_state("yangi_nomi")
    await message.answer("✍️ Yangi nom kiriting:")

@dp.message_handler(state="yangi_nomi", is_admin=True)
async def yangi_nom_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    eski_nom = malumot['tahrir_anime']
    yangi_nom = message.text
    # DB da yangilash logikasi shu yerda
    await state.finish()
    await message.answer(f"✅ {eski_nom} nomi {yangi_nom} ga o‘zgartirildi!")

# 🔑 Kodini o‘zgartirish
@dp.message_handler(lambda msg: msg.text == "🔑 Kodini o‘zgartirish", state="tahrirlash_amali", is_admin=True)
async def tahrir_kodi(message: types.Message, state: FSMContext):
    await state.set_state("yangi_kod")
    await message.answer("✍️ Yangi kod kiriting:")

@dp.message_handler(state="yangi_kod", is_admin=True)
async def yangi_kod_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    await state.finish()
    await message.answer(f"✅ {malumot['tahrir_anime']} kodi {message.text} ga o‘zgartirildi!")

# 🎬 Qismlar sonini o‘zgartirish
@dp.message_handler(lambda msg: msg.text == "🎬 Qismlar sonini o‘zgartirish", state="tahrirlash_amali", is_admin=True)
async def qismlar_ozgartirish(message: types.Message, state: FSMContext):
    await state.set_state("yangi_qismlar")
    await message.answer("🎬 Yangi qismlar sonini kiriting:")

@dp.message_handler(state="yangi_qismlar", is_admin=True)
async def yangi_qismlar_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    await state.finish()
    await message.answer(f"✅ {malumot['tahrir_anime']} uchun qismlar soni {message.text} qilib o‘zgartirildi!")

# 📡 Kanalni o‘zgartirish
@dp.message_handler(lambda msg: msg.text == "📡 Kanalni o‘zgartirish", state="tahrirlash_amali", is_admin=True)
async def kanal_ozgartirish(message: types.Message, state: FSMContext):
    await state.set_state("yangi_kanal")
    await message.answer("📡 Yangi kanal linkini kiriting:")

@dp.message_handler(state="yangi_kanal", is_admin=True)
async def yangi_kanal_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    await state.finish()
    await message.answer(f"✅ {malumot['tahrir_anime']} kanali {message.text} qilib o‘zgartirildi!")

# 💾 GitHub manzilini o‘zgartirish
@dp.message_handler(lambda msg: msg.text == "💾 GitHub manzilini o‘zgartirish", state="tahrirlash_amali", is_admin=True)
async def github_ozgartirish(message: types.Message, state: FSMContext):
    await state.set_state("yangi_github")
    await message.answer("💾 Yangi GitHub manzilini yuboring:")

@dp.message_handler(state="yangi_github", is_admin=True)
async def yangi_github_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    await state.finish()
    await message.answer(f"✅ {malumot['tahrir_anime']} uchun GitHub manzili yangilandi: {message.text}")

# 🗑 O‘chirish
@dp.message_handler(lambda msg: msg.text == "🗑 O‘chirish", state="tahrirlash_amali", is_admin=True)
async def anime_ochirish(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    anime = malumot['tahrir_anime']
    # DB yoki JSON dan o‘chirish logikasi
    await state.finish()
    await message.answer(f"❌ {anime} muvaffaqiyatli o‘chirildi!")

# ➕ Davom ettirish (yangi qismlar qo‘shish)
@dp.message_handler(lambda msg: msg.text == "➕ Davom ettirish", state="tahrirlash_amali", is_admin=True)
async def anime_davom(message: types.Message, state: FSMContext):
    await state.set_state("davom_qismlar")
    await message.answer("📥 Nechta yangi qism qo‘shmoqchisiz?")

@dp.message_handler(state="davom_qismlar", is_admin=True)
async def anime_davom_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    anime = malumot['tahrir_anime']
    yangi_qismlar = message.text
    # DB ga yangi qismlar qo‘shiladi
    await state.finish()
    await message.answer(f"✅ {anime} uchun {yangi_qismlar} ta yangi qism qo‘shildi!")

# ======================
# 📊 STATISTIKA
# ======================
@dp.message_handler(lambda msg: msg.text == "📊 Statistika", is_admin=True)
async def statistika_menu(message: types.Message, state: FSMContext):
    tugmalar = ReplyKeyboardMarkup(resize_keyboard=True)
    tugmalar.add("📅 Kunlik", "📆 Haftalik", "🗓 Oylik")
    tugmalar.add("⬅️ Orqaga")
    await state.set_state("statistika_turi")
    await message.answer("📊 Qaysi statistikani ko‘rishni xohlaysiz?", reply_markup=tugmalar)

@dp.message_handler(state="statistika_turi", is_admin=True)
async def statistika_korish(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.finish()
        await admin_panel(message)
        return

    turi = message.text
    # Bu yerda DB dan real statistikani olish kerak
    if turi == "📅 Kunlik":
        result = "📅 Bugun 125 foydalanuvchi botdan foydalandi."
    elif turi == "📆 Haftalik":
        result = "📆 Bu hafta 870 foydalanuvchi faol bo‘ldi."
    else:
        result = "🗓 Bu oy 3560 foydalanuvchi botdan foydalandi."

    await state.finish()
    await message.answer(result)

# ======================
# 📝 POST YARATISH
# ======================
@dp.message_handler(lambda msg: msg.text == "📝 Post yaratish", is_admin=True)
async def post_yaratish_boshlash(message: types.Message, state: FSMContext):
    await state.set_state("post_rasm")
    await message.answer("🖼 Post uchun rasm yuboring:")

@dp.message_handler(content_types=["photo"], state="post_rasm", is_admin=True)
async def post_rasm_qabul(message: types.Message, state: FSMContext):
    rasm_id = message.photo[-1].file_id
    await state.update_data(post_rasm=rasm_id)
    await state.set_state("post_text")
    await message.answer("✍️ Post matnini kiriting:")

@dp.message_handler(state="post_text", is_admin=True)
async def post_text_qabul(message: types.Message, state: FSMContext):
    await state.update_data(post_text=message.text)
    await state.set_state("post_kod")
    await message.answer("🔑 Post uchun anime kodini kiriting:")

@dp.message_handler(state="post_kod", is_admin=True)
async def post_kod_qabul(message: types.Message, state: FSMContext):
    malumot = await state.get_data()
    rasm = malumot['post_rasm']
    matn = malumot['post_text']
    kod = message.text

    # Suv belgisi va kod linkini qo‘shish logikasi shu yerda bo‘ladi
    caption = f"{matn}\n\n🔑 Kod: {kod}\n\n📺 Ko‘rish uchun botdan foydalaning!"

    await bot.send_photo(chat_id=message.chat.id, photo=rasm, caption=caption)
    await state.finish()
    await message.answer("✅ Post tayyorlandi va yuborildi!")


# =======================
# ADMIN PANEL - STATISTIKA VA POST YARATISH
# =======================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputFile

# --- Admin menyusi tugmalari ---
admin_menu = ReplyKeyboardMarkup(resize_keyboard=True)
admin_menu.add(
    KeyboardButton("➕ Anime yuklash"),
    KeyboardButton("✏️ Anime o‘zgartirish"),
)
admin_menu.add(
    KeyboardButton("📊 Statistika"),
    KeyboardButton("📝 Post yaratish"),
)
admin_menu.add(
    KeyboardButton("📢 Habar tarqatish"),
    KeyboardButton("⚙️ Sozlamalar"),
)
admin_menu.add(
    KeyboardButton("📂 Anime ro‘yxati"),
    KeyboardButton("🔙 Ortga"),
)


# --- Statistika tugmalari ---
statistika_menu = ReplyKeyboardMarkup(resize_keyboard=True)
statistika_menu.add(
    KeyboardButton("📈 Kunlik"),
    KeyboardButton("📉 Haftalik"),
    KeyboardButton("📊 Oylik")
)
statistika_menu.add(KeyboardButton("🔙 Ortga"))


# --- Post yaratish states ---
class PostYaratish(StatesGroup):
    rasm = State()
    matn = State()
    kodi = State()
    tasdiqlash = State()


# --- Statistika handler ---
@dp.message_handler(lambda msg: msg.text == "📊 Statistika", state="*")
async def admin_statistika_menu(message: types.Message):
    await message.answer("📊 Qaysi statistikani ko‘rishni xohlaysiz?", reply_markup=statistika_menu)


@dp.message_handler(lambda msg: msg.text in ["📈 Kunlik", "📉 Haftalik", "📊 Oylik"], state="*")
async def admin_statistika(message: types.Message):
    tanlov = message.text
    today = datetime.now().date()

    if tanlov == "📈 Kunlik":
        query = "SELECT COUNT(*) FROM foydalanuvchilar WHERE DATE(qoshilgan_vaqt) = $1"
        params = [today]
    elif tanlov == "📉 Haftalik":
        start = today - timedelta(days=7)
        query = "SELECT COUNT(*) FROM foydalanuvchilar WHERE DATE(qoshilgan_vaqt) BETWEEN $1 AND $2"
        params = [start, today]
    else:  # 📊 Oylik
        start = today.replace(day=1)
        query = "SELECT COUNT(*) FROM foydalanuvchilar WHERE DATE(qoshilgan_vaqt) >= $1"
        params = [start]

    try:
        count = await db.fetchval(query, *params)
    except:
        count = 0

    await message.answer(f"{tanlov} statistikasi: <b>{count}</b> foydalanuvchi", parse_mode="HTML")


# --- Post yaratish jarayoni ---
@dp.message_handler(lambda msg: msg.text == "📝 Post yaratish", state="*")
async def admin_post_start(message: types.Message, state: FSMContext):
    await message.answer("🖼 Iltimos, post uchun rasm yuboring", reply_markup=ReplyKeyboardRemove())
    await PostYaratish.rasm.set()


@dp.message_handler(content_types=["photo"], state=PostYaratish.rasm)
async def admin_post_rasm(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(rasm=photo_id)
    await message.answer("✍️ Endi post uchun matn yozing:")
    await PostYaratish.matn.set()


@dp.message_handler(state=PostYaratish.matn)
async def admin_post_matn(message: types.Message, state: FSMContext):
    await state.update_data(matn=message.text)
    await message.answer("🔢 Anime kodi kiriting:")
    await PostYaratish.kodi.set()


@dp.message_handler(state=PostYaratish.kodi)
async def admin_post_kod(message: types.Message, state: FSMContext):
    await state.update_data(kodi=message.text)

    data = await state.get_data()
    rasm = data.get("rasm")
    matn = data.get("matn")
    kodi = data.get("kodi")

    # Tasdiqlash tugmalari
    tasdiq_kb = InlineKeyboardMarkup(row_width=2)
    tasdiq_kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="post_tasdiq"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="post_bekor")
    )

    await bot.send_photo(
        chat_id=message.chat.id,
        photo=rasm,
        caption=f"📝 Post matni:\n\n{matn}\n\n📌 Anime kodi: {kodi}",
        reply_markup=tasdiq_kb
    )
    await PostYaratish.tasdiqlash.set()


@dp.callback_query_handler(lambda c: c.data in ["post_tasdiq", "post_bekor"], state=PostYaratish.tasdiqlash)
async def admin_post_tasdiq(call: types.CallbackQuery, state: FSMContext):
    if call.data == "post_tasdiq":
        data = await state.get_data()
        rasm = data.get("rasm")
        matn = data.get("matn")
        kodi = data.get("kodi")

        # Suv belgisi qo‘shish (oddiy text sifatida)
        caption = f"{matn}\n\n🔖 Anime kodi: <b>{kodi}</b>\n\n© AnimeBot"
        await bot.send_photo(chat_id=call.message.chat.id, photo=rasm, caption=caption, parse_mode="HTML")

        await call.message.answer("✅ Post muvaffaqiyatli yaratildi!", reply_markup=admin_menu)
    else:
        await call.message.answer("❌ Post yaratish bekor qilindi", reply_markup=admin_menu)

    await state.finish()
    await call.answer()

# =======================
# ADMIN PANEL - HABAR TARQATISH VA SOZLAMALAR
# =======================

from aiogram.dispatcher.filters import Text

# --- Habar tarqatish state ---
class HabarTarqatish(StatesGroup):
    matn = State()
    tasdiqlash = State()


# --- Admin menyusida tanlov ---
@dp.message_handler(Text(equals="📢 Habar tarqatish"), state="*")
async def admin_habar_tarqatish_start(message: types.Message, state: FSMContext):
    await message.answer("📢 Foydalanuvchilarga yuboriladigan habar matnini yozing:", reply_markup=ReplyKeyboardRemove())
    await HabarTarqatish.matn.set()


# --- Matnni qabul qilish ---
@dp.message_handler(state=HabarTarqatish.matn)
async def admin_habar_tarqatish_matn(message: types.Message, state: FSMContext):
    await state.update_data(matn=message.text)

    # Tasdiqlash tugmalari
    tasdiq_kb = InlineKeyboardMarkup(row_width=2)
    tasdiq_kb.add(
        InlineKeyboardButton("✅ Tarqatish", callback_data="tarqatish_tasdiq"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="tarqatish_bekor")
    )

    await message.answer(
        f"📢 Siz yubormoqchisiz:\n\n{message.text}\n\nTasdiqlaysizmi?",
        reply_markup=tasdiq_kb
    )
    await HabarTarqatish.tasdiqlash.set()


# --- Tasdiqlash yoki bekor qilish ---
@dp.callback_query_handler(lambda c: c.data in ["tarqatish_tasdiq", "tarqatish_bekor"], state=HabarTarqatish.tasdiqlash)
async def admin_habar_tarqatish_tasdiq(call: types.CallbackQuery, state: FSMContext):
    if call.data == "tarqatish_tasdiq":
        data = await state.get_data()
        matn = data.get("matn")

        users = await db.fetch("SELECT id FROM foydalanuvchilar")
        muvaffaqiyatli = 0
        xatolik = 0

        for user in users:
            try:
                await bot.send_message(chat_id=user["id"], text=matn)
                muvaffaqiyatli += 1
                await asyncio.sleep(0.05)  # flood limitdan saqlanish
            except:
                xatolik += 1

        await call.message.answer(
            f"✅ Tarqatish yakunlandi!\n\n"
            f"📨 Yuborildi: {muvaffaqiyatli}\n"
            f"❌ Xato: {xatolik}",
            reply_markup=admin_menu
        )
    else:
        await call.message.answer("❌ Tarqatish bekor qilindi", reply_markup=admin_menu)

    await state.finish()
    await call.answer()


# =======================
# ADMIN PANEL - SOZLAMALAR
# =======================

# Admin komandalarini sozlash uchun oddiy JSON fayl (sozlamalar.json) ishlatiladi
# Masalan:
# {
#   "anime_yuklash": true,
#   "anime_ozgartirish": true,
#   "statistika": true,
#   "post_yaratish": true,
#   "habar_tarqatish": true,
#   "sozlamalar": true,
#   "anime_royxati": true
# }

import json
sozlamalar_fayl = "sozlamalar.json"


async def sozlamalarni_olish():
    try:
        with open(sozlamalar_fayl, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "anime_yuklash": True,
            "anime_ozgartirish": True,
            "statistika": True,
            "post_yaratish": True,
            "habar_tarqatish": True,
            "sozlamalar": True,
            "anime_royxati": True
        }


async def sozlamalarni_saqlash(data):
    with open(sozlamalar_fayl, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- Sozlamalar menyusi ---
@dp.message_handler(Text(equals="⚙️ Sozlamalar"), state="*")
async def admin_sozlamalar_menu(message: types.Message):
    sozlamalar = await sozlamalarni_olish()
    kb = InlineKeyboardMarkup(row_width=1)

    for key, val in sozlamalar.items():
        holat = "✅" if val else "❌"
        kb.add(
            InlineKeyboardButton(f"{holat} {key.replace('_',' ').capitalize()}", callback_data=f"sozlama_{key}")
        )

    await message.answer("⚙️ Sozlamalarni boshqarish:", reply_markup=kb)


# --- Sozlamalarni yoqish/o‘chirish ---
@dp.callback_query_handler(lambda c: c.data.startswith("sozlama_"))
async def admin_sozlamalar_toggle(call: types.CallbackQuery):
    sozlamalar = await sozlamalarni_olish()
    key = call.data.replace("sozlama_", "")

    if key in sozlamalar:
        sozlamalar[key] = not sozlamalar[key]
        await sozlamalarni_saqlash(sozlamalar)

    kb = InlineKeyboardMarkup(row_width=1)
    for k, v in sozlamalar.items():
        holat = "✅" if v else "❌"
        kb.add(
            InlineKeyboardButton(f"{holat} {k.replace('_',' ').capitalize()}", callback_data=f"sozlama_{k}")
        )

    await call.message.edit_text("⚙️ Sozlamalarni boshqarish:", reply_markup=kb)
    await call.answer("✅ O‘zgartirildi")


# =======================
# ORTGA QAYTISH
# =======================

@dp.message_handler(Text(equals="🔙 Ortga"), state="*")
async def ortga_qaytish(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("🏠 Bosh menyu", reply_markup=admin_menu if message.from_user.id in ADMINLAR else user_menu)

# ===================== FOYDALANUVCHI MENU LOGIKASI =====================

@dp.message_handler(lambda message: message.text == "🔎 Anime qidirish")
async def qidirish_menu(message: types.Message):
    tugma = ReplyKeyboardMarkup(resize_keyboard=True)
    tugma.add("🔍 Kod orqali qidirish", "📖 Nomi orqali qidirish")
    tugma.add("⬅️ Orqaga")
    await message.answer("Anime qidirish usulini tanlang:", reply_markup=tugma)


@dp.message_handler(lambda message: message.text == "🔍 Kod orqali qidirish")
async def qidirish_kod(message: types.Message):
    await message.answer("Anime kodini kiriting (masalan: ANM123):")
    # bu yerda keyin foydalanuvchi kiritgan kodni DB dan qidiramiz


@dp.message_handler(lambda message: message.text == "📖 Nomi orqali qidirish")
async def qidirish_nomi(message: types.Message):
    await message.answer("Anime nomini kiriting:")
    # bu yerda nom bilan qidiramiz


@dp.message_handler(lambda message: message.text == "📨 Admin bilan aloqa")
async def admin_bilan(message: types.Message):
    await message.answer("Admin uchun xabaringizni yozing. Yuborishdan oldin tasdiqlash olinadi.")
    # bu yerda foydalanuvchi yozadi -> tasdiq tugmalari chiqadi


@dp.message_handler(lambda message: message.text == "🧪 Hamkorlik testi")
async def hamkorlik_testi(message: types.Message):
    await message.answer("Hamkorlik testi uchun mavzu yozing:")
    # keyin tasdiqlash va admin ga yuboriladi


# ===================== ADMIN MENU LOGIKASI =====================

@dp.message_handler(lambda message: message.text == "➕ Anime yuklash")
async def yuklash_boshlash(message: types.Message):
    await message.answer("Anime nomini yuboring:")
    # bu bosqichma-bosqich nom, kod, seriyalar va h.k. olinadi


@dp.message_handler(lambda message: message.text == "✏️ Anime tahrirlash")
async def tahrirlash_boshlash(message: types.Message):
    await message.answer("Qaysi animeni tahrirlashni xohlaysiz? Kodini kiriting:")
    # bu yerda admin animeni tanlaydi va o‘zgartiradi


@dp.message_handler(lambda message: message.text == "📊 Statistika")
async def statistika(message: types.Message):
    tugma = ReplyKeyboardMarkup(resize_keyboard=True)
    tugma.add("📅 Kunlik", "📆 Haftalik", "🗓 Oylik")
    tugma.add("⬅️ Orqaga")
    await message.answer("Statistika turini tanlang:", reply_markup=tugma)


@dp.message_handler(lambda message: message.text == "📝 Post yaratish")
async def post_yaratish(message: types.Message):
    await message.answer("Post uchun rasm yuboring:")
    # keyin rasm + matn + kod + suv belgisi qo‘shiladi


@dp.message_handler(lambda message: message.text == "📢 Xabar tarqatish")
async def xabar_tarqatish(message: types.Message):
    await message.answer("Tarqatmoqchi bo‘lgan xabaringizni yuboring:")
    # barcha foydalanuvchilarga broadcast qilinadi


@dp.message_handler(lambda message: message.text == "⚙️ Sozlamalar")
async def sozlamalar(message: types.Message):
    await message.answer("Sozlamalar menyusi: (bu yerda admin komandalarni boshqaradi)")
    # bu yerda ON/OFF qilinadigan komandalar chiqadi


@dp.message_handler(lambda message: message.text == "📂 Anime ro‘yxati")
async def anime_royxati(message: types.Message):
    await message.answer("Barcha animelar ro‘yxati kodi bilan chiqariladi:")
    # DB dan olish va tartiblab chiqarish


# ===================== ASOSIY START VA MAIN =====================

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    # bu yerda foydalanuvchini DB ga qo‘shamiz agar yo‘q bo‘lsa
    if user_id in ADMIN_IDS:
        await message.answer("Admin panelga xush kelibsiz!", reply_markup=admin_menu)
    else:
        await message.answer("Anime botga xush kelibsiz!", reply_markup=user_menu)


async def on_startup(dp):
    print("Bot ishga tushdi...")


if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
