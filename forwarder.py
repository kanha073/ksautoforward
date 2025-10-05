import os
import sqlite3
from pyrogram import Client, filters, idle

# ─── ENVIRONMENT VARIABLES ────────────────────────────────
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]

# ─── DATABASE SETUP ───────────────────────────────────────
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

# ─── CLIENT ───────────────────────────────────────────────
app = Client(
    "forwarder_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ─── DATABASE FUNCTIONS ───────────────────────────────────
def save_mapping(source_id, channel_id, target_id):
    cursor.execute(
        "INSERT OR REPLACE INTO message_map (source_id, channel_id, target_id) VALUES (?, ?, ?)",
        (source_id, channel_id, target_id)
    )
    conn.commit()

def get_mappings(source_id):
    cursor.execute("SELECT channel_id, target_id FROM message_map WHERE source_id=?", (source_id,))
    return cursor.fetchall()

# ─── NEW MESSAGE HANDLER ──────────────────────────────────
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def copy_to_channels(client, message):
    text = message.text or message.caption
    if not text:  # ignore pure media for now
        return

    for channel in TARGET_CHANNELS:
        try:
            sent = await client.send_message(channel, text)
            save_mapping(message.id, channel, sent.id)
            print(f"✅ New msg {message.id} copied to {channel} as {sent.id}")
        except Exception as e:
            print(f"❌ Error sending to {channel}: {e}")

# ─── EDIT HANDLER ─────────────────────────────────────────
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

# ─── OLD MESSAGE SYNC FUNCTION ────────────────────────────
async def sync_old_messages():
    print("🔍 Starting full old message sync...")
    async for message in app.get_chat_history(SOURCE_CHANNEL):
        text = message.text or message.caption
        if not text:
            continue

        # Check if message already exists in DB
        cursor.execute("SELECT * FROM message_map WHERE source_id=?", (message.id,))
        if cursor.fetchone():
            continue  # already synced

        # Send to target channels
        for channel in TARGET_CHANNELS:
            try:
                sent = await app.send_message(channel, text)
                save_mapping(message.id, channel, sent.id)
                print(f"📦 Synced old msg {message.id} → {channel}")
            except Exception as e:
                print(f"❌ Error syncing old msg {message.id} to {channel}: {e}")

    print("✅ Old message sync complete.")

# ─── MAIN FUNCTION ────────────────────────────────────────
async def main():
    await app.start()
    print("🚀 Bot started successfully. Running old message sync...")
    await sync_old_messages()
    print("✅ Ready for live message + edit sync.")
    await idle()
    await app.stop()

# ─── RUN ──────────────────────────────────────────────────
import asyncio
asyncio.run(main())
