import os
import io
import logging
import speech_recognition as sr
import telebot
from telebot import types
import sqlite3
from datetime import datetime
import subprocess
import tempfile

# ========== НАСТРОЙКИ ==========
TOKEN = "8536762258:AAHyBN8F1xzzgjvtEJHJVEfO6pRV0bfCLu0"
CHANNEL_ID = -1004473256789
ADMIN_ID = 608502324

bot = telebot.TeleBot(TOKEN)
bot_info = bot.get_me()
BOT_USERNAME = f"@{bot_info.username}"

# ========== БАЗА ДАННЫХ ==========
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

# ========== ФУНКЦИИ БД ==========
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

# ========== ПРЕМИУМ ЭМОДЗИ ==========
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

# ========== РАСШИФРОВКА БЕЗ ffmpeg (ЧЕРЕЗ WAV) ==========
def transcribe_ogg_bytes(ogg_bytes):
    """Расшифровка OGG напрямую через speech_recognition"""
    try:
        # Сохраняем OGG во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp:
            tmp.write(ogg_bytes)
            ogg_path = tmp.name
        
        # speech_recognition может работать с OGG если установлен pocketsphinx или google
        recognizer = sr.Recognizer()
        
        # Пробуем прочитать как аудиофайл
        with sr.AudioFile(ogg_path) as source:
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio, language="ru-RU")
        
        os.remove(ogg_path)
        return text
        
    except Exception as e:
        logger.error(f"OGG recognition error: {e}")
        try:
            os.remove(ogg_path)
        except:
            pass
        return None

def transcribe_audio_bytes(audio_bytes):
    """Пробуем разные способы расшифровки"""
    # Способ 1: Напрямую через OGG
    text = transcribe_ogg_bytes(audio_bytes)
    if text:
        return text
    
    # Способ 2: Через WAV (если есть ffmpeg)
    try:
        import subprocess
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp:
            tmp.write(audio_bytes)
            ogg_path = tmp.name
        
        wav_path = ogg_path + '.wav'
        
        # Пробуем ffmpeg если есть
        try:
            subprocess.run(['ffmpeg', '-i', ogg_path, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', wav_path, '-y', '-loglevel', 'quiet'], check=True, timeout=30)
        except:
            os.remove(ogg_path)
            return None
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio, language="ru-RU")
        
        os.remove(ogg_path)
        os.remove(wav_path)
        return text
        
    except Exception as e:
        logger.error(f"WAV recognition error: {e}")
        return None

# ========== ПРОВЕРКА ПОДПИСКИ ==========
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
        if chat.username:
            url = f"https://t.me/{chat.username}"
        else:
            url = f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
    except:
        url = "https://t.me/verusername"
    
    keyboard.add(types.InlineKeyboardButton("📢 Подписаться", url=url))
    keyboard.add(types.InlineKeyboardButton("✅ Проверить", callback_data="check_subscription"))
    return keyboard

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    add_user(user_id, first_name, username)
    
    if not check_subscription(user_id):
        no_sub = f'{emoji(E_LOCK, "🔒")} Для использования бота нужно подписаться на наш канал. После подписки нажмите на кнопку проверить.'
        bot.send_message(user_id, no_sub, reply_markup=get_subscribe_keyboard(), parse_mode='HTML')
        return
    
    welcome = (
        f'{emoji(E_HI, "👋")} Привет! {emoji(E_FIRE, "🔥")}\n\n'
        f'{emoji(E_BOT_DESC, "🤖")} Бот предназначен для расшифровки голосовых сообщений.{emoji(E_SPARK, "✨")}\n\n'
        f'{emoji(E_SIMPLE, "💡")} Всё просто: ты отправляешь голосовое сообщение, и бот говорит, что там написано. {emoji(E_CHECK, "✅")}'
    )
    bot.send_message(user_id, welcome, parse_mode='HTML')

# ========== АДМИН-ПАНЕЛЬ ==========
@bot.message_handler(commands=['vertexadm'])
def admin_command(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет доступа к этой команде.")
        return
    
    stats = get_stats()
    admin_text = (
        "📊 <b>Админ-панель</b>\n\n"
        f"👥 Всего людей: {stats['total_users']}\n"
        f"🎤 Всего голосовых: {stats['total_voices']}\n"
        f"📝 Всего переведено символов: {stats['total_chars']}\n\n"
        f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔄 Обновить статистику", callback_data="refresh_stats"))
    bot.send_message(user_id, admin_text, parse_mode='HTML', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "refresh_stats")
def refresh_stats(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Нет доступа!")
        return
    
    stats = get_stats()
    admin_text = (
        "📊 <b>Админ-панель</b>\n\n"
        f"👥 Всего людей: {stats['total_users']}\n"
        f"🎤 Всего голосовых: {stats['total_voices']}\n"
        f"📝 Всего переведено символов: {stats['total_chars']}\n\n"
        f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    bot.edit_message_text(admin_text, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=call.message.reply_markup)
    bot.answer_callback_query(call.id, "✅ Статистика обновлена!")

# ========== ПРОВЕРКА ПОДПИСКИ КОЛБЕК ==========
@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    if check_subscription(user_id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        welcome = (
            f'{emoji(E_HI, "👋")} Привет! {emoji(E_FIRE, "🔥")}\n\n'
            f'{emoji(E_BOT_DESC, "🤖")} Бот предназначен для расшифровки голосовых сообщений.{emoji(E_SPARK, "✨")}\n\n'
            f'{emoji(E_SIMPLE, "💡")} Всё просто: ты отправляешь голосовое сообщение, и бот говорит, что там написано. {emoji(E_CHECK, "✅")}'
        )
        bot.send_message(user_id, welcome, parse_mode='HTML')
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
    else:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписались!", show_alert=True)

# ========== ОБРАБОТКА ГОЛОСОВЫХ ==========
@bot.message_handler(content_types=['voice', 'video_note', 'audio'])
def handle_voice(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        no_sub = f'{emoji(E_LOCK, "🔒")} Для использования бота нужно подписаться на наш канал. После подписки нажмите на кнопку проверить.'
        bot.send_message(user_id, no_sub, reply_markup=get_subscribe_keyboard(), parse_mode='HTML')
        return
    
    if message.content_type == 'voice':
        file_id = message.voice.file_id
        duration = message.voice.duration
    elif message.content_type == 'video_note':
        file_id = message.video_note.file_id
        duration = message.video_note.length
    elif message.content_type == 'audio':
        file_id = message.audio.file_id
        duration = message.audio.duration
    else:
        return
    
    if duration > 120:
        bot.reply_to(message, "⚠️ Максимум 2 минуты!")
        return
    
    status_msg = bot.reply_to(message, f'{emoji(E_LISTEN, "🎧")} Послушал голосовое...', parse_mode='HTML')
    
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        if not downloaded_file:
            bot.edit_message_text("❌ Ошибка загрузки", message.chat.id, status_msg.message_id)
            return
        
        text = transcribe_audio_bytes(downloaded_file)
        
        if text is None:
            bot.edit_message_text("🤷 Не удалось распознать речь", message.chat.id, status_msg.message_id)
        else:
            add_voice_stat(user_id, duration, len(text))
            
            response = (
                f'{emoji(E_SAID, "💬")} Там сказано:\n\n'
                f'<blockquote>{emoji(E_TEXT, "📝")} {text}</blockquote>\n\n'
                f'{emoji(E_GENERATED, "⚡")} сгенерированно с помощью бота: {BOT_USERNAME}'
            )
            
            bot.edit_message_text(response, message.chat.id, status_msg.message_id, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        try:
            bot.edit_message_text("❌ Ошибка обработки", message.chat.id, status_msg.message_id)
        except:
            bot.reply_to(message, "❌ Ошибка обработки")

# ========== ТЕКСТ ==========
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        no_sub = f'{emoji(E_LOCK, "🔒")} Для использования бота нужно подписаться на наш канал. После подписки нажмите на кнопку проверить.'
        bot.send_message(user_id, no_sub, reply_markup=get_subscribe_keyboard(), parse_mode='HTML')
        return
    
    text_response = f'{emoji(E_SEND_VOICE, "🎤")} Отправь мне голосовое сообщение для расшифровки!'
    bot.reply_to(message, text_response, parse_mode='HTML')

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print(f"🤖 Бот: {BOT_USERNAME}")
    print("🔄 Запускаю бота...")
    bot.infinity_polling()
