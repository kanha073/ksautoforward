from pyrogram import Client, filters
import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))   # -100 se start hoga
TARGET_CHANNELS = [int(x) for x in os.getenv("TARGET_CHANNELS").split(",")]

app = Client("forwarder_bot",
             api_id=API_ID,
             api_hash=API_HASH,
             bot_token=BOT_TOKEN)

@app.on_message(filters.chat(SOURCE_CHANNEL))
async def forward_to_channels(client, message):
    for channel in TARGET_CHANNELS:
        try:
            await message.forward(chat_id=channel)
        except Exception as e:
            print(f"Error sending to {channel}: {e}")

print("Bot Started...")
app.run()
