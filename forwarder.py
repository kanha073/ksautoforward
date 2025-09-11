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

# Source channel se target channels me copy karna (without forward tag)
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def copy_to_channels(client, message):
    for channel in TARGET_CHANNELS:
        try:
            await message.copy(chat_id=channel)  # forward ke jagah copy
        except Exception as e:
            print(f"Error sending to {channel}: {e}")

# Test command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply("✅ Bot is running! Messages will be copied (no forward tag).")

print("Bot Started...")
app.run()
