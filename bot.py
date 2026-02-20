# bot.py
import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- Token Telegram ---
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("Le TOKEN n'est pas défini dans les Environment Variables")

# --- Données du bot ---
# Structure pour compter les victoires
# Victoires par utilisateur : {user_id: {"777": 0, "other": 0, "total": 0}}
user_stats = {}

# Compteurs globaux
global_stats = {"777": 0, "other": 0, "total": 0}

# --- Fonctions du bot ---
async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Traite les messages contenant les émojis de machine à sous"""
    text = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    # Initialisation stats utilisateur si besoin
    if user_id not in user_stats:
        user_stats[user_id] = {"777": 0, "other": 0, "total": 0, "name": username}

    # Détection victoire
    if "777" in text:
        win_type = "777"
        user_stats[user_id]["777"] += 1
        global_stats["777"] += 1
    elif "🍋🍋🍋" in text:  # exemple victoire secondaire
        win_type = "other"
        user_stats[user_id]["other"] += 1
        global_stats["other"] += 1
    else:
        # Vérifier si message contient d'autres motifs "victoire"
        # Pour l'exemple, tout autre combinaison de trois émojis différents
        win_type = "other"
        user_stats[user_id]["other"] += 1
        global_stats["other"] += 1

    user_stats[user_id]["total"] += 1
    global_stats["total"] += 1

    await update.message.reply_text(f"Spin reçu! Type de victoire: {win_type}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les stats globales"""
    msg = (
        f"📊 Statistiques globales :\n"
        f"777 : {global_stats['777']}\n"
        f"Autres victoires : {global_stats['other']}\n"
        f"Total : {global_stats['total']}"
    )
    await update.message.reply_text(msg)

async def top777(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Classement par 777"""
    ranking = sorted(user_stats.values(), key=lambda x: x["777"], reverse=True)
    msg = "🏆 Classement 777 :\n"
    for i, u in enumerate(ranking[:10], start=1):
        msg += f"{i}. {u['name']}: {u['777']}\n"
    await update.message.reply_text(msg)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Classement total des victoires"""
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

# Démarrage du bot dans un thread séparé
threading.Thread(target=app_telegram.run_polling, daemon=True).start()

# --- Flask Web Service pour Render ---
flask_app = Flask("")

@flask_app.route("/")
def home():
    return "Bot Telegram actif! 🎰"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render fournit la variable PORT
    flask_app.run(host="0.0.0.0", port=port)