import asyncpg
import asyncio
import os
from dotenv import load_dotenv

# 🔹 .env faylidan ma'lumotlarni yuklaymiz
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "baza_nomi")
DB_PASS = os.getenv("DB_PASS", "baza_paroli")
DB_NAME = os.getenv("DB_NAME", "baza_nomi")

async def create_pool():
    """
    PostgreSQL bilan ulanish hovuzini yaratadi
    """
    return await asyncpg.create_pool(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )

async def init_tables(pool):
    """
    Agar kerak bo'lsa, kestalarning yaratilishini ta'minlaydi
    """
    async with pool.acquire() as conn:
        # user_id
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_id (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(250) NOT NULL,
            status TEXT NOT NULL,
            refid VARCHAR(11) NOT NULL,
            sana VARCHAR(250) NOT NULL
        );
        """)
        # status
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS status (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(250) NOT NULL,
            kun VARCHAR(250) NOT NULL,
            date TEXT NOT NULL
        );
        """)
        # send
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS send (
            send_id SERIAL PRIMARY KEY,
            time1 TEXT NOT NULL,
            time2 TEXT NOT NULL,
            start_id TEXT NOT NULL,
            stop_id TEXT NOT NULL,
            admin_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            reply_markup TEXT NOT NULL,
            step TEXT NOT NULL,
            time3 TEXT NOT NULL,
            time4 TEXT NOT NULL,
            time5 TEXT NOT NULL
        );
        """)
        # kabinet
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS kabinet (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(250) NOT NULL,
            pul VARCHAR(250) NOT NULL,
            pul2 VARCHAR(250) NOT NULL,
            odam VARCHAR(250) NOT NULL,
            ban TEXT NOT NULL
        );
        """)
        # anime_datas
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS anime_datas (
            data_id SERIAL PRIMARY KEY,
            id TEXT NOT NULL,
            file_id TEXT NOT NULL,
            qism TEXT NOT NULL,
            sana TEXT
        );
        """)
        # animelar
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS animelar (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL,
            rams TEXT NOT NULL,
            qismi TEXT NOT NULL,
            davlat TEXT NOT NULL,
            tili TEXT NOT NULL,
            yili TEXT NOT NULL,
            janri TEXT NOT NULL,
            qidiruv TEXT NOT NULL,
            sana TEXT NOT NULL,
            aniType TEXT NOT NULL
        );
        """)

# 🔹 Test uchun
if __name__ == "__main__":
    async def main():
        pool = await create_pool()
        await init_tables(pool)
        print("✅ Baza muvaffaqiyatli tayyor!")

    asyncio.run(main())
