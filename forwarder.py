from pyrogram import Client, filters
from pymongo import MongoClient
import os

# 🔧 ENVIRONMENT VARIABLES
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]

# 🧭 MongoDB setup
MONGO_URL = os.getenv("MONGO_URL")  # Example: "mongodb+srv://user:pass@cluster.mongodb.net/"
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["forwarder_bot"]
collection = db["message_mappings"]

# 🤖 Pyrogram Client
app = Client("forwarder_bot",
             api_id=API_ID,
             api_hash=API_HASH,
             bot_token=BOT_TOKEN)

# 🧩 Helper: Save mapping in MongoDB
def save_mapping(source_id, mapping_dict):
    collection.update_one(
        {"source_msg_id": source_id},
        {"$set": {"mappings": mapping_dict}},
        upsert=True
    )

# 🧩 Helper: Load mapping from DB
def get_mapping(source_id):
    doc = collection.find_one({"source_msg_id": source_id})
    return doc["mappings"] if doc else None

# 🧩 Helper: Delete old mappings (optional cleanup)
def delete_mapping(source_id):
    collection.delete_one({"source_msg_id": source_id})

# 📩 Copy new messages
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def copy_to_channels(client, message):
    text = message.text or message.caption
    if not text:
        return

    mapping = {}
    for channel in TARGET_CHANNELS:
        try:
            sent = await client.send_message(chat_id=channel, text=text)
            mapping[channel] = sent.id
        except Exception as e:
            print(f"❌ Error sending to {channel}: {e}")

    if mapping:
        save_mapping(message.id, mapping)

# ✏️ Sync edits
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
            print(f"❌ Error editing in {channel}: {e}")

print("🚀 Bot started with MongoDB persistent mapping + edit sync...")
app.run()
