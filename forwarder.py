import asyncio
from pyrogram import Client, filters
from pymongo import MongoClient
import os

# 🔧 Environment Variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]
MONGO_URL = os.getenv("MONGO_URL")

# 🔹 MongoDB Setup
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["forwarder_bot"]
collection = db["message_mappings"]
sync_status = db["sync_status"]

# 🔹 Pyrogram Client
app = Client("forwarder_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🔹 MongoDB Helper Functions
def save_mapping(source_id, mapping_dict):
    collection.update_one(
        {"source_msg_id": source_id},
        {"$set": {"mappings": mapping_dict}},
        upsert=True
    )

def get_mapping(source_id):
    doc = collection.find_one({"source_msg_id": source_id})
    return doc["mappings"] if doc else None

def get_last_synced():
    doc = sync_status.find_one({"source_channel": SOURCE_CHANNEL})
    return doc["last_id"] if doc else 0

def update_last_synced(msg_id):
    sync_status.update_one(
        {"source_channel": SOURCE_CHANNEL},
        {"$set": {"last_id": msg_id}},
        upsert=True
    )

# 🔹 Initial Bulk Sync (First Target Channel Only)
async def initial_sync():
    print("🚀 Starting initial sync...")
    last_synced = get_last_synced()
    offset_id = 0
    batch_size = 50  # Telegram API safe batch

    while True:
        messages = await app.get_chat_history(SOURCE_CHANNEL, limit=batch_size, offset_id=offset_id)
        if not messages:
            break

        for msg in reversed(messages):  # oldest first
            if msg.id <= last_synced:
                continue

            text = msg.text or msg.caption
            if not text:
                continue

            try:
                sent = await app.send_message(chat_id=TARGET_CHANNELS[0], text=text)
                save_mapping(msg.id, {TARGET_CHANNELS[0]: sent.id})
                update_last_synced(msg.id)
                await asyncio.sleep(0.5)  # delay between messages
            except Exception as e:
                print(f"❌ Error sending message {msg.id}: {e}")
                await asyncio.sleep(2)

        offset_id = messages[-1].id
        await asyncio.sleep(2)  # delay between batches

    print("✅ Initial sync complete for first target channel!")

# 🔹 Live Forwarding to All Target Channels
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def forward_new_messages(client, message):
    text = message.text or message.caption
    if not text:
        return

    mapping = {}
    for channel in TARGET_CHANNELS:
        try:
            sent = await client.send_message(chat_id=channel, text=text)
            mapping[channel] = sent.id
            await asyncio.sleep(0.3)  # small delay between channels
        except Exception as e:
            print(f"❌ Error sending new message to {channel}: {e}")

    if mapping:
        save_mapping(message.id, mapping)

# 🔹 Sync Edits
@app.on_edited_message(filters.chat(SOURCE_CHANNEL))
async def edit_in_channels(client, message):
    text = message.text or message.caption
    if not text:
        return

    mapping = get_mapping(message.id)
    if not mapping:
        return

    for channel, target_id in mapping.items():
        try:
            await client.edit_message_text(chat_id=channel, message_id=target_id, text=text)
        except Exception as e:
            print(f"❌ Error editing message {message.id} in {channel}: {e}")

# 🔹 Start Bot and Initial Sync
app.start()
app.loop.run_until_complete(initial_sync())
print("🚀 Initial sync done! Live forwarding + edit sync active now...")
app.run()
