from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import json
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")

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

REVERSE_DAYS = {
    "الأحد": "sunday",
    "الاثنين": "monday",
    "الثلاثاء": "tuesday",
    "الأربعاء": "wednesday",
    "الخميس": "thursday"
}

# ===================== ترتيب المواد =====================

MODULE_ORDER = [
"Algorithmique et structure de données 2",
"Structure machine 2",
"Analyse 2",
"Algèbre 2",
"Introduction à l'intelligence artificielle",
"Logique mathématique",
"Electronique fondamentale"
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

# ===================== ماذا أدرس الآن =====================

def get_now_or_next():
    schedule = load_schedule()

    now = datetime.now(pytz.timezone("Africa/Casablanca"))
    day = now.strftime("%A").lower()
    time_now = now.strftime("%H:%M")

    today = sorted(schedule.get(day, []), key=lambda x: x["start"])

    for l in today:
        if l["start"] <= time_now <= l["end"]:
            return "current", l

    for l in today:
        if l["start"] > time_now:
            return "next", l

    return "none", None

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
        ["ماذا سأدرس الآن؟"],
        ["جدول اليوم"],
        ["جدول الغد"],
        ["جدول يوم معين"],
        ["قائمة الأساتذة"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "السلام عليكم ورحمة الله تعالى وبركاته.\n اختر ما تُريد :",
        reply_markup=reply_markup
    )

# ===================== معالجة الرسائل =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    schedule = load_schedule()

    # رجوع ذكي
    if text == "رجوع":

        stage = context.user_data.get("teacher_stage")

        if stage == "choose_type":

            keyboard = [[m] for m in MODULE_ORDER]
            keyboard.append(["رجوع"])

            context.user_data["teacher_stage"] = "choose_module"

            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "اختر المقياس:",
                reply_markup=reply_markup
            )
            return

        await start(update, context)
        return

    # ماذا أدرس الآن
    if text == "ماذا سأدرس الآن؟":

        status, lesson = get_now_or_next()

        if status == "current":
            msg = "📚 أنت الآن في هذه الحصة:\n"
            msg += format_lessons([lesson])

        elif status == "next":
            msg = "⏱ لا توجد حصة الآن\n➡ الحصة القادمة:\n"
            msg += format_lessons([lesson])

        else:
            msg = "✅ انتهت حصص اليوم!"

        await update.message.reply_text(msg)
        return

    # جدول اليوم
    if text == "جدول اليوم":

        day = get_day_name(0)
        lessons = schedule.get(day, [])

        ar_day = AR_DAYS.get(day, day)

        msg = f"📅 جدول اليوم {ar_day}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return

    # جدول الغد
    if text == "جدول الغد":

        day = get_day_name(1)
        lessons = schedule.get(day, [])

        ar_day = AR_DAYS.get(day, day)

        msg = f"📆 جدول الغد {ar_day}:\n"
        msg += format_lessons(lessons)

        await update.message.reply_text(msg)
        return

    # يوم معين
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

    # قائمة الأساتذة
    if text == "قائمة الأساتذة":

        keyboard = [[m] for m in MODULE_ORDER]
        keyboard.append(["رجوع"])

        context.user_data["teacher_stage"] = "choose_module"

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "اختر المقياس:",
            reply_markup=reply_markup
        )
        return

    # اختيار مقياس
    if text in MODULE_ORDER:

        keyboard = [
            ["TD"],
            ["محاضرة"],
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

    # عرض الأساتذة
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
