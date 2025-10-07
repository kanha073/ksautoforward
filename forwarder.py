from pyrogram import Client, filters, idle
from pymongo import MongoClient
import asyncio, os

# Environment Variables
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
source_channel = int(os.getenv("SOURCE_CHANNEL"))
target_channels = [int(ch.strip()) for ch in os.getenv("TARGET_CHANNELS").split(",")]
mongo_uri = os.getenv("MONGO_URI")

# MongoDB Setup
mongo_client = MongoClient(mongo_uri)
db = mongo_client["forwarder_db"]
collection = db["message_links"]

bot = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)


@bot.on_message(filters.chat(source_channel))
async def forward_new_message(client, message):
    """Forward new messages from source to targets"""
    try:
        existing = collection.find_one({"source_id": message.id})
        if existing:
            return  # Already handled

        for target in target_channels:
            sent = await message.copy(target)
            collection.insert_one({
                "source_id": message.id,
                "target_id": sent.id,
                "target_chat": target
            })
            print(f"✅ Forwarded new message {message.id} → {target}")
    except Exception as e:
        print(f"⚠️ Error forwarding new message: {e}")


@bot.on_edited_message(filters.chat(source_channel))
async def handle_edit(client, message):
    """Edit sync for both old and new messages"""
    try:
        linked_msgs = list(collection.find({"source_id": message.id}))

        # If old msg not tracked yet → add it (no forward)
        if not linked_msgs:
            collection.insert_one({
                "source_id": message.id,
                "target_id": None,
                "target_chat": None
            })
            print(f"📄 Old message {message.id} detected — now tracked for edits.")
            return

        # Update all linked targets
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
    """Track old messages (without forwarding them)"""
    async with bot:
        async for msg in bot.get_chat_history(source_channel, limit=0):
            if not collection.find_one({"source_id": msg.id}):
                collection.insert_one({
                    "source_id": msg.id,
                    "target_id": None,
                    "target_chat": None
                })
                print(f"🕰️ Old message added to tracking list: {msg.id}")


async def main():
    await check_old_messages()
    print("🚀 Bot is running — forwarding + syncing edits active...")
    await bot.start()
    await idle()


if __name__ == "__main__":
    asyncio.run(main())
