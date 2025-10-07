import os
import asyncio
from pyrogram import Client, filters
from pymongo import MongoClient

# ------------------------
# Environment Variables
# ------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]

MONGO_URI = os.getenv("MONGO_URI")  # ex: "mongodb://localhost:27017/"
DB_NAME = "forwarder_bot"

# ------------------------
# MongoDB Setup
# ------------------------
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
collection = db["message_map"]

# ------------------------
# Pyrogram Client
# ------------------------
app = Client("forwarder_bot",
             api_id=API_ID,
             api_hash=API_HASH,
             bot_token=BOT_TOKEN)

# ------------------------
# DB Helpers
# ------------------------
def save_mapping(source_id, channel_id, target_id):
    collection.update_one(
        {"source_id": source_id, "channel_id": channel_id},
        {"$set": {"target_id": target_id}},
        upsert=True
    )

def get_mappings(source_id):
    return list(collection.find({"source_id": source_id}, {"channel_id": 1, "target_id": 1, "_id": 0}))

# ------------------------
# Sync Old Messages (prepopulate DB)
# ------------------------
async def sync_old_messages():
    print("🔄 Syncing old messages for edit tracking...")
    async for message in app.iter_history(SOURCE_CHANNEL):
        text = message.text or message.caption
        if not text:
            continue

        # Check if mapping exists for all target channels
        for channel in TARGET_CHANNELS:
            exists = collection.find_one({"source_id": message.id, "channel_id": channel})
            if not exists:
                # Try to find message in target channel with same content
                # We'll fetch last 500 messages from target channel and match text
                found_target = None
                async for target_msg in app.iter_history(channel, limit=500):
                    if (target_msg.text or target_msg.caption) == text:
                        found_target = target_msg
                        break
                if found_target:
                    save_mapping(message.id, channel, found_target.id)
                    print(f"✅ Mapping added for old msg {message.id} -> {channel}:{found_target.id}")

# ------------------------
# Handle New Messages
# ------------------------
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def copy_to_channels(client, message):
    text = message.text or message.caption
    if not text:
        return

    for channel in TARGET_CHANNELS:
        try:
            sent = await client.send_message(channel, text)
            save_mapping(message.id, channel, sent.id)
            print(f"✅ New msg {message.id} copied to {channel} as {sent.id}")
        except Exception as e:
            print(f"❌ Error sending to {channel}: {e}")

# ------------------------
# Handle Edited Messages
# ------------------------
@app.on_edited_message(filters.chat(SOURCE_CHANNEL))
async def edit_in_channels(client, message):
    text = message.text or message.caption
    if not text:
        return

    mappings = get_mappings(message.id)
    if not mappings:
        print(f"⚠️ No mappings found for {message.id}")
        return

    for mapping in mappings:
        try:
            await client.edit_message_text(mapping["channel_id"], mapping["target_id"], text)
            print(f"✏️ Edited msg {mapping['target_id']} in {mapping['channel_id']}")
        except Exception as e:
            print(f"❌ Error editing in {mapping['channel_id']}: {e}")

# ------------------------
# Main Start
# ------------------------
async def main():
    # Start Pyrogram client
    await app.start()
    # Sync old messages once at start
    await sync_old_messages()
    print("🚀 Bot started with old message edit sync ready!")
    # Idle to keep bot running
    await app.idle()

if __name__ == "__main__":
    asyncio.run(main())
