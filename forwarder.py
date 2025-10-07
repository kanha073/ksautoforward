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
source_channel_id = os.getenv("SOURCE_CHANNEL")  # int or string
target_channels = [int(ch.strip()) for ch in os.getenv("TARGET_CHANNELS").split(",")]
mongo_uri = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # For /scan and /status

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
# Edit Sync
# ---------------------------
@bot.on_edited_message(filters.chat(source_channel_id))
async def handle_edit(client, message):
    try:
        linked_msgs = list(collection.find({"source_id": message.id}))
        if not linked_msgs:
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
# Delete Sync
# ---------------------------
@bot.on_deleted_messages(filters.chat(source_channel_id))
async def handle_delete(client, messages):
    for msg in messages:
        linked_msgs = list(collection.find({"source_id": msg.id}))
        for link in linked_msgs:
            if not link["target_id"] or not link["target_chat"]:
                continue
            try:
                await bot.delete_messages(chat_id=link["target_chat"], message_ids=link["target_id"])
                print(f"🗑️ Deleted synced message {msg.id} → {link['target_chat']}")
            except Exception as e:
                print(f"⚠️ Delete failed for {link['target_chat']}: {e}")

# ---------------------------
# Infinite Retry for Old Messages
# ---------------------------
async def fetch_old_messages_forever(wait_time=60):
    while True:
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
            break  # success → exit loop
        except Exception as e:
            print(f"⚠️ Old messages fetch failed: {e} — retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)

# ---------------------------
# /scan Command for Old Messages
# ---------------------------
@bot.on_message(filters.command("scan") & filters.user(ADMIN_ID))
async def scan_old_messages(client, message):
    await message.reply("🔄 Scanning all old messages, please wait...")
    count = 0
    async for msg in bot.get_chat_history(source_channel_id, limit=0):
        if not collection.find_one({"source_id": msg.id}):
            collection.insert_one({
                "source_id": msg.id,
                "target_id": None,
                "target_chat": None
            })
            count += 1
    await message.reply(f"✅ Scan complete. {count} old messages added for edit tracking.")

# ---------------------------
# /status Command for Monitoring
# ---------------------------
@bot.on_message(filters.command("status") & filters.user(ADMIN_ID))
async def status_old_messages(client, message):
    ready_count = collection.count_documents({
        "target_id": {"$ne": None},
        "target_chat": {"$ne": None}
    })
    waiting_count = collection.count_documents({
        "$or": [
            {"target_id": None},
            {"target_chat": None}
        ]
    })

    text = (
        f"📊 Old Messages Status:\n\n"
        f"✅ Ready for edit/delete: {ready_count}\n"
        f"⌛ Waiting for peer registration: {waiting_count}\n\n"
        f"ℹ️ Use /scan to force scan all old messages."
    )
    await message.reply(text)

# ---------------------------
# Start Bot
# ---------------------------
async def start_bot():
    await bot.start()
    print("🚀 Bot started successfully!")
    await fetch_old_messages_forever()  # Infinite retry until peer registered
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
