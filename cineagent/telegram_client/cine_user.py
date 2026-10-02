import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient


load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE")
target_bot_username = os.getenv("TARGET_BOT_USERNAME")

client = TelegramClient("cineagent", api_id, api_hash)


async def main():
    if not target_bot_username:
        raise RuntimeError("TARGET_BOT_USERNAME is not set in .env")

    await client.start(phone=phone)

    try:
        bot = await client.get_entity(target_bot_username)

        async with client.conversation(bot) as conversation:
            await conversation.send_message("TEST")
            response = await conversation.get_response(timeout=30)

        sender = await response.get_sender()
        print(f"Message ID: {response.id}")
        print(f"Text/caption: {response.message!r}")
        print(f"Contains media: {response.media is not None}")
        print(f"Media type: {type(response.media).__name__ if response.media else None}")
        print(f"Buttons: {response.buttons}")
        print(f"Sender: {sender}")
        print(f"Message type: {type(response).__name__}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
