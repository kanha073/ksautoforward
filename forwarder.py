from pyrogram import Client, filters
import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]

app = Client("forwarder_bot",
             api_id=API_ID,
             api_hash=API_HASH,
             bot_token=BOT_TOKEN)

# Mapping store karne ke liye (source_msg_id -> {target_channel: target_msg_id})
message_map = {}

# Copy messages (no forward tag) + store mapping
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def copy_to_channels(client, message):
    text = message.text or message.caption
    if not text:  # agar message me text hi nahi hai to skip kar do
        return

    message_map[message.id] = {}
    for channel in TARGET_CHANNELS:
        try:
            sent = await client.send_message(chat_id=channel, text=text)
            message_map[message.id][channel] = sent.id
        except Exception as e:
            print(f"❌ Error sending to {channel}: {e}")

# Sync edits from source channel
@app.on_edited_message(filters.chat(SOURCE_CHANNEL))
async def edit_in_channels(client, message):
    text = message.text or message.caption
    if not text:
        return

    if message.id not in message_map:
        return

    for channel, target_id in message_map[message.id].items():
        try:
            await client.edit_message_text(
                chat_id=channel,
                message_id=target_id,
                text=text
            )
        except Exception as e:
            print(f"❌ Error editing in {channel}: {e}")

print("🚀 Bot Started with text edit sync...")
app.run()
