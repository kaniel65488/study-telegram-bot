from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import json
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")

# ===================== ملفات المستخدمين =====================

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

    group = context.user_data.get("group")

    users[user_id] = {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_path": photo_path,
        "group": group,
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "first_seen": users.get(user_id, {}).get(
            "first_seen",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    }

    save_users(users)

# ===================== تحميل البيانات حسب المجموعة =====================

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


WEEKEND_DAYS = {
    "friday": "الجمعة",
    "saturday": "السبت"
}

MODULE_ORDER = [
"Electronique fondamentale","Structure machine 2",
"Analyse 2","Algèbre 2",
"Introduction à l'intelligence artificielle",
"Logique mathématique","Algorithmique et structure de données 2"
]

# ===================== تنسيق العرض =====================

def format_lessons(lessons):
    if not lessons:
        return "✅ لا توجد حصص في هذا اليوم."

    lessons = sorted(lessons, key=lambda x: x["start"])

    text = ""
    for l in lessons:
        text += f"""
📚  {l['module']}
🎯  {l.get('type','')}
⏰ من {l['start']} إلى {l['end']}
🏫  {l['room']}
━━━━━━━━━━━━━━━━
"""
    return text

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
        ["قائمة الأساتذة"],
        ["تغيير المجموعة"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"📌 أنت في المجموعة: {context.user_data['group']}\nاختر ما تريد:",
        reply_markup=reply_markup
    )

# ===================== start =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    users = load_users()
    user_id = str(update.effective_user.id)

    if user_id in users and users[user_id].get("group"):
        context.user_data["group"] = users[user_id]["group"]
        return await show_main_menu(update, context)

    await ask_group(update, context)

# ===================== المعالجة الرئيسية =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await save_user_data(update, context)

    text = update.message.text

    # ===== اختيار المجموعة أول مرة =====
    if "group" not in context.user_data:

        if text in [str(i) for i in range(1, 13)]:
            context.user_data["group"] = text

            await update.message.reply_text(
                f"✅ تم اختيار المجموعة {text}"
            )

            await save_user_data(update, context)

            return await show_main_menu(update, context)

        await ask_group(update, context)
        return

    group = context.user_data["group"]

    # ===== تغيير المجموعة =====
    if text == "تغيير المجموعة":
        context.user_data.pop("group", None)
        await ask_group(update, context)
        return

    schedule = load_schedule(group)

    if schedule is None:
        await update.message.reply_text("❌ لا يوجد جدول لهذه المجموعة بعد")
        return

    # ===== جدول اليوم =====
    if text == "جدول اليوم":
        day = get_day_name(0)
        msg = "📅 جدول اليوم:\n" + format_lessons(schedule.get(day, []))
        await update.message.reply_text(msg)
        return

    # ===== جدول الغد =====
    if text == "جدول الغد":
        day = get_day_name(1)

        if day in WEEKEND_DAYS:
            await update.message.reply_text("💤 يوم راحة")
            return

        msg = "📆 جدول الغد:\n" + format_lessons(schedule.get(day, []))
        await update.message.reply_text(msg)
        return

    # ===== قائمة الأساتذة =====
    if text == "قائمة الأساتذة":

        keyboard = []
        row = []

        for module in MODULE_ORDER:
            row.append(module)

            if len(row) == 2:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        keyboard.append(["رجوع"])

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

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"اختر نوع الحصة لمقياس:\n{text}",
            reply_markup=reply_markup
        )
        return

    # ===== عرض الأساتذة =====
    if text in ["TD", "محاضرة"]:

        module = context.user_data.get("chosen_module")

        teachers = get_teachers_by(group, module, text)

        msg = f"{module} - {text}\n\n"

        if not teachers:
            msg += "لا يوجد حالياً."
        else:
            for t in teachers:
                msg += f"\n👤 {t['name']}\n📧 {t.get('email','غير متوفر')}\n"

        await update.message.reply_text(msg)
        return

    await update.message.reply_text("من فضلك استعمل الأزرار 👇")

# ===================== تشغيل البوت =====================

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
