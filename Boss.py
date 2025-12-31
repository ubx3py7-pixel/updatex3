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
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
DB_FILE = os.path.join(BASE_DIR, "users.db")
# ==========================================

os.makedirs(USERS_DIR, exist_ok=True)

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    role TEXT,
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

def get_user(user_id):
    cur.execute("SELECT role, bot_limit FROM users WHERE user_id=?", (user_id,))
    return cur.fetchone()

def ensure_user(user_id):
    user = get_user(user_id)
    if not user:
        role = "owner" if user_id == OWNER_ID else "user"
        limit_ = 9999 if role == "owner" else 1
        cur.execute("INSERT INTO users VALUES (?,?,?)", (user_id, role, limit_))
        conn.commit()

def running_bots(user_id):
    cur.execute("SELECT COUNT(*) FROM bots WHERE user_id=? AND status='running'", (user_id,))
    return cur.fetchone()[0]

# ================= BOT COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)
    await update.message.reply_text(
        "🤖 Boss Bot Ready\n\n"
        "/addbot – Host your bot\n"
        "/stopbot – Stop your bot\n"
        "/status – Bot status"
    )

async def addbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    role, limit_ = get_user(user_id)
    if running_bots(user_id) >= limit_:
        await update.message.reply_text("❌ Bot limit reached")
        return

    await update.message.reply_text("Send BOT TOKEN:")
    context.user_data["step"] = "token"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    step = context.user_data.get("step")

    if step == "token":
        context.user_data["bot_token"] = text
        context.user_data["step"] = "chat"
        await update.message.reply_text("Send CHAT ID:")
        return

    if step == "chat":
        bot_token = context.user_data["bot_token"]
        chat_id = text

        user_dir = os.path.join(USERS_DIR, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)

        shutil.copy(os.path.join(TEMPLATE_DIR, "spbot5.py"), user_dir)
        shutil.copy(os.path.join(TEMPLATE_DIR, "msg.py"), user_dir)

        env_path = os.path.join(user_dir, ".env")
        with open(os.path.join(TEMPLATE_DIR, "env.template")) as f:
            env_data = f.read()

        env_data = env_data.replace("BOT_TOKEN=", f"BOT_TOKEN={bot_token}")
        env_data = env_data.replace("CHAT_ID=", f"CHAT_ID={chat_id}")
        env_data = env_data.replace("OWNER_TG_ID=", f"OWNER_TG_ID={OWNER_ID}")

        with open(env_path, "w") as f:
            f.write(env_data)

        proc = subprocess.Popen(
            ["python3", "spbot5.py"],
            cwd=user_dir
        )

        cur.execute("INSERT INTO bots VALUES (?,?,?)", (user_id, proc.pid, "running"))
        conn.commit()

        await update.message.reply_text("✅ Bot started successfully!")
        context.user_data.clear()

async def stopbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT pid FROM bots WHERE user_id=? AND status='running'", (user_id,))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text("❌ No running bot")
        return

    pid = row[0]
    try:
        os.kill(pid, signal.SIGTERM)
    except:
        pass

    cur.execute("UPDATE bots SET status='stopped' WHERE user_id=?", (user_id,))
    conn.commit()

    await update.message.reply_text("🛑 Bot stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT status FROM bots WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row:
        await update.message.reply_text(f"📊 Bot status: {row[0]}")
    else:
        await update.message.reply_text("ℹ️ No bot found")

# ================= OWNER COMMAND =================
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
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🔥 Boss Bot Running")
app.run_polling()
