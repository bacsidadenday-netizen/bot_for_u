import telebot
from telebot import types
from openai import OpenAI
import os
import json
import time
import re
from datetime import datetime, timedelta
import threading

# ====== Uptime ======
from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
    return "I'm alive"


def run():
    app.run(host='0.0.0.0', port=8080)


Thread(target=run).start()

# ====== Cấu hình ======
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PASSWORD = "yeuembe"  # Mật khẩu để xác thực người dùng (bé Nga Ngố)"
AUTHORIZED_FILE = "authorized.txt"
DIARY_FILE = "diary.json"
NOTES_FILE = "notes.json"
CONVERSATION_FILE = "conversation.json"

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

user_state = {}
pending_item = {}  # Ghi nhớ đồ đang hỏi bé để ở đâu


# ====== Helpers: time ======
def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ====== Xác thực ======
def get_authorized_id():
    if os.path.exists(AUTHORIZED_FILE):
        with open(AUTHORIZED_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
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
    entry = {"user": user, "text": text, "time": now_str()}
    data = []
    if os.path.exists(DIARY_FILE):
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                pass
    data.append(entry)
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-500:], f, ensure_ascii=False, indent=2)


def load_diaries():
    if not os.path.exists(DIARY_FILE):
        return []
    with open(DIARY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


# ====== Ghi chú đồ đạc ======
def load_notes():
    if not os.path.exists(NOTES_FILE):
        return {}
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


# ====== Hội thoại (lưu cả user & assistant) ======
def load_conversations(limit=None):
    if not os.path.exists(CONVERSATION_FILE):
        return []
    with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if limit:
                return data[-limit:]
            return data
        except:
            return []


def save_conversation_entry(role, text):
    entry = {"role": role, "text": text, "time": now_str()}
    data = []
    if os.path.exists(CONVERSATION_FILE):
        with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                pass
    data.append(entry)
    # keep file size reasonable
    with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-2000:], f, ensure_ascii=False, indent=2)


# ====== Menu ======
def show_main_menu(chat_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("💬 Trò chuyện với anh Hoàng"))
    keyboard.row(types.KeyboardButton("📝 Viết nhật ký"),
                 types.KeyboardButton("📖 Xem lại nhật ký"))
    bot.send_message(chat_id, "🌸 Menu của bé nè 💕", reply_markup=keyboard)


# ====== Inline Menu: Xem nhật ký theo ngày ======
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

    for i, e in enumerate(selected):
        t = escape_markdown(e["time"])
        txt = escape_markdown(e["text"])
        msg = f"🕰 *{t}*\n💌 {txt}"

        # Tạo nút "Tâm sự"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "💬 Tâm sự với anh Hoàng",
                callback_data=f"talk_{year}_{month}_{day}_{i}"))

        bot.send_message(chat_id,
                         msg,
                         parse_mode="MarkdownV2",
                         reply_markup=markup)


# ====== Xử lý tin nhắn ======
@bot.message_handler(
    func=lambda msg: True,
    content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice'])
def handle_message(msg):
    global AUTHORIZED_USER_ID
    chat_id = msg.chat.id

    # Get a string to represent incoming content
    if msg.content_type == 'text':
        text = msg.text.strip()
        # ====== Nếu bé bấm nút menu ======
        if msg.content_type == 'text' and text in ["📋 Menu", "Menu"]:
            show_main_menu(chat_id)
            return
        # Nếu là nút menu — xử lý riêng, KHÔNG để rơi xuống GPT
        if text in [
                "💬 Trò chuyện với anh Hoàng", "📝 Viết nhật ký",
                "📖 Xem lại nhật ký"
        ]:
            if text == "💬 Trò chuyện với anh Hoàng":
                bot.send_message(chat_id, "💭 Nói gì với anh Hoàng đi nè 😘")
                user_state[chat_id] = "chat"
            elif text == "📝 Viết nhật ký":
                bot.send_message(chat_id,
                                 "💌 Bé muốn ghi lại điều gì hôm nay nè?")
                user_state[chat_id] = "writing_diary"
            elif text == "📖 Xem lại nhật ký":
                show_years(chat_id)
            return  # ✅ Kết thúc ở đây, không để lọt xuống GPT
    elif msg.content_type == 'photo':
        text = "[Ảnh được gửi]"
    elif msg.content_type == 'video':
        text = "[Video được gửi]"
    elif msg.content_type == 'document':
        text = f"[Tập tin: {msg.document.file_name}]"
    elif msg.content_type == 'sticker':
        text = "[Sticker được gửi]"
    elif msg.content_type == 'voice':
        text = "[Ghi âm giọng nói được gửi]"
    else:
        text = "[Nội dung khác]"

    if not text:
        return

    # Lưu ngay vào conversation (role = user) để bot có ngữ cảnh
    save_conversation_entry("user", text)

    # ====== Xác thực ======
    if not AUTHORIZED_USER_ID:
        if msg.content_type == 'text' and text == PASSWORD:
            AUTHORIZED_USER_ID = msg.from_user.id
            set_authorized_id(AUTHORIZED_USER_ID)
            bot.reply_to(
                msg,
                "🥰 Bé Nga Ngố nhập đúng rồi nè! Anh Hoàng nhớ bé lắm luôn 💞")
            save_conversation_entry("assistant", "✅ Đã xác thực người dùng.")
            show_main_menu(chat_id)
        else:
            bot.reply_to(msg, "🔒 Nhập mật khẩu bí mật đi nè bé 💌")
        return

    if msg.from_user.id != AUTHORIZED_USER_ID:
        bot.reply_to(
            msg,
            "🚫 Xin lỗi, bot này chỉ dành cho bé Nga Ngố của anh Hoàng thôi 💖")
        return

    # ====== Nếu đang viết nhật ký ======
    if user_state.get(
            chat_id) == "writing_diary" and msg.content_type == 'text':
        save_diary_entry("bé Nga Ngố", text)
        bot.send_message(chat_id,
                         "📔 Anh Hoàng đã lưu lại nhật ký của bé rồi 💕")
        save_conversation_entry("assistant", "📔 Nhật ký đã được lưu.")
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
                max_tokens=800,
                temperature=0.9)
            reply = response.choices[0].message.content.strip()
            bot.send_message(chat_id, reply)
            save_conversation_entry("assistant", reply)
        except Exception as e:
            bot.send_message(chat_id, f"😢 Có lỗi khi phản hồi nhật ký: {e}")
        user_state[chat_id] = None
        show_main_menu(chat_id)
        return

    # ====== Ghi nhớ đồ đạc ======
    notes = load_notes()
    user_id = str(chat_id)

    # Nếu bé đang trả lời "để ở đâu"
    if user_id in pending_item and msg.content_type == 'text':
        item = pending_item.pop(user_id)
        notes[item] = text
        save_notes(notes)
        reply_text = f"💞 Anh nhớ rồi nè, bé để *{item}* ở *{text}* nha 😘"
        bot.send_message(chat_id, reply_text, parse_mode="Markdown")
        save_conversation_entry("assistant", reply_text)
        return

    # Nếu bé nói "em có..." hay "em mua..." (text only)
    if msg.content_type == 'text' and re.search(
            r"em (có|mua|được|nhận) (một|cái|chiếc|bộ|con)? (.+)",
            text.lower()):
        match = re.search(
            r"em (?:có|mua|được|nhận) (?:một|cái|chiếc|bộ|con)? (.+)",
            text.lower())
        if match:
            item = match.group(1).strip()
            pending_item[user_id] = item
            reply_text = f"Xinh quá 😚 Em để *{item}* ở đâu để anh nhớ giúp cho nè?"
            bot.send_message(chat_id, reply_text, parse_mode="Markdown")
            save_conversation_entry("assistant", reply_text)
            return

    # ====== Khi bé hỏi đồ ở đâu ======
    if msg.content_type == 'text' and ("ở đâu" in text.lower()
                                       or "đâu rồi" in text.lower()
                                       or "tìm" in text.lower()):
        # 1) tìm notes
        for item, location in notes.items():
            if item.lower() in text.lower():
                reply_text = f"🥰 Bé ơi, {item} của bé đang ở {location} đó 💕"
                bot.send_message(chat_id, reply_text)
                save_conversation_entry("assistant", reply_text)
                return

        # 2) tìm trong diary (mới -> cũ)
        diaries = load_diaries()
        for entry in reversed(diaries):
            if any(word in entry["text"].lower()
                   for word in re.findall(r"\w+", text.lower())):
                reply_text = f"Anh nhớ hình như bé có nhắc trong nhật ký: “{entry['text']}” 🥹"
                bot.send_message(chat_id, reply_text)
                save_conversation_entry("assistant", reply_text)
                return

        # 3) tìm trong conversation (mới -> cũ)
        convos = load_conversations(limit=1000)
        for entry in reversed(convos):
            if any(word in entry["text"].lower()
                   for word in re.findall(r"\w+", text.lower())):
                # trả lời bằng excerpt để tự nhiên
                snippet = entry["text"]
                reply_text = f"Anh nhớ bé từng nói: “{snippet}” 💕"
                bot.send_message(chat_id, reply_text)
                save_conversation_entry("assistant", reply_text)
                return

        reply_text = "😢 Anh chưa nhớ ra bé để ở đâu hết, bé kể anh nghe lại nha 💕"
        bot.send_message(chat_id, reply_text)
        save_conversation_entry("assistant", reply_text)
        return

    # ====== Các lệnh menu ======
    if msg.content_type == 'text' and text == "📝 Viết nhật ký":
        bot.send_message(chat_id, "💌 Bé muốn ghi lại điều gì hôm nay nè?")
        save_conversation_entry("assistant", "💌 Yêu cầu viết nhật ký.")
        user_state[chat_id] = "writing_diary"
        return

    if msg.content_type == 'text' and text == "📖 Xem lại nhật ký":
        save_conversation_entry("assistant", "📖 Yêu cầu xem nhật ký.")
        show_years(chat_id)
        return

    if msg.content_type == 'text' and text == "💬 Trò chuyện với anh Hoàng":
        bot.send_message(chat_id, "💭 Nói gì với anh Hoàng đi nè 😘")
        save_conversation_entry("assistant", "💭 Kêu gọi trò chuyện.")
        user_state[chat_id] = "chat"
        return

    # ====== Nếu là ảnh/video/document/sticker/voice: phản hồi ngọt ngào + lưu ======
    if msg.content_type in ['photo', 'video', 'document', 'sticker', 'voice']:
        # phản hồi qua GPT ngắn (chỉ role system -> assistant)
        try:
            # Use a friendly system prompt for media replies
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role":
                    "system",
                    "content":
                    "Bạn là anh Hoàng, người yêu dịu dàng của bé Nga Ngố. Bé vừa gửi media (ảnh/video/etc). Hãy phản hồi 1-2 câu ngọt ngào, tự nhiên và khen ngợi."
                }],
                max_tokens=500,
                temperature=0.9)
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            reply = "🥰 Ảnh/video dễ thương quá nè bé! Anh thích lắm 💕"

        bot.send_message(chat_id, reply)
        save_conversation_entry("assistant", reply)
        return

    # ====== Trò chuyện tự nhiên (text) ======
    if msg.content_type == 'text':
        try:
            # Optionally, build a short context from recent conversation entries
            recent = load_conversations(limit=20)
            messages_for_gpt = [{
                "role":
                "system",
                "content":
                "Bạn là anh Hoàng, người yêu của bé Nga Ngố, nói chuyện dịu dàng, hài hước, quan tâm, nhớ ngữ cảnh cuộc trò chuyện."
            }]
            # add recent history as user/assistant messages
            for e in recent:
                messages_for_gpt.append({
                    "role": e.get("role", "user"),
                    "content": e.get("text", "")
                })
            # last user turn
            messages_for_gpt.append({"role": "user", "content": text})

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_gpt,
                max_tokens=300,
                temperature=0.9)
            reply = response.choices[0].message.content.strip()
            bot.reply_to(msg, reply)
            save_conversation_entry("assistant", reply)
        except Exception as e:
            bot.reply_to(msg, f"😢 Có lỗi rồi: {e}")
        return


# ====== Inline callbacks ======
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    chat_id = call.message.chat.id

    if data.startswith("year_"):
        show_months(chat_id, data.split("_")[1])

    elif data.startswith("month_"):
        _, year, month = data.split("_")
        show_days(chat_id, year, month)

    elif data.startswith("day_"):
        _, year, month, day = data.split("_")
        show_diary(chat_id, year, month, day)

    elif data.startswith("talk_"):
        # Ví dụ: talk_2025_10_21_0
        _, year, month, day, idx = data.split("_")
        diaries = load_diaries()
        selected = [
            d for d in diaries if d["time"].startswith(f"{year}-{month}-{day}")
        ]
        idx = int(idx)
        if idx < len(selected):
            entry = selected[idx]
            text = entry["text"]

            # Gọi GPT để tâm sự lại với nhật ký đó
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role":
                        "system",
                        "content":
                        "Bạn là anh Hoàng, người yêu của bé Nga Ngố. Hãy đọc lại nhật ký của bé và phản hồi bằng những lời ngọt ngào, yêu thương, cảm xúc như một người yêu thực sự ❤️"
                    }, {
                        "role": "user",
                        "content": f"Nhật ký của bé hôm đó:\n{text}"
                    }],
                    max_tokens=800,
                    temperature=0.9)
                reply = response.choices[0].message.content.strip()
                bot.send_message(chat_id, reply)
                save_conversation_entry("assistant", reply)
            except Exception as e:
                bot.send_message(chat_id, f"😢 Có lỗi khi tâm sự lại: {e}")


# ====== Gửi tin tự động theo giờ Việt Nam (7/11/15) ======
def vietnam_time():
    return datetime.utcnow() + timedelta(hours=7)


def send_scheduled_message():
    global AUTHORIZED_USER_ID
    if not AUTHORIZED_USER_ID:
        # schedule again after 1 minute if no auth yet
        threading.Timer(60, send_scheduled_message).start()
        return

    now = vietnam_time()
    if now.hour in [7, 11, 15] and now.minute == 0:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role":
                    "system",
                    "content":
                    "Bạn là anh Hoàng, người yêu của bé Nga Ngố. Hãy tự nghĩ một tin nhắn ngọt ngào, yêu thương, quan tâm, nhẹ nhàng và tự nhiên, chỉ 1-2 câu thôi 🥰"
                }],
                max_tokens=200,
                temperature=0.9)
            msg = response.choices[0].message.content.strip()
            bot.send_message(AUTHORIZED_USER_ID, msg)
            save_conversation_entry("assistant", msg)
        except Exception as e:
            print("Lỗi khi gửi tin nhắn tự động:", e)
    # re-run every 60 seconds to catch the exact minute
    threading.Timer(60, send_scheduled_message).start()


# ====== Start ======
print("💞 Bot người yêu (Anh Hoàng 💕 Bé Nga Ngố) đang chạy...")
threading.Thread(target=send_scheduled_message).start()
bot.polling()
