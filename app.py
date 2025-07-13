import os
import logging
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

from flask import Flask, request
from telegram import Update, Bot

# --- KONFIGURASI AWAL ---
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

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

# BARIS BARU: Variabel global untuk menyimpan riwayat percakapan
# Format: {chat_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
conversation_history = {}

# BAGIAN DIUBAH: Logika pemroses pesan kini memiliki ingatan
async def process_message(update: Update):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user_message = update.message.text
    
    # BARIS BARU: Ambil atau buat riwayat baru untuk pengguna ini
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    
    user_history = conversation_history[chat_id]
    
    # BARIS BARU: Tambahkan pesan baru dari pengguna ke riwayatnya
    user_history.append({"role": "user", "content": user_message})
    
    # BARIS BARU: Batasi panjang riwayat agar tidak terlalu besar (misal: 10 pesan terakhir)
    # Ini penting untuk menghemat token API
    if len(user_history) > 10:
        user_history = user_history[-10:]

    try:
        # BARIS BARU: Gabungkan prompt sistem dengan riwayat percakapan
        messages_to_send = [
            {"role": "system", "content": "You are a helpful assistant. You can remember the last few messages in our conversation."}
        ] + user_history

        chat_completion = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages_to_send, # Menggunakan pesan yang sudah ada riwayatnya
            max_tokens=1500,
        )
        response_text = chat_completion.choices[0].message.content
        
        # BARIS BARU: Simpan balasan dari bot ke dalam riwayat
        user_history.append({"role": "assistant", "content": response_text})
        conversation_history[chat_id] = user_history # Simpan kembali riwayat yang sudah terupdate
        
        await update.message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error saat memproses pesan: {e}")
        await update.message.reply_text(f"Maaf, terjadi kesalahan: {str(e)}")


@app.route('/webhook', methods=['POST'])
def webhook():
    update_data = request.get_json()
    logger.info(f"Menerima update dari chat_id: {update_data.get('message', {}).get('chat', {}).get('id')}")
    update = Update.de_json(update_data, bot)
    asyncio.run(process_message(update))
    return 'ok', 200

@app.route('/')
def index():
    return 'Bot server with memory is running!'