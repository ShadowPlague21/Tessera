import logging
import os
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Config
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://localhost:8000")
BOT_ID = "tg-bot-1"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Tessera! Type /generate <prompt> to create an image.")

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a prompt. Example: /generate a cat")
        return

    prompt = " ".join(context.args)
    user_id = str(update.effective_user.id)
    
    payload = {
        "frontend": "telegram",
        "bot_id": BOT_ID,
        "capability": "image",
        "user_ref": f"telegram:{user_id}",
        "params": {
            "capability": "image",
            "prompt": prompt,
            "resolution": "1024x1024"
        },
        "reply_context": {
            "chat_id": update.effective_chat.id,
            "message_id": update.message.message_id
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{SCHEDULER_URL}/api/v1/jobs", json=payload, timeout=10)
            
            if resp.status_code == 402:
                await update.message.reply_text("Quota exceeded!")
                return
            
            resp.raise_for_status()
            data = resp.json()
            
            await update.message.reply_text(
                f"Job Queued! ID: {data['job_id']}\nEst time: {data['estimated_time_seconds']}s"
            )
            
            # Start polling in background
            asyncio.create_task(poll_job(data['job_id'], update.effective_chat.id))
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("Failed to create job.")

async def poll_job(job_id: str, chat_id: int):
    # Simple polling logic
    attempts = 0
    # Create a new application instance or use global/context? 
    # For simplicity in this script, we can't easily access the bot instance to send message back 
    # without passing it. But we don't have it here easily.
    # We will just print to log for now, as this is a scaffold.
    # In production, this needs a proper notification system (webhook or persistent poller).
    pass 

def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return

    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate))
    
    application.run_polling()

if __name__ == "__main__":
    main()
