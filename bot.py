# bot.py
import os
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from hypercorn.asyncio import serve
from hypercorn.config import Config

# --- Token Telegram ---
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("Le TOKEN n'est pas défini dans les Environment Variables")

# --- Données du bot ---
user_stats = {}  # {user_id: {"777":0, "other":0, "total":0, "name":username}}
global_stats = {"777": 0, "other": 0, "total": 0}


# --- Base de données ---
conn = sqlite3.connect("scores.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS scores (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    spins INTEGER DEFAULT 0,
    wins_bar INTEGER DEFAULT 0,
    wins_grape INTEGER DEFAULT 0,
    wins_lemon INTEGER DEFAULT 0,
    wins_seven INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0
)
""")
conn.commit()

# --- Décodage des rouleaux (valeur 1-64) ---
SYMBOLS = ["bar", "grape", "lemon", "seven"]

def decode_slots(value: int):
    """Retourne (reel1, reel2, reel3) sous forme de strings."""
    v = value - 1
    r1 = SYMBOLS[v % 4]
    r2 = SYMBOLS[(v // 4) % 4]
    r3 = SYMBOLS[(v // 16) % 4]
    return r1, r2, r3

SYMBOL_EMOJI = {
    "bar":   "🍫 BAR",
    "grape": "🍇 Raisin",
    "lemon": "🍋 Citron",
    "seven": "7️⃣ Seven",
}

# Valeur 64 = seven/seven/seven = Jackpot
# Valeur 1  = bar/bar/bar
# Valeur 22 = grape/grape/grape
# Valeur 43 = lemon/lemon/lemon

WIN_COLUMN = {
    "bar":   "wins_bar",
    "grape": "wins_grape",
    "lemon": "wins_lemon",
    "seven": "wins_seven",
}


async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (update.message.dice and update.message.dice.emoji == "🎰"):
        return

    user = update.message.from_user
    value = update.message.dice.value
    r1, r2, r3 = decode_slots(value)

    # Créer le joueur s'il n'existe pas
    cursor.execute("SELECT user_id FROM scores WHERE user_id=?", (user.id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO scores (user_id, username) VALUES (?, ?)", (user.id, user.first_name))
        conn.commit()

    cursor.execute("UPDATE scores SET spins = spins + 1 WHERE user_id=?", (user.id,))

    # Victoire = 3 rouleaux identiques
    if r1 == r2 == r3:
        col = WIN_COLUMN[r1]
        cursor.execute(f"""
            UPDATE scores SET {col} = {col} + 1, total_wins = total_wins + 1
            WHERE user_id=?
        """, (user.id,))

        if r1 == "seven":
            await update.message.reply_text(f"🎉 JACKPOT 7️⃣7️⃣7️⃣ pour {user.first_name} !!!")
        else:
            emoji_name = SYMBOL_EMOJI[r1]
            await update.message.reply_text(f"✨ Victoire {emoji_name}{emoji_name}{emoji_name} pour {user.first_name} !")

    conn.commit()

# --- /stats : stats individuelles ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cursor.execute("""
        SELECT spins, wins_seven, wins_bar, wins_grape, wins_lemon, total_wins
        FROM scores WHERE user_id=?
    """, (user.id,))
    data = cursor.fetchone()
    if not data:
        await update.message.reply_text("Aucune statistique trouvée. Lance d'abord une 🎰 !")
        return
    spins, w7, wbar, wgrape, wlemon, total = data
    await update.message.reply_text(
        f"📊 Stats de {user.first_name} :\n"
        f"🎰 Tentatives : {spins}\n\n"
        f"7️⃣ Jackpot (777) : {w7}\n"
        f"🍫 BAR BAR BAR : {wbar}\n"
        f"🍇 Raisin x3 : {wgrape}\n"
        f"🍋 Citron x3 : {wlemon}\n\n"
        f"🏆 Total victoires : {total}"
    )

# --- /top777 : classement jackpots ---
async def top777(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, wins_seven FROM scores ORDER BY wins_seven DESC LIMIT 10")
    results = cursor.fetchall()
    if not results or all(r[1] == 0 for r in results):
        await update.message.reply_text("Pas encore de jackpot 777 !")
        return
    text = "7️⃣ Classement Jackpot 777 :\n\n"
    for i, (name, score) in enumerate(results, 1):
        text += f"{i}. {name} — {score} 🎰\n"
    await update.message.reply_text(text)

# --- /topsecondaire : classement victoires secondaires ---
async def topsecondaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("""
        SELECT username, (wins_bar + wins_grape + wins_lemon) as sec
        FROM scores ORDER BY sec DESC LIMIT 10
    """)
    results = cursor.fetchall()
    if not results or all(r[1] == 0 for r in results):
        await update.message.reply_text("Pas encore de victoires secondaires !")
        return
    text = "✨ Classement victoires secondaires :\n\n"
    for i, (name, score) in enumerate(results, 1):
        text += f"{i}. {name} — {score}\n"
    await update.message.reply_text(text)

# --- /top : classement total ---
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, total_wins FROM scores ORDER BY total_wins DESC LIMIT 10")
    results = cursor.fetchall()
    if not results or all(r[1] == 0 for r in results):
        await update.message.reply_text("Pas encore de victoires !")
        return
    text = "🥇 Classement total des victoires :\n\n"
    for i, (name, score) in enumerate(results, 1):
        text += f"{i}. {name} — {score} victoires\n"
    await update.message.reply_text(text)

# --- /groupe : stats globales du groupe ---
async def groupe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("""
        SELECT SUM(spins), SUM(wins_seven), SUM(wins_bar), SUM(wins_grape), SUM(wins_lemon), SUM(total_wins)
        FROM scores
    """)
    data = cursor.fetchone()
    if not data or data[0] is None:
        await update.message.reply_text("Aucune donnée de groupe pour l'instant !")
        return
    spins, w7, wbar, wgrape, wlemon, total = data
    await update.message.reply_text(
        f"🌍 Stats du groupe :\n"
        f"🎰 Total tentatives : {spins}\n\n"
        f"7️⃣ Jackpot (777) : {w7}\n"
        f"🍫 BAR BAR BAR : {wbar}\n"
        f"🍇 Raisin x3 : {wgrape}\n"
        f"🍋 Citron x3 : {wlemon}\n\n"
        f"🏆 Total victoires : {total}"
    )

# --- Lancement ---
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_dice))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("top777", top777))
app.add_handler(CommandHandler("topsecondaire", topsecondaire))
app.add_handler(CommandHandler("top", top))
app.add_handler(CommandHandler("groupe", groupe))
app.run_polling()

# --- Flask Web Service pour Render ---
flask_app = Flask("")

@flask_app.route("/")
def home():
    return "Bot Telegram actif! 🎰"

# --- Main async pour Render Free ---
async def main():
    await app_telegram.initialize()
    await app_telegram.start()

    port = int(os.environ.get("PORT", 10000))
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]

    # Lance Flask (Hypercorn) et Telegram simultanément
    flask_task = asyncio.create_task(serve(flask_app, config))
    await app_telegram.updater.start_polling()
    await flask_task

if __name__ == "__main__":
    asyncio.run(main())