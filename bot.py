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

# --- Fonctions du bot ---
async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    if user_id not in user_stats:
        user_stats[user_id] = {"777":0, "other":0, "total":0, "name": username}

    # Détection victoire
    if "777" in text:
        win_type = "777"
        user_stats[user_id]["777"] += 1
        global_stats["777"] += 1
    else:
        win_type = "other"
        user_stats[user_id]["other"] += 1
        global_stats["other"] += 1

    user_stats[user_id]["total"] += 1
    global_stats["total"] += 1

    await update.message.reply_text(f"Spin reçu ! Type de victoire : {win_type}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"📊 Statistiques globales :\n"
        f"777 : {global_stats['777']}\n"
        f"Autres victoires : {global_stats['other']}\n"
        f"Total : {global_stats['total']}"
    )
    await update.message.reply_text(msg)

async def top777(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = sorted(user_stats.values(), key=lambda x: x["777"], reverse=True)
    msg = "🏆 Classement 777 :\n"
    for i, u in enumerate(ranking[:10], start=1):
        msg += f"{i}. {u['name']}: {u['777']}\n"
    await update.message.reply_text(msg)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = sorted(user_stats.values(), key=lambda x: x["total"], reverse=True)
    msg = "🏅 Classement total :\n"
    for i, u in enumerate(ranking[:10], start=1):
        msg += f"{i}. {u['name']}: {u['total']}\n"
    await update.message.reply_text(msg)

# --- Création du bot Telegram ---
app_telegram = ApplicationBuilder().token(TOKEN).build()
app_telegram.add_handler(MessageHandler(filters.ALL, handle_dice))
app_telegram.add_handler(CommandHandler("stats", stats))
app_telegram.add_handler(CommandHandler("top777", top777))
app_telegram.add_handler(CommandHandler("top", top))

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