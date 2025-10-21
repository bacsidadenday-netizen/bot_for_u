import telebot
from telebot import types
from openai import OpenAI
import os
import json
import time
import re
from datetime import datetime

# ====== Cấu hình ======
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PASSWORD = "yeuanh"
AUTHORIZED_FILE = "authorized.txt"
DIARY_FILE = "diary.json"
CONVO_FILE = "conversation.json"  # Lưu hội thoại vĩnh viễn

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)
user_state = {}


# ====== Bộ nhớ hội thoại vĩnh viễn ======
def load_conversation():
    if os.path.exists(CONVO_FILE):
        with open(CONVO_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


def save_conversation(data):
    with open(CONVO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


conversation_history = load_conversation()
MAX_HISTORY = 2000  # 🧠 Nhớ được tới 2000 tin nhắn gần nhất


# ====== Xác thực ======
def get_authorized_id():
    if os.path.exists(AUTHORIZED_FILE):
        with open(AUTHORIZED_FILE, "r") as f:
            return int(f.read().strip())
    return None


def set_authorized_id(user_id):
    with open(AUTHORIZED_FILE, "w") as f:
        f.write(str(user_id))


AUTHORIZED_USER_ID = get_authorized_id()


# ====== Escape Markdown ======
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


# ====== Nhật ký ======
def save_diary_entry(user, text):
    entry = {
        "user": user,
        "text": text,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    data = []
    if os.path.exists(DIARY_FILE):
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                pass
    data.append(entry)
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_diaries():
    if not os.path.exists(DIARY_FILE):
        return []
    with open(DIARY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


# ====== Menu ======
def show_menu_button(chat_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("📋 Menu"))
    bot.send_message(chat_id,
                     "💞 Anh Hoàng đang ở đây nè 💬",
                     reply_markup=keyboard)


def show_main_menu(chat_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("📝 Viết nhật ký"),
                 types.KeyboardButton("📖 Xem lại nhật ký"))
    keyboard.add(types.KeyboardButton("💬 Trò chuyện với anh Hoàng"),
                 types.KeyboardButton("❌ Ẩn menu"))
    bot.send_message(chat_id, "🌸 Bé chọn đi nè:", reply_markup=keyboard)


# ====== Inline Menu: Xem nhật ký ======
def show_years(chat_id):
    diaries = load_diaries()
    if not diaries:
        bot.send_message(chat_id, "📭 Bé chưa có nhật ký nào hết á 😅")
        return

    years = sorted(list({d["time"][:4] for d in diaries}), reverse=True)
    markup = types.InlineKeyboardMarkup()
    for y in years:
        markup.add(types.InlineKeyboardButton(y, callback_data=f"year_{y}"))
    bot.send_message(chat_id,
                     "📅 Bé muốn xem nhật ký năm nào nè?",
                     reply_markup=markup)


def show_months(chat_id, year):
    diaries = load_diaries()
    months = sorted(
        list({d["time"][5:7]
              for d in diaries if d["time"].startswith(year)}))
    markup = types.InlineKeyboardMarkup()
    for m in months:
        markup.add(
            types.InlineKeyboardButton(f"Tháng {m}",
                                       callback_data=f"month_{year}_{m}"))
    bot.send_message(chat_id,
                     f"📆 Bé chọn tháng trong năm {year} nha 💕",
                     reply_markup=markup)


def show_days(chat_id, year, month):
    diaries = load_diaries()
    days = sorted(
        list({
            d["time"][8:10]
            for d in diaries if d["time"].startswith(f"{year}-{month}")
        }))
    markup = types.InlineKeyboardMarkup()
    for day in days:
        markup.add(
            types.InlineKeyboardButton(
                f"Ngày {day}", callback_data=f"day_{year}_{month}_{day}"))
    bot.send_message(chat_id,
                     f"🩷 Bé chọn ngày trong {month}/{year} nè:",
                     reply_markup=markup)


def show_diary(chat_id, year, month, day):
    diaries = load_diaries()
    selected = [
        d for d in diaries if d["time"].startswith(f"{year}-{month}-{day}")
    ]
    if not selected:
        bot.send_message(chat_id, "😅 Không thấy nhật ký ngày đó rồi bé ơi.")
        return
    for e in selected:
        t = escape_markdown(e["time"])
        txt = escape_markdown(e["text"])
        msg = f"🕰 *{t}*\n💌 {txt}"
        bot.send_message(chat_id, msg, parse_mode="MarkdownV2")


# ====== Tin nhắn chính ======
@bot.message_handler(func=lambda msg: True)
def handle_message(msg):
    global AUTHORIZED_USER_ID
    chat_id = msg.chat.id
    text = msg.text.strip()

    # --- Đăng nhập ---
    if not AUTHORIZED_USER_ID:
        if text == PASSWORD:
            AUTHORIZED_USER_ID = msg.from_user.id
            set_authorized_id(AUTHORIZED_USER_ID)
            bot.reply_to(
                msg,
                "🥰 Bé Nga Ngố nhập đúng rồi nè! Anh Hoàng nhớ bé lắm luôn 💞")
            show_menu_button(chat_id)
        else:
            bot.reply_to(msg, "🔒 Nhập mật khẩu bí mật đi nè bé 💌")
        return

    # --- Chặn người lạ ---
    if msg.from_user.id != AUTHORIZED_USER_ID:
        bot.reply_to(
            msg,
            "🚫 Xin lỗi, bot này chỉ dành cho bé Nga Ngố của anh Hoàng thôi 💖")
        return

    # --- Menu hiển thị / ẩn ---
    if text == "📋 Menu":
        show_main_menu(chat_id)
        return

    if text == "❌ Ẩn menu":
        show_menu_button(chat_id)
        return

    # --- Viết nhật ký ---
    if user_state.get(chat_id) == "writing_diary":
        save_diary_entry("bé Nga Ngố", text)
        bot.send_message(chat_id,
                         "📔 Anh Hoàng đã lưu lại nhật ký của bé rồi 💕")

        # GPT phản hồi nhật ký
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role":
                    "system",
                    "content":
                    "Bạn là anh Hoàng yêu bé Nga Ngố, phản hồi lại nhật ký một cách ngọt ngào ❤️🥺😘"
                }, {
                    "role": "user",
                    "content": f"Nhật ký hôm nay của bé là:\n{text}"
                }],
                max_tokens=200,
            )
            reply = response.choices[0].message.content.strip()
            bot.send_message(chat_id, reply)
        except Exception as e:
            bot.send_message(chat_id, f"😢 Có lỗi khi phản hồi nhật ký: {e}")

        user_state[chat_id] = None
        show_menu_button(chat_id)
        return

    # --- Chọn menu ---
    if text == "📝 Viết nhật ký":
        bot.send_message(chat_id, "💌 Bé muốn ghi lại điều gì hôm nay nè?")
        user_state[chat_id] = "writing_diary"
        return

    if text == "📖 Xem lại nhật ký":
        show_years(chat_id)
        return

    # --- Trò chuyện & lưu ---
    fresh_memory = load_conversation()
    history = fresh_memory.get(str(chat_id), [])
    history.append({"role": "user", "content": text})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    messages = [{
        "role":
        "system",
        "content":
        "Bạn là anh Hoàng, người yêu của bé Nga Ngố, luôn nói chuyện dịu dàng, nhớ hết những gì đã nói ❤️🥺😘"
    }] + history

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=250,
        )
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        fresh_memory[str(chat_id)] = history
        save_conversation(fresh_memory)
        bot.reply_to(msg, reply)
    except Exception as e:
        bot.reply_to(msg, f"😢 Có lỗi rồi: {e}")


# ====== Xử lý callback Inline Button ======
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    chat_id = call.message.chat.id

    if data.startswith("year_"):
        year = data.split("_")[1]
        show_months(chat_id, year)
    elif data.startswith("month_"):
        _, year, month = data.split("_")
        show_days(chat_id, year, month)
    elif data.startswith("day_"):
        _, year, month, day = data.split("_")
        show_diary(chat_id, year, month, day)


# ====== Gửi menu tự động khi khởi động lại bot ======
if AUTHORIZED_USER_ID:
    try:
        show_menu_button(AUTHORIZED_USER_ID)
    except Exception as e:
        print("⚠️ Không gửi được menu khởi động:", e)

print("💞 Bot người yêu (Anh Hoàng 💕 Bé Nga Ngố) đang chạy...")
bot.polling()
