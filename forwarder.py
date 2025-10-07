import asyncio
from pyrogram import Client, filters, idle
from pymongo import MongoClient
import os

# Environment Variables
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
invite_link = os.getenv("SOURCE_INVITE")  # Use Telegram join link here
target_channels = [int(ch.strip()) for ch in os.getenv("TARGET_CHANNELS").split(",")]
mongo_uri = os.getenv("MONGO_URI")

# MongoDB Setup
mongo_client = MongoClient(mongo_uri)
db = mongo_client["forwarder_db"]
collection = db["message_links"]

bot = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)


async def setup_source_channel():
    """Join private channel using invite link and return channel ID"""
    try:
        chat = await bot.join_chat(invite_link)
        print(f"✅ Joined channel: {chat.title} (ID: {chat.id})")
        return chat.id
    except Exception as e:
        print(f"❌ Could not join channel: {e}")
        return None


@bot.on_message(filters.chat(lambda chat_id: chat_id == source_channel_id))
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


@bot.on_edited_message(filters.chat(lambda chat_id: chat_id == source_channel_id))
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
    global source_channel_id
    source_channel_id = await setup_source_channel()
    if not source_channel_id:
        print("❌ Cannot start bot without source channel access.")
        return
    await check_old_messages()
    print("🚀 Bot running — forwarding + edit sync active!")
    await idle()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
