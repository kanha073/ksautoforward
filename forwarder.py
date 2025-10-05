import os
import sqlite3
from pyrogram import Client, filters

# --- Load environment variables ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]

# --- Database setup ---
conn = sqlite3.connect("messages.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS message_map (
    source_id INTEGER,
    channel_id INTEGER,
    target_id INTEGER,
    PRIMARY KEY (source_id, channel_id)
)
""")
conn.commit()

app = Client("forwarder_bot",
             api_id=API_ID,
             api_hash=API_HASH,
             bot_token=BOT_TOKEN)


# --- DB helper functions ---
def save_mapping(source_id, channel_id, target_id):
    cursor.execute(
        "INSERT OR REPLACE INTO message_map (source_id, channel_id, target_id) VALUES (?, ?, ?)",
        (source_id, channel_id, target_id)
    )
    conn.commit()

def get_mappings(source_id):
    cursor.execute("SELECT channel_id, target_id FROM message_map WHERE source_id=?", (source_id,))
    return cursor.fetchall()

def mapping_exists(source_id):
    cursor.execute("SELECT 1 FROM message_map WHERE source_id=? LIMIT 1", (source_id,))
    return cursor.fetchone() is not None


# --- Handle new messages ---
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


# --- Handle edits ---
@app.on_edited_message(filters.chat(SOURCE_CHANNEL))
async def edit_in_channels(client, message):
    text = message.text or message.caption
    if not text:
        return

    mappings = get_mappings(message.id)
    if not mappings:
        print(f"⚠️ No mappings found for {message.id}")
        return

    for channel_id, target_id in mappings:
        try:
            await client.edit_message_text(channel_id, target_id, text)
            print(f"✏️ Edited msg {target_id} in {channel_id}")
        except Exception as e:
            print(f"❌ Error editing in {channel_id}: {e}")


# --- Sync all old messages ---
async def sync_old_messages(client):
    print("🔍 Starting full old message sync... This may take time if channel is large.")

    async for msg in client.get_chat_history(SOURCE_CHANNEL, limit=None):
        if not (msg.text or msg.caption):
            continue  # ignore pure media
        if mapping_exists(msg.id):
            continue  # already copied before

        for channel in TARGET_CHANNELS:
            try:
                sent = await client.send_message(channel, msg.text or msg.caption)
                save_mapping(msg.id, channel, sent.id)
                print(f"📦 Synced old msg {msg.id} → {channel}")
            except Exception as e:
                print(f"⚠️ Failed to sync old msg {msg.id} to {channel}: {e}")

    print("✅ All old messages synced successfully.")


# --- On startup: run the old sync ---
@app.on_startup()
async def on_start(client):
    print("🚀 Bot started. Running initial sync...")
    await sync_old_messages(client)
    print("✅ Ready for real-time message and edit sync.")


print("🟢 Bot is starting with full old+new message sync...")
app.run()
