import os
import logging
import tempfile
import subprocess
import speech_recognition as sr
import telebot
from telebot import types
import sqlite3
from datetime import datetime

# Путь к локальному ffmpeg
FFMPEG = os.path.join(os.path.dirname(__file__), "ffmpeg")
FFPROBE = os.path.join(os.path.dirname(__file__), "ffprobe")

TOKEN = "8536762258:AAHyBN8F1xzzgjvtEJHJVEfO6pRV0bfCLu0"
CHANNEL_ID = -1004473256789
ADMIN_ID = 608502324

bot = telebot.TeleBot(TOKEN)
bot_info = bot.get_me()
BOT_USERNAME = f"@{bot_info.username}"

conn = sqlite3.connect('bot_stats.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, joined_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action_type TEXT, audio_duration REAL, text_length INTEGER, date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS total_stats (id INTEGER PRIMARY KEY, total_voices INTEGER DEFAULT 0, total_text_length INTEGER DEFAULT 0)''')
cursor.execute("INSERT OR IGNORE INTO total_stats (id, total_voices, total_text_length) VALUES (1, 0, 0)")
conn.commit()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
print("🚀 Бот запущен!")

def add_user(user_id, first_name, username):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)", (user_id, first_name, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def add_voice_stat(user_id, duration, text_length):
    cursor.execute("INSERT INTO stats (user_id, action_type, audio_duration, text_length, date) VALUES (?, 'voice', ?, ?, ?)", (user_id, duration, text_length, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    cursor.execute("UPDATE total_stats SET total_voices = total_voices + 1, total_text_length = total_text_length + ? WHERE id = 1", (text_length,))
    conn.commit()

def get_stats():
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT total_voices, total_text_length FROM total_stats WHERE id = 1")
    stats = cursor.fetchone()
    return {'total_users': total_users, 'total_voices': stats[0], 'total_chars': stats[1]}

def emoji(id, fallback="✨"):
    return f'<tg-emoji emoji-id="{id}">{fallback}</tg-emoji>'

E_LOCK = "5778570255555105942"
E_HI = "5134122666331996794"
E_FIRE = "5384337002751630535"
E_BOT_DESC = "6030400221232501136"
E_SPARK = "5300949134662978210"
E_SIMPLE = "6043996047582170909"
E_CHECK = "5188487846968732572"
E_LISTEN = "6030445631921721471"
E_SAID = "5773626993010546707"
E_TEXT = "6039381989985882045"
E_GENERATED = "6043960760130868895"
E_SEND_VOICE = "5985478698722136468"

def transcribe_audio_bytes(audio_bytes):
    ogg_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as f:
            f.write(audio_bytes)
            ogg_path = f.name
        wav_path = ogg_path + '.wav'
        
        # Используем локальный ffmpeg
        subprocess.run([FFMPEG, '-i', ogg_path, '-ac', '1', '-ar', '16000', wav_path, '-y', '-loglevel', 'quiet'], check=True, timeout=30)
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="ru-RU")
        return text
    except Exception as e:
        logger.error(f"Error: {e}")
        return None
    finally:
        if ogg_path and os.path.exists(ogg_path): os.remove(ogg_path)
        if wav_path and os.path.exists(wav_path): os.remove(wav_path)

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_subscribe_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    try:
        chat = bot.get_chat(CHANNEL_ID)
        url = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
    except:
        url = "https://t.me/verusername"
    keyboard.add(types.InlineKeyboardButton("📢 Подписаться", url=url))
    keyboard.add(types.InlineKeyboardButton("✅ Проверить", callback_data="check_subscription"))
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    add_user(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not check_subscription(message.from_user.id):
        bot.send_message(message.from_user.id, f'{emoji(E_LOCK, "🔒")} Для использования бота нужно подписаться на наш канал. После подписки нажмите на кнопку проверить.', reply_markup=get_subscribe_keyboard(), parse_mode='HTML')
        return
    bot.send_message(message.from_user.id, f'{emoji(E_HI, "👋")} Привет! {emoji(E_FIRE, "🔥")}\n\n{emoji(E_BOT_DESC, "🤖")} Бот предназначен для расшифровки голосовых сообщений.{emoji(E_SPARK, "✨")}\n\n{emoji(E_SIMPLE, "💡")} Всё просто: ты отправляешь голосовое сообщение, и бот говорит, что там написано. {emoji(E_CHECK, "✅")}', parse_mode='HTML')

@bot.message_handler(commands=['vertexadm'])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет доступа")
        return
    stats = get_stats()
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_stats"))
    bot.send_message(message.from_user.id, f"📊 <b>Админ-панель</b>\n\n👥 Всего людей: {stats['total_users']}\n🎤 Всего голосовых: {stats['total_voices']}\n📝 Всего символов: {stats['total_chars']}", parse_mode='HTML', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "refresh_stats")
def refresh_stats(call):
    if call.from_user.id != ADMIN_ID: return
    stats = get_stats()
    bot.edit_message_text(f"📊 <b>Админ-панель</b>\n\n👥 Всего людей: {stats['total_users']}\n🎤 Всего голосовых: {stats['total_voices']}\n📝 Всего символов: {stats['total_chars']}\n🕐 {datetime.now().strftime('%H:%M:%S')}", call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=call.message.reply_markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_sub_cb(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.from_user.id, f'{emoji(E_HI, "👋")} Привет! {emoji(E_FIRE, "🔥")}\n\n{emoji(E_BOT_DESC, "🤖")} Бот предназначен для расшифровки голосовых сообщений.{emoji(E_SPARK, "✨")}\n\n{emoji(E_SIMPLE, "💡")} Всё просто: ты отправляешь голосовое сообщение, и бот говорит, что там написано. {emoji(E_CHECK, "✅")}', parse_mode='HTML')
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
    else:
        bot.answer_callback_query(call.id, "❌ Не подписан!", show_alert=True)

@bot.message_handler(content_types=['voice', 'video_note', 'audio'])
def handle_voice(message):
    if not check_subscription(message.from_user.id):
        bot.send_message(message.from_user.id, f'{emoji(E_LOCK, "🔒")} Для использования бота нужно подписаться на наш канал. После подписки нажмите на кнопку проверить.', reply_markup=get_subscribe_keyboard(), parse_mode='HTML')
        return
    if message.content_type == 'voice':
        fid, dur = message.voice.file_id, message.voice.duration
    elif message.content_type == 'video_note':
        fid, dur = message.video_note.file_id, message.video_note.length
    else:
        fid, dur = message.audio.file_id, message.audio.duration
    if dur > 120:
        bot.reply_to(message, "⚠️ Максимум 2 минуты!"); return
    status_msg = bot.reply_to(message, f'{emoji(E_LISTEN, "🎧")} Послушал голосовое...', parse_mode='HTML')
    try:
        downloaded_file = bot.download_file(bot.get_file(fid).file_path)
        if not downloaded_file:
            bot.edit_message_text("❌ Ошибка загрузки", message.chat.id, status_msg.message_id); return
        text = transcribe_audio_bytes(downloaded_file)
        if not text:
            bot.edit_message_text("🤷 Не удалось распознать речь", message.chat.id, status_msg.message_id)
        else:
            add_voice_stat(message.from_user.id, dur, len(text))
            bot.edit_message_text(f'{emoji(E_SAID, "💬")} Там сказано:\n\n<blockquote>{emoji(E_TEXT, "📝")} {text}</blockquote>\n\n{emoji(E_GENERATED, "⚡")} сгенерированно с помощью бота: {BOT_USERNAME}', message.chat.id, status_msg.message_id, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error: {e}")
        try: bot.edit_message_text("❌ Ошибка", message.chat.id, status_msg.message_id)
        except: bot.reply_to(message, "❌ Ошибка")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not check_subscription(message.from_user.id):
        bot.send_message(message.from_user.id, f'{emoji(E_LOCK, "🔒")} Для использования бота нужно подписаться на наш канал. После подписки нажмите на кнопку проверить.', reply_markup=get_subscribe_keyboard(), parse_mode='HTML')
        return
    bot.reply_to(message, f'{emoji(E_SEND_VOICE, "🎤")} Отправь мне голосовое сообщение для расшифровки!', parse_mode='HTML')

if __name__ == "__main__":
    if not os.path.exists(FFMPEG):
        print("❌ ffmpeg не найден! Запусти: bash setup.sh")
        exit(1)
    print(f"🤖 Бот: {BOT_USERNAME}")
    bot.infinity_polling()
