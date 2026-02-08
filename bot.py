from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import json
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")

# ===================== حفظ بيانات المستخدمين =====================

USERS_FILE = "users.json"
PHOTOS_DIR = "profile_photos"

if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def save_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    users = load_users()

    user_id = str(user.id)

    photos = await context.bot.get_user_profile_photos(user.id)
    photo_path = users.get(user_id, {}).get("photo_path")

    if photos.total_count > 0:
        file = await photos.photos[0][-1].get_file()

        photo_path = f"{PHOTOS_DIR}/{user_id}.jpg"
        await file.download_to_drive(photo_path)

    users[user_id] = {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_path": photo_path,
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "first_seen": users.get(user_id, {}).get(
            "first_seen",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    }

    save_users(users)

# ===================== تحميل حسب المجموعة =====================

def load_schedule(group):
    path = f"G{group}/schedule{group}.json"

    if not os.path.exists(path):
        return None

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_teachers(group):

    path = "teachers_all_groups.json"

    if not os.path.exists(path):
        return None

    with open(path, encoding="utf-8") as f:
        all_data = json.load(f)

    return all_data.get(str(group), [])


def get_teachers_by(group, module, lesson_type):

    teachers = load_teachers(group)

    if teachers is None:
        return []

    key = "محاضر" if lesson_type == "محاضرة" else lesson_type

    result = []

    for t in teachers:
        if t.get("module") == module and key in t.get("type", ""):
            result.append(t)

    return result

# ===================== الوقت =====================

def get_day_name(offset=0):
    now = datetime.now(pytz.timezone("Africa/Casablanca"))
    target = now + timedelta(days=offset)
    return target.strftime("%A").lower()

AR_DAYS = {
    "sunday": "الأحد",
    "monday": "الاثنين",
    "tuesday": "الثلاثاء",
    "wednesday": "الأربعاء",
    "thursday": "الخميس"
}

WEEKEND_DAYS = {
    "friday": "الجمعة",
    "saturday": "السبت"
}

REVERSE_DAYS = {
    "الأحد": "sunday",
    "الاثنين": "monday",
    "الثلاثاء": "tuesday",
    "الأربعاء": "wednesday",
    "الخميس": "thursday"
}

MODULE_ORDER = [
"Electronique fondamentale","Structure machine 2",
"Analyse 2","Algèbre 2",
"Introduction à l'intelligence artificielle",
"Logique mathématique","Algorithmique et structure de données 2"
]

# ===================== تنسيق =====================

def format_lessons(lessons):
    if not lessons:
        return "✅ لا توجد حصص في هذا اليوم."

    lessons = sorted(lessons, key=lambda x: x["start"])

    text = ""
    for l in lessons:
        text += f"""
‏📚  {l['module']}
‏🎯  {l.get('type','')}
‏⏰ من {l['start']} إلى {l['end']}
‏🏫  {l['room']}
‏━━━━━━━━━━━━━━━━
"""
    return text

# ===================== الحالي والتالي =====================

def get_current_and_next_today(schedule):

    now = datetime.now(pytz.timezone("Africa/Casablanca"))
    day = now.strftime("%A").lower()
    time_now = now.strftime("%H:%M")

    today = sorted(schedule.get(day, []), key=lambda x: x["start"])

    current = None
    next_lesson = None

    for l in today:
        if l["start"] <= time_now <= l["end"]:
            current = l

        if l["start"] > time_now and next_lesson is None:
            next_lesson = l

    return current, next_lesson

# ===================== اختيار المجموعة =====================

async def ask_group(update, context):

    keyboard = [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["10", "11", "12"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🔢 أدخل رقم مجموعتك (1 → 12):",
        reply_markup=reply_markup
    )

# ===================== القائمة الرئيسية =====================

async def show_main_menu(update, context):

    keyboard = [
        ["جدول الغد", "جدول اليوم"],
        ["الدرس التالي", "الدرس الحالي"],
        ["قائمة الأساتذة", "جدول يوم معين"],
        ["تغيير المجموعة"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"📌 أنت في المجموعة: {context.user_data['group']}\nاختر ما تريد:",
        reply_markup=reply_markup
    )

# ===================== start =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_group(update, context)

# ===================== المعالجة =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await save_user_data(update, context)

    text = update.message.text

    # اختيار المجموعة أولاً
    if "group" not in context.user_data:

        if text in [str(i) for i in range(1, 13)]:
            context.user_data["group"] = text

            await update.message.reply_text(
                f"✅ تم اختيار المجموعة {text}"
            )

            return await show_main_menu(update, context)

        await ask_group(update, context)
        return

    group = context.user_data["group"]

    if text == "تغيير المجموعة":
        context.user_data.pop("group", None)
        await ask_group(update, context)
        return

    schedule = load_schedule(group)

    if schedule is None:
        await update.message.reply_text(
            "❌ لا يوجد جدول لهذه المجموعة بعد"
        )
        return

    # الحالي
    if text == "الدرس الحالي":

        current, _ = get_current_and_next_today(schedule)

        if current:
            msg = "📚 أنت الآن في هذه الحصة:\n" + format_lessons([current])
        else:
            msg = "⏳ لا توجد حصة الآن"

        await update.message.reply_text(msg)
        return

    # التالي
    if text == "الدرس التالي":

        _, next_lesson = get_current_and_next_today(schedule)

        if next_lesson:
            msg = "➡ الحصة التالية اليوم:\n" + format_lessons([next_lesson])
        else:
            msg = "✅ لا توجد حصة تالية اليوم"

        await update.message.reply_text(msg)
        return

    # اليوم
    if text == "جدول اليوم":

        day = get_day_name(0)
        lessons = schedule.get(day, [])

        ar_day = AR_DAYS.get(day, day)

        msg = f"📅 جدول اليوم {ar_day}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return

    # الغد
    if text == "جدول الغد":

        day = get_day_name(1)

        if day in WEEKEND_DAYS:
            ar = WEEKEND_DAYS[day]
            msg = f"📆 الغد {ar}\n\n💤 يوم راحة"
            await update.message.reply_text(msg)
            return

        lessons = schedule.get(day, [])
        ar_day = AR_DAYS.get(day, day)

        msg = f"📆 جدول الغد {ar_day}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return

    # يوم معيّن
    if text == "جدول يوم معين":

        await update.message.reply_text(
            "اكتب اسم اليوم بالعربية:\n\nالأحد\nالاثنين\nالثلاثاء\nالأربعاء\nالخميس"
        )
        return

    if text in REVERSE_DAYS:

        eng_day = REVERSE_DAYS[text]
        lessons = schedule.get(eng_day, [])

        msg = f"📅 جدول يوم {text}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return

    await update.message.reply_text("من فضلك استعمل الأزرار 👇")

# ===================== تشغيل =====================

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Starting webhook on port", PORT)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
