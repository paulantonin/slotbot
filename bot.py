import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
# --- Base de données ---
conn = sqlite3.connect("scores.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS scores (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    spins INTEGER DEFAULT 0,
    wins_777 INTEGER DEFAULT 0,
    secondary_wins INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0
)
""")
conn.commit()

# --- Valeurs gagnantes secondaires connues ---
SECONDARY_VALUES = [1, 22, 43, 15, 30, 50]  # citron, raisin, cloche (exemples)

# --- Gestion machine ---
async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.dice and update.message.dice.emoji == "🎰":
        user = update.message.from_user
        value = update.message.dice.value

        cursor.execute("SELECT * FROM scores WHERE user_id=?", (user.id,))
        data = cursor.fetchone()

        if not data:
            cursor.execute("INSERT INTO scores (user_id, username) VALUES (?, ?)", (user.id, user.first_name))
            conn.commit()

        # Mise à jour spins
        cursor.execute("UPDATE scores SET spins = spins + 1 WHERE user_id=?", (user.id,))

        if value == 64:
            cursor.execute("""
                UPDATE scores 
                SET wins_777 = wins_777 + 1,
                    total_wins = total_wins + 1
                WHERE user_id=?
            """, (user.id,))
            await update.message.reply_text(f"🎉 JACKPOT 777 pour {user.first_name} !!!")

        elif value in SECONDARY_VALUES:
            cursor.execute("""
                UPDATE scores 
                SET secondary_wins = secondary_wins + 1,
                    total_wins = total_wins + 1
                WHERE user_id=?
            """, (user.id,))
            await update.message.reply_text(f"✨ Victoire secondaire pour {user.first_name} !")

        conn.commit()

# --- Stats personnelles ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cursor.execute("SELECT spins, wins_777, secondary_wins, total_wins FROM scores WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if not data:
        await update.message.reply_text("Aucune statistique trouvée.")
        return

    spins, w777, sec, total = data

    await update.message.reply_text(
        f"📊 Stats de {user.first_name} :\n"
        f"🎰 Tentatives : {spins}\n"
        f"🏆 777 : {w777}\n"
        f"✨ Victoires secondaires : {sec}\n"
        f"🥇 Total victoires : {total}"
    )

# --- Classement 777 ---
async def top777(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, wins_777 FROM scores ORDER BY wins_777 DESC LIMIT 10")
    results = cursor.fetchall()

    text = "🏆 Classement 777 :\n\n"
    for i, (name, score) in enumerate(results, start=1):
        text += f"{i}. {name} - {score} 🎰\n"

    await update.message.reply_text(text)

# --- Classement total ---
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, total_wins FROM scores ORDER BY total_wins DESC LIMIT 10")
    results = cursor.fetchall()

    text = "🥇 Classement total des victoires :\n\n"
    for i, (name, score) in enumerate(results, start=1):
        text += f"{i}. {name} - {score} victoires\n"

    await update.message.reply_text(text)

# --- Lancement bot ---
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, handle_dice))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("top777", top777))
app.add_handler(CommandHandler("top", top))

app.run_polling()