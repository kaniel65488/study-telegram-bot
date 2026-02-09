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

# ===================== مطابقة ذكية للأسماء =====================

def clean(text):
    return text.lower()\
        .replace("é","e")\
        .replace("è","e")\
        .replace("à","a")\
        .replace("  "," ")\
        .strip()


MODULE_ALIASES = {
    "algorithmique et structure de donnees 2": "algorithmique et structure de donnees 2",
    "asd 2": "algorithmique et structure de donnees 2",

    "structure machine 2": "structure machine 2",
    "ms 2": "structure machine 2",

    "introduction à l'ia": "introduction à l'intelligence artificielle",
    "introduction a l'ia": "introduction à l'intelligence artificielle",
}


def normalize(name):
    return MODULE_ALIASES.get(clean(name), clean(name))

# ===================== تحميل البيانات =====================

def load_schedule(group):

    base = f"schedule{group}.json"

    # نقلب داخل المجلد بأي شكل كان
    folder = None

    for d in os.listdir():
        if d.lower() == f"g{group}".lower():
            folder = d
            break

    if not folder:
        print("FOLDER NOT FOUND FOR GROUP", group)
        return None

    # البحث داخل المجلد عن الملف بأي حالة أحرف
    for f in os.listdir(folder):
        if f.lower() == base.lower():
            path = os.path.join(folder, f)

            with open(path, encoding="utf-8-sig") as file:
                return json.load(file)

    print("SCHEDULE FILE NOT FOUND FOR GROUP", group)
    return None

def load_teachers(group):

    try:
        with open("teachers_all_groups.json", encoding="utf-8-sig") as f:
            all_data = json.load(f)

        return all_data.get(str(group), [])

    except Exception as e:
        print("TEACHERS LOAD ERROR:", e)
        return []





def get_teachers_by(group, module, lesson_type):

    teachers = load_teachers(group)

    if not teachers:
        return []

    module_n = normalize(module)

    result = []

    for t in teachers:

        teacher_module = normalize(t.get("module",""))

        if teacher_module != module_n:
            continue

        ttype = t.get("type","")

        # تنظيف التشكيل
        ttype_clean = (
            ttype
            .replace("ُ","")
            .replace("َ","")
            .replace("ِ","")
            .lower()
        )

        # ===== منطق الفرز =====

        if lesson_type == "TD":
            if "td" in ttype_clean:
                result.append(t)

        elif lesson_type == "TP":
            if "tp" in ttype_clean:
                result.append(t)

        elif lesson_type == "محاضرة":
            if (
                "محاضر" in ttype_clean or
                "محاضرة" in ttype_clean or
                "cours" in ttype_clean
            ):
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

# ===================== تنسيق الدروس =====================

def format_lessons(lessons):
    if not lessons:
        return "✅ لا توجد حصص في هذا اليوم."

    try:
        lessons = sorted(lessons, key=lambda x: x.get("start",""))
    except:
        pass   # إذا كاين خطأ في الوقت ما نطيحوش

    text = ""
    for l in lessons:
        text += f"""
📚  {l.get('module','')}
🎯  {l.get('type','')}
⏰ من {l.get('start','?')} إلى {l.get('end','?')}
🏫  {l.get('room','')}
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

    # نتجاهل المجموعة المحفوظة عند start
    context.user_data.pop("group", None)
    await ask_group(update, context)
    return


    await ask_group(update, context)

# ===================== المعالجة =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await save_user_data(update, context)

    text = update.message.text

    stage = context.user_data.get("stage")

   
    if text == "رجوع":

        stage = context.user_data.get("stage")

        # لو كنا داخل اختيار TD/TP/محاضرة
        if stage == "choose_type":
            context.user_data["stage"] = "choose_module"

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

        # لو كنا داخل قائمة المواد
        elif stage == "choose_module":
            context.user_data.pop("stage", None)
            return await show_main_menu(update, context)

        # افتراضياً
        return await show_main_menu(update, context)



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

    if text == "تغيير المجموعة":
        context.user_data.pop("group", None)
        await ask_group(update, context)
        return

    schedule = load_schedule(group)

    if schedule is None:
        await update.message.reply_text("❌ لا يوجد جدول لهذه المجموعة بعد")
        return

    if text == "جدول اليوم":
        day = get_day_name(0)
        msg = "📅 جدول اليوم:\n" + format_lessons(schedule.get(day, []))
        await update.message.reply_text(msg)
        return

    if text == "جدول الغد":
        day = get_day_name(1)

        if day in WEEKEND_DAYS:
            await update.message.reply_text("💤 يوم راحة")
            return

        msg = "📆 جدول الغد:\n" + format_lessons(schedule.get(day, []))
        await update.message.reply_text(msg)
        return

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
        context.user_data["stage"] = "choose_module"
        return


# 👇 هذا لازم يكون خارج الشرط الأول
    if text in MODULE_ORDER:

        context.user_data["stage"] = "choose_type"

        asd_module = "Algorithmique et structure de données 2"
        ia_module = "Introduction à l'intelligence artificielle"
    
        # ===== حالة IA: بلا TD =====
        if text == ia_module:
            keyboard = [
                ["TP"],
                ["محاضرة"],
                ["رجوع"]
            ]
    
        # ===== حالة ASD2: فيها الكل =====
        elif text == asd_module:
            keyboard = [
                ["TD", "TP"],
                ["محاضرة"],
                ["رجوع"]
            ]
    
        # ===== باقي المواد: بلا TP =====
        else:
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




    if text in ["TD", "محاضرة", "TP"]: 

        module = context.user_data.get("chosen_module")

        teachers = get_teachers_by(group, module, text)

        msg = f"{module} - {text}\n\n"

        if not teachers:
            msg += "لا يوجد حالياً."
        else:
            for t in teachers:

                emails = []

                for k in ["email","email1","email2","email3"]:
                    if t.get(k) and t[k] != "/":
                        emails.append(t[k])

                email_text = "\n".join(emails) if emails else "غير متوفر"

                msg += f"\n👤 {t['name']}\n📧 {email_text}\n"

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

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
