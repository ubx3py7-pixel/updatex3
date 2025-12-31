import os
import sqlite3
import shutil
import subprocess
import signal
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ================= CONFIG =================
BOSS_BOT_TOKEN = "8557427092:AAHDt9lqKfJxddyJQQawa-1lt0mHmaaRjoc"
OWNER_ID = 6940098775  # your telegram numeric id
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "users")
DB_FILE = os.path.join(BASE_DIR, "users.db")

BOT_FILES = ["spbot5.py", "msg.py"]
ENV_TEMPLATE = "rename to .env"
# =========================================

os.makedirs(USERS_DIR, exist_ok=True)

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    bot_limit INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS bots (
    user_id INTEGER,
    pid INTEGER,
    status TEXT
)
""")
conn.commit()

def ensure_user(uid):
    cur.execute("SELECT bot_limit FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        limit_ = 9999 if uid == OWNER_ID else 1
        cur.execute("INSERT INTO users VALUES (?,?)", (uid, limit_))
        conn.commit()

def running_bots(uid):
    cur.execute("SELECT COUNT(*) FROM bots WHERE user_id=? AND status='running'", (uid,))
    return cur.fetchone()[0]

# ================= BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id)
    await update.message.reply_text(
        "🤖 Boss Bot Ready\n\n"
        "/addbot – Host your bot\n"
        "/stopbot – Stop bot\n"
        "/status – Bot status"
    )

async def addbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)

    cur.execute("SELECT bot_limit FROM users WHERE user_id=?", (uid,))
    limit_ = cur.fetchone()[0]

    if running_bots(uid) >= limit_:
        await update.message.reply_text("❌ Bot limit reached")
        return

    context.user_data["step"] = "token"
    await update.message.reply_text("Send BOT TOKEN:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get("step") == "token":
        context.user_data["token"] = text
        context.user_data["step"] = "chat"
        await update.message.reply_text("Send CHAT ID:")
        return

    if context.user_data.get("step") == "chat":
        token = context.user_data["token"]
        chat_id = text

        user_dir = os.path.join(USERS_DIR, f"user_{uid}")
        os.makedirs(user_dir, exist_ok=True)

        for f in BOT_FILES:
            shutil.copy(os.path.join(BASE_DIR, f), user_dir)

        with open(os.path.join(BASE_DIR, ENV_TEMPLATE)) as f:
            env = f.read()

        env = env.replace("BOT_TOKEN=", f"BOT_TOKEN={token}")
        env = env.replace("CHAT_ID=", f"CHAT_ID={chat_id}")
        env = env.replace("OWNER_TG_ID=", f"OWNER_TG_ID={OWNER_ID}")

        with open(os.path.join(user_dir, ".env"), "w") as f:
            f.write(env)

        proc = subprocess.Popen(["python3", "spbot5.py"], cwd=user_dir)

        cur.execute("INSERT INTO bots VALUES (?,?,?)", (uid, proc.pid, "running"))
        conn.commit()

        await update.message.reply_text("✅ Bot started")
        context.user_data.clear()

async def stopbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT pid FROM bots WHERE user_id=? AND status='running'", (uid,))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text("❌ No running bot")
        return

    try:
        os.kill(row[0], signal.SIGTERM)
    except:
        pass

    cur.execute("UPDATE bots SET status='stopped' WHERE user_id=?", (uid,))
    conn.commit()

    await update.message.reply_text("🛑 Bot stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT status FROM bots WHERE user_id=?", (uid,))
    row = cur.fetchone()
    await update.message.reply_text(
        f"📊 Bot status: {row[0]}" if row else "ℹ️ No bot found"
    )

async def setlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(context.args[0])
        limit_ = int(context.args[1])
        cur.execute("UPDATE users SET bot_limit=? WHERE user_id=?", (limit_, uid))
        conn.commit()
        await update.message.reply_text("✅ Limit updated")
    except:
        await update.message.reply_text("Usage: /setlimit <user_id> <limit>")

# ================= RUN =================
app = ApplicationBuilder().token(BOSS_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addbot", addbot))
app.add_handler(CommandHandler("stopbot", stopbot))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("setlimit", setlimit))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("🔥 Boss Bot Running")
app.run_polling()
