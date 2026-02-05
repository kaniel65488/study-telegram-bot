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

    # جلب صورة البروفايل إن وُجدت
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

# ===================== تحميل الملفات =====================

def load_schedule():
    with open("schedule.json", encoding="utf-8") as f:
        return json.load(f)

def load_teachers():
    with open("teachers.json", encoding="utf-8") as f:
        return json.load(f)

# ===================== مساعدات الوقت =====================

def get_day_name(offset=0):
    now = datetime.now(pytz.timezone("Africa/Casablanca"))
    target = now + timedelta(days=offset)
    return target.strftime("%A").lower()

# ===================== تحويل الأيام =====================

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

# ===================== ترتيب المواد =====================

MODULE_ORDER = [
"Electronique fondamentale","Structure machine 2",
"Analyse 2","Algèbre 2",
"Introduction à l'intelligence artificielle",
"Logique mathématique","Algorithmique et structure de données 2"
]

# ===================== تنسيق الحصص =====================

def format_lessons(lessons):
    if not lessons:
        return "✅ لا توجد حصص في هذا اليوم."

    lessons = sorted(lessons, key=lambda x: x["start"])

    text = ""
    for l in lessons:
        text += f"""
\u200F📚  {l['module']}
\u200F🎯  {l.get('type','')}
\u200F⏰ من {l['start']} إلى {l['end']}
\u200F🏫  {l['room']}
\u200F━━━━━━━━━━━━━━━━
"""
    return text

# ===================== الدرس الحالي والتالي داخل نفس اليوم =====================

def get_current_and_next_today():
    schedule = load_schedule()

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


# ===================== أساتذة حسب النوع =====================

def get_teachers_by(module, lesson_type):
    teachers = load_teachers()

    key = "محاضر" if lesson_type == "محاضرة" else lesson_type

    result = []

    for t in teachers:
        if t.get("module") == module and key in t.get("type", ""):
            result.append(t)

    return result

# ===================== الواجهة الرئيسية =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["جدول الغد", "جدول اليوم"],
        ["الدرس التالي", "الدرس الحالي"],
        ["قائمة الأساتذة", "جدول يوم معين"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "السلام عليكم ورحمة الله تعالى وبركاته.\n اختر ما تُريد :",
        reply_markup=reply_markup
    )

# ===================== لوحة المقاييس =====================

def build_module_keyboard():
    buttons = []
    row = []

    for i, module in enumerate(MODULE_ORDER):
        row.append(module)

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(["رجوع"])

    return buttons


# ===================== معالجة الرسائل =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await save_user_data(update, context)

    text = update.message.text
    schedule = load_schedule()

    # ===== رجوع =====
    if text == "رجوع":

        stage = context.user_data.get("teacher_stage")

        if stage == "choose_type":

            keyboard = build_module_keyboard()

            context.user_data["teacher_stage"] = "choose_module"

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "اختر المقياس:",
                reply_markup=reply_markup
            )
            return

        await start(update, context)
        return


    # ===== الدرس الحالي =====
    if text == "الدرس الحالي":

        current, _ = get_current_and_next_today()

        if current:
            msg = "📚 أنت الآن في هذه الحصة:\n"
            msg += format_lessons([current])
        else:
            msg = "⏳ لا توجد حصة الآن"

        await update.message.reply_text(msg)
        return


    # ===== الدرس التالي =====
    if text == "الدرس التالي":

        _, next_lesson = get_current_and_next_today()

        if next_lesson:
            msg = "➡ الحصة التالية اليوم:\n"
            msg += format_lessons([next_lesson])
        else:
            msg = "✅ لا توجد حصة تالية اليوم"

        await update.message.reply_text(msg)
        return


    # ===== جدول اليوم =====
    if text == "جدول اليوم":

        day = get_day_name(0)
        lessons = schedule.get(day, [])

        ar_day = AR_DAYS.get(day, day)

        msg = f"📅 جدول اليوم {ar_day}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return


    # ===== جدول الغد =====
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


    # ===== يوم معين =====
    if text == "جدول يوم معين":

        await update.message.reply_text(
            "اكتب اسم اليوم بالعربية:\n\nالأحد\nالاثنين\nالثلاثاء\nالأربعاء\nالخميس"
        )
        return


    # ===== تحقق من اليوم =====
    if text in REVERSE_DAYS:

        eng_day = REVERSE_DAYS[text]
        lessons = schedule.get(eng_day, [])

        msg = f"📅 جدول يوم {text}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return


    if any(word in text for word in ["أحد","اثنين","ثلاثاء","أربعاء","خميس"]):

        await update.message.reply_text(
            "❌ خطأ في كتابة اليوم\n\n"
            "الصيغ الصحيحة هي:\n"
            "الأحد\nالاثنين\nالثلاثاء\nالأربعاء\nالخميس"
        )
        return


    # ===== الأساتذة =====
    if text == "قائمة الأساتذة":

        keyboard = build_module_keyboard()

        context.user_data["teacher_stage"] = "choose_module"

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "اختر المقياس:",
            reply_markup=reply_markup
        )
        return


    # ===== اختيار مقياس =====
    if text in MODULE_ORDER:

        keyboard = [
            ["TD", "محاضرة"],
            ["رجوع"]
        ]

        context.user_data["chosen_module"] = text
        context.user_data["teacher_stage"] = "choose_type"

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"اختر نوع الحصة لمقياس:\n{text}",
            reply_markup=reply_markup
        )
        return


    # ===== عرض الأساتذة =====
    if text in ["TD", "محاضرة"]:

        module = context.user_data.get("chosen_module")

        teachers = get_teachers_by(module, text)

        msg = f"{module} - {text}\n\n"

        if not teachers:
            msg += "لا يوجد حالياً, سيتم إضافته عمّا قريب بإذن الله تعالى."
        else:
            for t in teachers:

                email = t.get("email")

                if not email or email.strip() == "":
                    email = "سيتم إضافته عمّا قريب..."

                msg += f"""
👤 {t['name']}
📧 {email}
"""

        await update.message.reply_text(msg)
        return


    await update.message.reply_text("من فضلك استعمل الأزرار 👇")


# ===================== تشغيل Webhook =====================

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
