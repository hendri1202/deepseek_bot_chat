import os
import logging
import asyncio
from openai import OpenAI
from flask import Flask, request
from telegram import Update, Bot

# --- KONFIGURASI AWAL ---
# Mengatur logging untuk memantau aktivitas bot di dasbor Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- MENGAMBIL KUNCI API DARI ENVIRONMENT VARIABLES RENDER ---
# load_dotenv() tidak lagi diperlukan karena Render menggunakan sistemnya sendiri.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Pengecekan penting saat aplikasi dimulai.
# Jika salah satu token tidak ada, aplikasi akan crash dengan pesan error yang jelas di Logs Render.
if not TELEGRAM_BOT_TOKEN:
    logger.critical("Variabel TELEGRAM_BOT_TOKEN tidak ditemukan! Bot tidak bisa dimulai.")
    raise ValueError("Missing TELEGRAM_BOT_TOKEN environment variable")

if not DEEPSEEK_API_KEY:
    logger.critical("Variabel DEEPSEEK_API_KEY tidak ditemukan! Bot tidak bisa dimulai.")
    raise ValueError("Missing DEEPSEEK_API_KEY environment variable")

# Inisialisasi Klien API
try:
    deepseek_client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1"
    )
except Exception as e:
    logger.error(f"Gagal menginisialisasi klien DeepSeek: {e}")
    deepseek_client = None

# --- APLIKASI WEB FLASK & LOGIKA BOT ---

app = Flask(__name__)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# PERINGATAN: "Memori" ini bersifat sementara dan akan HILANG setiap kali server
# di Render restart atau tertidur (jika menggunakan paket gratis).
# Untuk memori permanen, Anda perlu menggunakan database (misalnya PostgreSQL).
conversation_history = {}

async def process_message(update: Update):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user_message = update.message.text
    
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    
    user_history = conversation_history[chat_id]
    user_history.append({"role": "user", "content": user_message})
    
    if len(user_history) > 10:
        user_history = user_history[-10:]

    try:
        messages_to_send = [
            {"role": "system", "content": "You are a helpful assistant. You can remember the last few messages in our conversation."}
        ] + user_history

        chat_completion = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_to_send,
            max_tokens=1500,
        )
        response_text = chat_completion.choices[0].message.content
        
        user_history.append({"role": "assistant", "content": response_text})
        conversation_history[chat_id] = user_history
        
        await update.message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error saat memproses pesan: {e}")
        await update.message.reply_text(f"Maaf, terjadi kesalahan. Silakan coba lagi nanti.")

# === BAGIAN PENTING UNTUK WEBHOOK ===

# 1. Endpoint untuk MENERIMA pesan dari Telegram.
# Path-nya menggunakan token agar tidak mudah ditebak orang lain (lebih aman).
@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def webhook_handler():
    update = Update.de_json(request.get_json(force=True), bot)
    # Menjalankan fungsi async di dalam thread Flask
    asyncio.run(process_message(update))
    return 'ok'

# 2. Endpoint untuk MENYETEL/MENDAFTARKAN webhook.
# Anda hanya perlu mengunjungi URL ini sekali saja untuk melakukan setup.
@app.route('/setwebhook')
def set_webhook():
    # URL publik Anda dari dasbor Render.
    render_url = f"https://deepseek-bot-chat.onrender.com/{TELEGRAM_BOT_TOKEN}"
    
    # Memberitahu Telegram untuk mengirim update ke URL ini
    status = bot.set_webhook(render_url)
    
    if status:
        logger.info(f"Webhook berhasil di-set ke: {render_url}")
        return f"Webhook setup ok! URL set to: {render_url}"
    else:
        logger.error("Gagal menyetel webhook.")
        return "Webhook setup failed."

# 3. Endpoint dasar untuk mengecek apakah server hidup.
@app.route('/')
def index():
    return 'Bot server is running!'
