import asyncio
from pyrogram import Client, filters, idle
from pymongo import MongoClient
import os

# ---------------------------
# Environment Variables
# ---------------------------
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

# Use numeric ID (-100xxxxxxxxx) for private channel OR @username for public
source_channel_id = os.getenv("SOURCE_CHANNEL")  # "-1001234567890" or "@channelusername"
target_channels = [int(ch.strip()) for ch in os.getenv("TARGET_CHANNELS").split(",")]
mongo_uri = os.getenv("MONGO_URI")

# ---------------------------
# MongoDB Setup
# ---------------------------
mongo_client = MongoClient(mongo_uri)
db = mongo_client["forwarder_db"]
collection = db["message_links"]

# ---------------------------
# Pyrogram Bot Setup
# ---------------------------
bot = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# ---------------------------
# Forward New Messages
# ---------------------------
@bot.on_message(filters.chat(source_channel_id))
async def forward_new_message(client, message):
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


# ---------------------------
# Edit Sync for All Messages
# ---------------------------
@bot.on_edited_message(filters.chat(source_channel_id))
async def handle_edit(client, message):
    try:
        linked_msgs = list(collection.find({"source_id": message.id}))
        if not linked_msgs:
            # Track old message if first time edited
            collection.insert_one({
                "source_id": message.id,
                "target_id": None,
                "target_chat": None
            })
            print(f"📄 Old message {message.id} detected — now tracked for edits.")
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


# ---------------------------
# Safe Old Messages Fetch
# ---------------------------
async def check_old_messages_retry(max_retries=5, wait_time=10):
    for attempt in range(max_retries):
        try:
            async for msg in bot.get_chat_history(source_channel_id, limit=0):
                if not collection.find_one({"source_id": msg.id}):
                    collection.insert_one({
                        "source_id": msg.id,
                        "target_id": None,
                        "target_chat": None
                    })
                    print(f"🕰️ Old message added: {msg.id}")
            print("📄 Old messages tracking complete.")
            return
        except Exception as e:
            print(f"⚠️ Old messages fetch failed (attempt {attempt+1}): {e}")
            await asyncio.sleep(wait_time)
    print("❌ Could not fetch old messages after multiple attempts. Retry later.")


# ---------------------------
# Start Bot
# ---------------------------
async def start_bot():
    await bot.start()
    print("🚀 Bot started successfully!")

    # Track old messages safely
    await check_old_messages_retry()

    # Keep bot running
    await idle()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
