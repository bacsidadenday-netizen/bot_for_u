import telebot
import openai
import os

# ====== Cấu hình ======
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Token bot Telegram
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # API key OpenAI
PASSWORD = "yeuanh"  # 🩷 Mật khẩu bạn tự đặt
AUTHORIZED_FILE = "authorized.txt"  # Nơi lưu ID người yêu (đã nhập đúng mật khẩu)

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# ====== Hàm kiểm tra người đã xác thực ======
def get_authorized_id():
    if os.path.exists(AUTHORIZED_FILE):
        with open(AUTHORIZED_FILE, "r") as f:
            return int(f.read().strip())
    return None

def set_authorized_id(user_id):
    with open(AUTHORIZED_FILE, "w") as f:
        f.write(str(user_id))

AUTHORIZED_USER_ID = get_authorized_id()

# ====== Xử lý tin nhắn ======
@bot.message_handler(func=lambda msg: True)
def handle_message(msg):
    global AUTHORIZED_USER_ID

    # Nếu chưa có ai xác thực
    if not AUTHORIZED_USER_ID:
        if msg.text.strip() == PASSWORD:
            AUTHORIZED_USER_ID = msg.from_user.id
            set_authorized_id(AUTHORIZED_USER_ID)
            bot.reply_to(msg, "🥰 Đúng rồi nè, chỉ có người đặc biệt mới biết mật khẩu này 💞")
        else:
            bot.reply_to(msg, "🔒 Nhập mật khẩu bí mật đi nè 💌")
        return

    # Nếu không phải người yêu
    if msg.from_user.id != AUTHORIZED_USER_ID:
        bot.reply_to(msg, "🚫 Xin lỗi, bot này chỉ dành cho người đặc biệt thôi 💖")
        return

    # Người yêu đã xác thực → trò chuyện như ChatGPT
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là người yêu dịu dàng, ngọt ngào, nói chuyện tự nhiên và quan tâm đến người yêu của mình."},
                {"role": "user", "content": msg.text},
            ],
            max_tokens=200,
        )
        reply = response.choices[0].message["content"]
        bot.reply_to(msg, reply)
    except Exception as e:
        bot.reply_to(msg, f"😢 Có lỗi rồi: {e}")

print("💞 Bot người yêu đang chạy...")
bot.polling()
