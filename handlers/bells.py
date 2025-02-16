from vkbottle.bot import Message, BotLabeler
from datetime import datetime
import requests

from utils.consts import BELL_SCHEDULE

bl = BotLabeler()
bl.vbml_ignore_case = True

@bl.private_message(text="Звонки")
async def show_bells(message: Message):
    bells = "Звонки:\n" + "\n".join(
        f"{i}. {start} - {end} ({break_time}м)"
        for i, (start, end, break_time) in enumerate(BELL_SCHEDULE, 1)
    )
    await message.answer(bells)

@bl.private_message(text="Какой сейчас урок")
async def current_lesson(message: Message):
    rq = requests.get("https://time100.ru/api.php").json()
    rq = int(rq) + 10800
    curtime = datetime.utcfromtimestamp(rq).strftime("%H:%M")
    
    def time_in_range(start, end, current):
        return start <= current <= end
    
    for i, (start, end, _) in enumerate(BELL_SCHEDULE, 1):
        if time_in_range(start, end, curtime):
            await message.answer(f"Сейчас {i} урок ({curtime})")
            return
            
    await message.answer(f"Сейчас урока нет ({curtime})") 