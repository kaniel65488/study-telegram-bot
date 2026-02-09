from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import json, os
from datetime import datetime, timedelta
import pytz

TOKEN = os.getenv("TOKEN")

# ================= GOOGLE SHEET =================

def get_sheet():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json:
        return None

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(creds_json),
        ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    )

    return gspread.authorize(creds).open("study_bot_users").sheet1


async def save_user_data(update, context):

    user = update.effective_user
    group = context.user_data.get("group","")

    sheet = get_sheet()
    if not sheet:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    records = sheet.get_all_records()

    for i, row in enumerate(records, start=2):
        if str(row["telegram_id"]) == str(user.id):

            sheet.update(
                range_name=f"B{i}:G{i}",
                values=[[
                    user.username or "",
                    user.first_name or "",
                    user.last_name or "",
                    group,
                    row.get("first_seen", now),
                    now
                ]]
            )
            return

    sheet.append_row([
        user.id,
        user.username or "",
        user.first_name or "",
        user.last_name or "",
        group,
        now,
        now
    ])

# ================= DATA =================

def load_schedule(group):
    path = f"G{group}/schedule{group}.json"
    if not os.path.exists(path):
        return None

    return json.load(open(path, encoding="utf-8-sig"))


def load_teachers(group):
    data = json.load(open("teachers_all_groups.json", encoding="utf-8-sig"))
    return data.get(str(group), [])


# ================= TIME =================

def get_day(offset=0):
    now = datetime.now(pytz.timezone("Africa/Casablanca"))
    return (now + timedelta(days=offset)).strftime("%A").lower()

AR = {
 "monday":"الإثنين","tuesday":"الثلاثاء","wednesday":"الأربعاء",
 "thursday":"الخميس","friday":"الجمعة","saturday":"السبت","sunday":"الأحد"
}

# ================= UI =================

async def ask_group(update, context):
    kb = [["1","2","3"],["4","5","6"],["7","8","9"],["10","11","12"]]
    await update.message.reply_text(
        "اختر مجموعتك:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )


async def main_menu(update, context):
    kb = [["جدول اليوم","جدول الغد"],["قائمة الأساتذة"],["تغيير المجموعة"]]
    await update.message.reply_text(
        f"المجموعة: {context.user_data['group']}",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# ================= FLOW =================

MODULES = [
"Algèbre 2","Analyse 2","Structure machine 2",
"Electronique fondamentale","Logique mathématique",
"Algorithmique et structure de données 2",
"Introduction à l'intelligence artificielle"
]

def get_emails(t):
    emails = []

    for k in ["email","email1","email2","email3"]:
        if t.get(k) and t[k] != "/":
            emails.append(t[k])

    return emails


async def handle(update, context):

    await save_user_data(update, context)

    text = update.message.text

    # ----- اختيار المجموعة -----
    if "group" not in context.user_data:
        if text in [str(i) for i in range(1,13)]:
            context.user_data["group"] = text
            return await main_menu(update, context)
        return await ask_group(update, context)

    # ----- تغيير مجموعة -----
    if text == "تغيير المجموعة":
        context.user_data.pop("group", None)
        return await ask_group(update, context)

    group = context.user_data["group"]

    # ----- جدول اليوم -----
    if text == "جدول اليوم":
        sch = load_schedule(group)
        if not sch:
            return await update.message.reply_text("❌ لا يوجد جدول لهذه المجموعة")

        day = get_day(0)
        lessons = sch.get(day, [])
        return await update.message.reply_text(format_lessons(lessons))

    # ----- جدول الغد -----
    if text == "جدول الغد":
        sch = load_schedule(group)
        if not sch:
            return await update.message.reply_text("❌ لا يوجد جدول لهذه المجموعة")

        day = get_day(1)
        lessons = sch.get(day, [])
        return await update.message.reply_text(format_lessons(lessons))

    # ----- قائمة الأساتذة -----
    if text == "قائمة الأساتذة":
        context.user_data["stage"] = "module"
        kb = [[m] for m in MODULES] + [["رجوع"]]
        return await update.message.reply_text(
            "اختر المادة:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

    # ----- اختيار المادة -----
    if context.user_data.get("stage") == "module":

        context.user_data["module"] = text
        context.user_data["stage"] = "type"

        if text == "Algorithmique et structure de données 2":
            kb = [["TD","TP"],["محاضرة"],["رجوع"]]

        elif text == "Introduction à l'intelligence artificielle":
            kb = [["TP"],["محاضرة"],["رجوع"]]

        else:
            kb = [["TD"],["محاضرة"],["رجوع"]]

        return await update.message.reply_text(
            "نوع الحصة:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

    # ----- اختيار النوع -----
    if context.user_data.get("stage") == "type":

        module = context.user_data["module"]
        teachers = load_teachers(group)

        msg = f"{module} - {text}\n\n"

        for t in teachers:
            if t["module"].lower().startswith(module.lower()):

                if text == "TD" and "TD" in t["type"]:

                    emails = get_emails(t)
                    email_text = "\n".join(emails) if emails else "غير متوفر"

                    msg += f"👤 {t['name']}\n📧 {email_text}\n\n"


                if text == "TP" and "TP" in t["type"]:

                    emails = get_emails(t)
                    email_text = "\n".join(emails) if emails else "غير متوفر"

                    msg += f"👤 {t['name']}\n📧 {email_text}\n\n"


                if text == "محاضرة" and "محاضر" in t["type"]:

                    emails = get_emails(t)
                    email_text = "\n".join(emails) if emails else "غير متوفر"

                    msg += f"👤 {t['name']}\n📧 {email_text}\n\n"


        context.user_data.pop("stage", None)

        return await update.message.reply_text(msg or "لا يوجد")

    # أي إدخال خارج السياق
    await update.message.reply_text(
        "❌ اختيار غير صحيح، من فضلك استعمل الأزرار فقط 👇"
    )

# ================= RUN =================

def format_lessons(ls):
    if not ls:
        return "لا توجد حصص"

    txt = ""
    for l in ls:
        txt += f"""
🔹 {l['module']}
🎯 {l['type']}
⏰ {l['start']} → {l['end']}
🏫 {l['room']}
━━━━━━━━━━
"""
    return txt


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", ask_group))
    app.add_handler(MessageHandler(filters.TEXT, handle))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT",10000)),
        url_path=TOKEN,
        webhook_url=f"{os.getenv('RENDER_EXTERNAL_URL')}/{TOKEN}"
    )

if __name__=="__main__":
    main()
