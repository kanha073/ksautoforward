import os
import asyncio
from pyrogram import Client, filters

# Env variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

SOURCE_CHANNEL = int(os.environ.get("SOURCE_CHANNEL", 0))  # -100 se start hoga
TARGET_CHANNELS = [int(x) for x in os.environ.get("TARGET_CHANNELS", "").split(",") if x]

# Bot client
app = Client(
    "forwarder-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ✅ Old messages sync
async def sync_old_messages():
    print("🔍 Starting full old message sync...")

    # Force resolve channel peer (Fixes Peer ID Invalid error)
    await app.get_chat(SOURCE_CHANNEL)

    async for message in app.get_chat_history(SOURCE_CHANNEL, limit=0):
        for target in TARGET_CHANNELS:
            try:
                await app.copy_message(
                    chat_id=target,
                    from_chat_id=SOURCE_CHANNEL,
                    message_id=message.id
                )
                print(f"✅ Synced old msg {message.id} -> {target}")
            except Exception as e:
                print(f"❌ Failed to forward {message.id}: {e}")

# ✅ New message forward
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def forward_new_message(client, message):
    for target in TARGET_CHANNELS:
        try:
            await message.copy(chat_id=target)
            print(f"📩 Forwarded new msg {message.id} -> {target}")
        except Exception as e:
            print(f"❌ Failed to forward new msg {message.id}: {e}")

# ✅ Bot runner
async def main():
    async with app:
        print("🚀 Bot started successfully. Running old message sync...")
        await sync_old_messages()
        print("✅ Old sync completed. Now listening for new messages...")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
