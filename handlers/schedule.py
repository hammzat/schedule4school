import json
from vkbottle.bot import Message, BotLabeler
from vkbottle import Keyboard, Text
from utils.db import Database
from utils.date_util import monday, tuesday, wednesday, thursday, friday, saturday, preobraze
from utils.classes import is_valid_class, has_saturday_classes
from utils.keyboards import class_select
from vkbottle.dispatch.rules.base import PayloadMapRule
import logging

bl = BotLabeler()
bl.vbml_ignore_case = True

db = Database()

@bl.private_message(text="Моё расписание")
async def my_schedule(message: Message):
    cursor, conn = db.connect()
    cursor.execute(f"SELECT class FROM users WHERE VK_id = {message.from_id}")
    class_ = cursor.fetchone()[0]
    
    keyboard = Keyboard(inline=True)
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    if has_saturday_classes(class_):
        days.append("Суббота")
        
    for day in days:
        keyboard.add(Text(day))
        keyboard.row()
    
    await message.answer(f"Выберите день (сегодня {preobraze()})", keyboard=keyboard)
    conn.close()

@bl.private_message(text=["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"])
async def show_schedule(message: Message):
    cursor, conn = db.connect()
    cursor.execute(f"SELECT class FROM users WHERE VK_id = {message.from_id}")
    class_ = cursor.fetchone()[0]
    
    schedule_funcs = {
        "Понедельник": monday,
        "Вторник": tuesday,
        "Среда": wednesday,
        "Четверг": thursday,
        "Пятница": friday,
        "Суббота": saturday
    }
    
    if message.text == "Суббота" and not has_saturday_classes(class_):
        await message.answer("У вашего класса нет занятий в субботу")
        return
        
    schedule = schedule_funcs[message.text](class_)
    await message.answer(schedule)
    conn.close()

@bl.private_message(text=["5а", "5б", "6а", "6б", "7а", "7б", "8а", "8б", "9а", "9б", "10а", "11а"])
async def show_class_schedule(message: Message):
    try:
        text = message.text.lower().replace('a', 'а')
        
        if not is_valid_class(text):
            await message.answer("Неверный формат класса. Пример: 8а, 8б")
            return
            
        keyboard = class_select(text)
        await message.answer("Выберите день", keyboard=keyboard)
        
    except Exception as e:
        logging.error(f"Ошибка при получении расписания: {str(e)}")
        await message.answer("Произошла ошибка при получении расписания") 
        

@bl.private_message(PayloadMapRule({"schedule": str}))
async def handle_schedule_payload(message: Message):
    try:
        payload = json.loads(message.payload)
        command = payload["schedule"]
        if not command or "_" not in command:
            return
            
        prefix, day = command.split("_")
        if len(prefix) < 2:
            return
            
        class_letter = "а" if prefix[0] == "a" else "б"
        grade = prefix[1:]
        class_name = f"{grade}{class_letter}"
        
        day_mapping = {
            "monday": "понедельник",
            "vtorn": "вторник", 
            "sreda": "среда",
            "chetverg": "четверг",
            "pyatnica": "пятница",
            "sb": "суббота"
        }
        
        if day not in day_mapping:
            return
            
        day_name = day_mapping[day]
        
        if not is_valid_class(class_name):
            await message.answer("Неверный формат класса")
            return
            
        if day == "sb" and not has_saturday_classes(class_name):
            await message.answer("У этого класса нет занятий в субботу")
            return
            
        schedule_funcs = {
            "понедельник": monday,
            "вторник": tuesday,
            "среда": wednesday,
            "четверг": thursday,
            "пятница": friday,
            "суббота": saturday
        }
        
        schedule = schedule_funcs[day_name](class_name)
        await message.answer(schedule)
        
    except Exception as e:
        logging.error(f"Ошибка при обработке payload расписания: {str(e)}")
        await message.answer("Произошла ошибка при получении расписания")