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
SEARCH_QUERY = "Person of Interest S01E01"

async def main():
    if not target_bot_username:
        raise RuntimeError("TARGET_BOT_USERNAME is not set in .env")

    await client.start(phone=phone)

    try:
        bot = await client.get_entity(target_bot_username)

        async with client.conversation(bot) as conversation:
            await conversation.send_message(SEARCH_QUERY)
            response = await conversation.get_response(timeout=30)
            print(f"\nSearch:{SEARCH_QUERY}")
            print("\nInline buttons:")
            for row_number, row in enumerate(response.buttons or [], start=1):
                for button_number, button in enumerate(row, start=1):
                    print(f"\nRow {row_number}, button {button_number}")
                    print("Text:", button.text)
                    print("Callback data:", repr(button.data))


        sender = await response.get_sender()
        print(f"Message ID: {response.id}")
        print(f"Text: {response.message!r}" if response.media is None else "Text: None")
        print(f"Caption: {response.message!r}" if response.media else "Caption: None")
        print(f"Contains media: {response.media is not None}")
        print(f"Contains document: {response.document is not None}")
        print(f"Media type: {type(response.media).__name__ if response.media else None}")
        print(f"Buttons: {response.buttons}")
        print(f"Reply markup: {response.reply_markup}")
        print(f"Sender ID: {getattr(sender, 'id', None)}")
        print(f"Sender username: {getattr(sender, 'username', None)}")
        print(f"Message type: {type(response).__name__}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
