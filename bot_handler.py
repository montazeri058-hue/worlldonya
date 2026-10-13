"""
============================================
سالن زیبایی دنیا — Bot Callback Handler
============================================
This script handles admin inline button clicks
(approve/reject/cancel) and daily alarm messages.

Run this on ANY computer with Python 3.7+:
    pip install requests schedule
    python bot_handler.py

Keep it running. It polls Telegram for updates.
============================================
"""

import requests
import json
import time
import schedule
from datetime import datetime, timedelta

# ============================================
# CONFIGURATION — MUST MATCH YOUR MINI APP
# ============================================
BOT_TOKEN = "8888713886:AAH6EhDXAnITxfQ2q6awU910IFEnZK5NUSs"
DB_CHANNEL_ID = "-1004483005434"  # Your private channel ID
ADMIN_IDS = [5443942779, 844753244]  # Admin Telegram User IDs

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============================================
# SIMPLE FILE-BASED LOCAL DATABASE
# (Mirrors what the Mini App stores in CloudStorage)
# ============================================
DB_FILE = "bookings_db.json"

def load_db():
    """Load bookings from local JSON file"""
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"bookings": []}

def save_db(data):
    """Save bookings to local JSON file"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def find_booking(booking_id):
    """Find a booking by ID"""
    db = load_db()
    for b in db["bookings"]:
        if b.get("id") == booking_id:
            return b
    return None

def update_booking_status(booking_id, new_status):
    """Update booking status in local DB"""
    db = load_db()
    for b in db["bookings"]:
        if b.get("id") == booking_id:
            b["status"] = new_status
            save_db(db)
            return b
    return None

# ============================================
# TELEGRAM API HELPERS
# ============================================
def api_call(method, params=None):
    """Make a Telegram Bot API call"""
    try:
        response = requests.post(
            f"{API_BASE}/{method}",
            json=params or {},
            timeout=30
        )
        return response.json()
    except Exception as e:
        print(f"API Error ({method}): {e}")
        return {"ok": False}

def send_message(chat_id, text, parse_mode="Markdown", reply_markup=None):
    """Send a message via Telegram"""
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    return api_call("sendMessage", params)

def answer_callback(callback_id, text=""):
    """Answer a callback query"""
    return api_call("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": bool(text)
    })

# ============================================
# PARSE CHANNEL MESSAGES FOR BOOKINGS
# ============================================
def sync_from_channel():
    """
    Read recent channel messages to sync booking data.
    This is called periodically to keep the local DB in sync
    with what the Mini App saves to the channel.
    """
    # Note: Bot API doesn't have getHistory for channels.
    # We rely on getUpdates for channel_post updates instead.
    pass

# ============================================
# HANDLE CALLBACK QUERIES (Admin Buttons)
# ============================================
def handle_callback(callback_query):
    """Process admin inline button clicks"""
    callback_id = callback_query["id"]
    data = callback_query.get("data", "")
    admin_id = callback_query["from"]["id"]
    message = callback_query.get("message", {})

    if admin_id not in ADMIN_IDS:
        answer_callback(callback_id, "⛔ شما دسترسی ادمین ندارید")
        return

    # Parse action and booking ID
    parts = data.split("_", 1)
    if len(parts) < 2:
        answer_callback(callback_id, "❌ خطای داده")
        return

    action = parts[0]
    booking_id = parts[1]

    # Extract booking info from the message text
    msg_text = message.get("text", "")

    if action == "approve":
        handle_approve(callback_id, booking_id, msg_text, message)
    elif action == "reject":
        handle_reject(callback_id, booking_id, msg_text, message)
    elif action == "cancel":
        handle_cancel(callback_id, booking_id, msg_text, message)
    else:
        answer_callback(callback_id, "❌ عملیات نامعتبر")

def extract_user_id_from_booking_id(booking_id):
    """Extract user ID from booking ID format: BK_USERID_TIMESTAMP"""
    try:
        parts = booking_id.split("_")
        if len(parts) >= 3:
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return None

def handle_approve(callback_id, booking_id, msg_text, message):
    """Approve a booking"""
    user_id = extract_user_id_from_booking_id(booking_id)
    
    # Update local DB
    booking = update_booking_status(booking_id, "approved")

    # Notify user
    if user_id:
        send_message(
            user_id,
            "✅ *نوبت شما تأیید شد!*\n\n"
            "منتظر دیدار شما هستیم! 💇‍♀️\n\n"
            "🌐 سالن زیبایی دنیا"
        )

    # Update admin message to show it's been processed
    if message.get("chat") and message.get("message_id"):
        api_call("editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": msg_text + "\n\n✅ *تأیید شد* ✅",
            "parse_mode": "Markdown"
        })

    # Log to channel
    api_call("sendMessage", {
        "chat_id": DB_CHANNEL_ID,
        "text": f"✅ STATUS_UPDATE\n{json.dumps({'bookingId': booking_id, 'status': 'approved', 'by': 'admin'})}"
    })

    answer_callback(callback_id, "✅ نوبت تأیید شد")
    print(f"[APPROVE] Booking {booking_id} approved")

def handle_reject(callback_id, booking_id, msg_text, message):
    """Reject a booking"""
    user_id = extract_user_id_from_booking_id(booking_id)

    update_booking_status(booking_id, "rejected")

    if user_id:
        send_message(
            user_id,
            "❌ *متأسفانه نوبت شما رد شد*\n\n"
            "لطفاً زمان دیگری را انتخاب کنید.\n\n"
            "🌐 سالن زیبایی دنیا"
        )

    if message.get("chat") and message.get("message_id"):
        api_call("editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": msg_text + "\n\n❌ *رد شد* ❌",
            "parse_mode": "Markdown"
        })

    api_call("sendMessage", {
        "chat_id": DB_CHANNEL_ID,
        "text": f"❌ STATUS_UPDATE\n{json.dumps({'bookingId': booking_id, 'status': 'rejected', 'by': 'admin'})}"
    })

    answer_callback(callback_id, "❌ نوبت رد شد")
    print(f"[REJECT] Booking {booking_id} rejected")

def handle_cancel(callback_id, booking_id, msg_text, message):
    """Cancel a booking (admin-initiated)"""
    user_id = extract_user_id_from_booking_id(booking_id)

    update_booking_status(booking_id, "cancelled")

    if user_id:
        send_message(
            user_id,
            "🗑 *نوبت شما توسط مدیریت لغو شد*\n\n"
            "برای رزرو مجدد از ربات استفاده کنید.\n\n"
            "🌐 سالن زیبایی دنیا"
        )

    if message.get("chat") and message.get("message_id"):
        api_call("editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": msg_text + "\n\n🗑 *لغو شد* 🗑",
            "parse_mode": "Markdown"
        })

    api_call("sendMessage", {
        "chat_id": DB_CHANNEL_ID,
        "text": f"🗑 STATUS_UPDATE\n{json.dumps({'bookingId': booking_id, 'status': 'cancelled', 'by': 'admin'})}"
    })

    answer_callback(callback_id, "🗑 نوبت لغو شد")
    print(f"[CANCEL] Booking {booking_id} cancelled")

# ============================================
# HANDLE /start AND TEXT MESSAGES
# ============================================
def handle_message(message):
    """Handle incoming text messages"""
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    user_id = message["from"]["id"]

    if text == "/start":
        # Send welcome message with Mini App button
        send_message(
            chat_id,
            "💇‍♀️ *به ربات سالن زیبایی دنیا خوش آمدید!*\n\n"
            "از طریق دکمه زیر می‌توانید نوبت خود را رزرو کنید.\n\n"
            "⏰ ساعت کاری: ۱۴:۰۰ تا ۱۸:۰۰\n"
            "📅 رزرو آنلاین ۲۴ ساعته",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "📅 رزرو نوبت", "web_app": {"url": "YOUR_MINI_APP_URL_HERE"}}],
                    [{"text": "📋 نوبت‌های من", "web_app": {"url": "YOUR_MINI_APP_URL_HERE"}}],
                    [{"text": "🌐 وبسایت دنیا", "url": "https://YOUR_WEBSITE_URL"}]
                ]
            }
        )

    elif text == "/admin" and user_id in ADMIN_IDS:
        send_message(
            chat_id,
            "👑 *پنل مدیریت*\n\n"
            "از طریق مینی اپ به پنل مدیریت دسترسی دارید.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "👑 ورود به پنل مدیریت", "web_app": {"url": "YOUR_MINI_APP_URL_HERE"}}]
                ]
            }
        )

    elif text == "/today" and user_id in ADMIN_IDS:
        send_daily_report(chat_id)

# ============================================
# HANDLE CHANNEL POSTS (Sync Database)
# ============================================
def handle_channel_post(post):
    """
    When the Mini App saves a booking to the channel,
    we pick it up here and save it to our local DB too.
    """
    text = post.get("text", "")

    if text.startswith("📦 BOOKING_DATA"):
        try:
            json_str = text.replace("📦 BOOKING_DATA\n", "")
            booking = json.loads(json_str)

            db = load_db()
            # Check if booking already exists
            existing = any(b.get("id") == booking.get("id") for b in db["bookings"])
            if not existing:
                db["bookings"].append(booking)
                save_db(db)
                print(f"[SYNC] New booking saved: {booking.get('id')}")
        except json.JSONDecodeError as e:
            print(f"[SYNC ERROR] Could not parse booking: {e}")

    elif "STATUS_UPDATE" in text:
        try:
            lines = text.split("\n")
            if len(lines) >= 2:
                update = json.loads(lines[1])
                booking_id = update.get("bookingId")
                new_status = update.get("status")
                if booking_id and new_status:
                    update_booking_status(booking_id, new_status)
                    print(f"[SYNC] Status updated: {booking_id} -> {new_status}")
        except json.JSONDecodeError as e:
            print(f"[SYNC ERROR] Could not parse status update: {e}")

# ============================================
# DAILY ALARM — Send Today's & Tomorrow's Appointments
# ============================================
def send_daily_report(chat_id=None):
    """Send daily appointment summary to admins"""
    db = load_db()
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    today_bookings = [
        b for b in db["bookings"]
        if b.get("date") == today and b.get("status") in ("approved", "pending")
    ]

    tomorrow_bookings = [
        b for b in db["bookings"]
        if b.get("date") == tomorrow and b.get("status") in ("approved", "pending")
    ]

    report = "📊 *گزارش روزانه سالن دنیا*\n"
    report += "━━━━━━━━━━━━━━━━━\n\n"

    report += f"📅 *نوبت‌های امروز ({today}):*\n"
    if today_bookings:
        for b in sorted(today_bookings, key=lambda x: x.get("time", "")):
            status = "✅" if b["status"] == "approved" else "⏳"
            report += f"  {status} {b.get('time', '?')} — {b.get('userName', '?')} — {', '.join(b.get('services', []))}\n"
    else:
        report += "  نوبتی ندارید ✨\n"

    report += f"\n📅 *نوبت‌های فردا ({tomorrow}):*\n"
    if tomorrow_bookings:
        for b in sorted(tomorrow_bookings, key=lambda x: x.get("time", "")):
            status = "✅" if b["status"] == "approved" else "⏳"
            report += f"  {status} {b.get('time', '?')} — {b.get('userName', '?')} — {', '.join(b.get('services', []))}\n"
    else:
        report += "  نوبتی ندارید ✨\n"

    report += "\n━━━━━━━━━━━━━━━━━\n"
    report += f"📈 کل نوبت‌ها: {len(db['bookings'])}"

    targets = [chat_id] if chat_id else ADMIN_IDS
    for admin_id in targets:
        send_message(admin_id, report)

    print(f"[DAILY] Report sent to {len(targets)} admin(s)")

# Schedule daily alarm at 8:00 AM Iran time (adjust as needed)
schedule.every().day.at("08:00").do(send_daily_report)
# Also send at 13:00 (1 hour before work starts)
schedule.every().day.at("13:00").do(send_daily_report)

# ============================================
# MAIN POLLING LOOP
# ============================================
def main():
    """Main bot loop using long polling"""
    print("=" * 50)
    print("🚀 سالن زیبایی دنیا — Bot Handler Started")
    print(f"📡 Bot Token: ...{BOT_TOKEN[-8:]}")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"📺 Channel: {DB_CHANNEL_ID}")
    print("=" * 50)

    # Initialize DB file if not exists
    db = load_db()
    save_db(db)

    # Set bot commands
    api_call("setMyCommands", {
        "commands": [
            {"command": "start", "description": "شروع و منوی اصلی"},
            {"command": "today", "description": "نوبت‌های امروز (ادمین)"},
            {"command": "admin", "description": "پنل مدیریت (ادمین)"}
        ]
    })

    offset = 0

    while True:
        try:
            # Run scheduled tasks
            schedule.run_pending()

            # Long poll for updates
            result = api_call("getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message", "callback_query", "channel_post"]
            })

            if result.get("ok") and result.get("result"):
                for update in result["result"]:
                    offset = update["update_id"] + 1

                    # Handle callback queries (admin buttons)
                    if "callback_query" in update:
                        handle_callback(update["callback_query"])

                    # Handle messages (/start, etc.)
                    elif "message" in update:
                        handle_message(update["message"])

                    # Handle channel posts (database sync)
                    elif "channel_post" in update:
                        handle_channel_post(update["channel_post"])

        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()