from vkbottle.bot import Message, BotLabeler
from vkbottle import Keyboard, Text
from vkbottle.dispatch.rules.base import PayloadMapRule
from datetime import datetime, timedelta
from utils.image_utils import downloadimages, upload_photo
import os
bl = BotLabeler()
bl.vbml_ignore_case = True

@bl.private_message(command="changes")
@bl.private_message(text="Изменения")
async def show_changes(message: Message):
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("⏸ Сегодня", payload={"command": "changes_now"}))
    keyboard.row()
    keyboard.add(Text("▶️ Завтра", payload={"command": "changes_tomorrow"}))
    keyboard.row()
    keyboard.add(Text("⏩ Послезавтра", payload={"command": "changes_totomorrow"}))
    await message.answer("Выберите день", keyboard=keyboard)

async def handle_changes(message: Message, days_offset: int, day_name: str):
    paths = downloadimages()
    now = datetime.now()
    target_date = (now + timedelta(days=days_offset)).strftime("%d.%m")
    count = 0
    for path in paths:
        if target_date in path:
            count += 1
            photo = await upload_photo(message.ctx_api, path)
            await message.answer(
                message=f"🔔 Изменения на {day_name}",
                attachment=f"photo{photo[0].owner_id}_{photo[0].id}"
            )
        os.remove(path)
        
    if count == 0:
        await message.answer(f'😔 Изменений на {day_name} нет!')

@bl.private_message(payload={"command": "changes_now"})
async def changes_now(message: Message):
    await handle_changes(message, 0, "сегодня")

@bl.private_message(payload={"command": "changes_tomorrow"})
async def changes_tomorrow(message: Message):
    await handle_changes(message, 1, "завтра")

@bl.private_message(payload={"command": "changes_totomorrow"})
async def changes_totomorrow(message: Message):
    await handle_changes(message, 2, "послезавтра") 