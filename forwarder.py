import asyncio
from pyrogram import Client, filters, idle
from pymongo import MongoClient
import os

# Environment Variables
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

# Use numeric ID (-100xxxxxxxxx) for private channel OR @username for public
source_channel_id = os.getenv("SOURCE_CHANNEL")  # "-1001234567890" or "@channelusername"

target_channels = [int(ch.strip()) for ch in os.getenv("TARGET_CHANNELS").split(",")]
mongo_uri = os.getenv("MONGO_URI")

# MongoDB Setup
mongo_client = MongoClient(mongo_uri)
db = mongo_client["forwarder_db"]
collection = db["message_links"]

bot = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)


@bot.on_message(filters.chat(source_channel_id))
async def forward_new_message(client, message):
    """Forward new messages from source to targets"""
    try:
        if collection.find_one({"source_id": message.id}):
            return
        for target in target_channels:
            sent = await message.copy(target)
            collection.insert_one({
                "source_id": message.id,
                "target_id": sent.id,
                "target_chat": target
            })
            print(f"✅ Forwarded {message.id} → {target}")
    except Exception as e:
        print(f"⚠️ Error forwarding new message: {e}")


@bot.on_edited_message(filters.chat(source_channel_id))
async def handle_edit(client, message):
    """Sync edits to target channels"""
    try:
        linked_msgs = list(collection.find({"source_id": message.id}))
        if not linked_msgs:
            collection.insert_one({
                "source_id": message.id,
                "target_id": None,
                "target_chat": None
            })
            print(f"📄 Old message {message.id} detected — now tracked.")
            return

        for link in linked_msgs:
            if not link["target_id"] or not link["target_chat"]:
                continue
            try:
                await bot.edit_message_text(
                    chat_id=link["target_chat"],
                    message_id=link["target_id"],
                    text=message.text or "",
                    entities=message.entities
                )
                print(f"✏️ Synced edit: {message.id} → {link['target_chat']}")
            except Exception as e:
                print(f"⚠️ Edit failed for {link['target_chat']}: {e}")
    except Exception as e:
        print(f"⚠️ Error handling edit: {e}")


async def check_old_messages():
    """Track old messages from source channel"""
    try:
        async for msg in bot.get_chat_history(source_channel_id, limit=0):
            if not collection.find_one({"source_id": msg.id}):
                collection.insert_one({
                    "source_id": msg.id,
                    "target_id": None,
                    "target_chat": None
                })
                print(f"🕰️ Old message added: {msg.id}")
    except Exception as e:
        print(f"⚠️ Could not fetch old messages: {e}")


async def start_bot():
    await bot.start()
    print("🚀 Bot started successfully!")

    # Track old messages first
    await check_old_messages()
    print("📄 Old messages tracking complete.")

    # Start idle to keep bot running
    await idle()


if __name__ == "__main__":
    # Heroku / Koyeb compatible asyncio loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
