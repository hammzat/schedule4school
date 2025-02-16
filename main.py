import logging
import sys
import requests
import os
import io
import re
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from config import *
from bs4 import *
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import inspect
import traceback
from functools import wraps
from PIL import Image
from utility import *
from utils.date_util import *
from keyboards import *

import loguru
from vkbottle import ABCRule, Bot, Keyboard, LoopWrapper, Text, KeyboardButtonColor, OpenLink, BaseStateGroup
from vkbottle.bot import BotLabeler
from vkbottle.dispatch.rules.base import CommandRule, PayloadMapRule
from vkbottle.modules import json
from vkbottle.user import Message
from utils.db import Database
from utils.other import isAdmin

DEBUG = 1

def setup_logging():
    if DEBUG:
        loguru.logger.remove()
        loguru.logger.add(
            sys.stdout,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        logging.getLogger("apscheduler").setLevel(logging.DEBUG)
    else:
        loguru.logger.remove()
        loguru.logger.add(sys.stdout, level="ERROR")
        logging.getLogger("apscheduler").setLevel(logging.ERROR)

    print("Логирование настроено")

bot = Bot(token=VK_API_TOKEN)
bot.labeler.vbml_ignore_case = True
scheduler = AsyncIOScheduler(timezone='Europe/Moscow')

lw = LoopWrapper()
user_data = {}

db = Database()

class RegistrationState(BaseStateGroup):
    WAITING_CLASS = "waiting_class"

class HasUserState(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        state = await bot.state_dispenser.get(event.from_id)
        return state is not None
    
class HasBroadcastState(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        state = await bot.state_dispenser.get(event.from_id)
        return state and state.state == "waiting_message"

class NeedAdmin(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        return await isAdmin(bot, event.from_id)

@bot.on.private_message(text="Регистрация")
async def start_registration(message: Message):
    await bot.state_dispenser.set(message.from_id, RegistrationState.WAITING_CLASS)
    await message.answer(
        "Напишите ваш класс (например: 8а, 8б):"
    )

@bot.on.private_message(HasUserState(), text=["5а", "5б", "6а", "6б", "7а", "7б", "8а", "8б", "9а", "9б", "10а", "11а"])
async def handle_registration(message: Message):
    state = await bot.state_dispenser.get(message.from_id)
    if not state:
        return
        
    if state.state == RegistrationState.WAITING_CLASS.state:
        text = message.text.lower().replace('a', 'а')
        if not is_valid_class(text):
            await message.answer("Неверный формат класса. Пример: 8а, 8б")
            return
            
        try:
            user_info = await message.get_user()
            full_name = f"{user_info.first_name} {user_info.last_name}"
            vk_register_user(
                text,
                message.from_id,
                full_name
            )
            
            await bot.state_dispenser.delete(message.from_id)
            
            await message.answer(
                "Регистрация успешно завершена!",
                keyboard=generate_mainkeyboard()
            )
        except Exception as e:
            logging.error(f"Error during registration: {str(e)}")
            await message.answer("Произошла ошибка при регистрации. Попробуйте позже.")

@bot.on.private_message(command="start")
@bot.on.private_message(text="начать")
async def send_start_message(message: Message):
    cursor, conn = db.connect()
    cursor.execute("SELECT VK_id FROM users WHERE VK_id = ?", (message.from_id,))
    exists = cursor.fetchone()
    
    if not exists:
        user = await message.get_user()
        keyboard = Keyboard(inline=True)
        keyboard.add(Text("Регистрация"), color=KeyboardButtonColor.PRIMARY)
        await message.answer(
            f"Здравствуй, {user.first_name}\n"
            "Данный бот может выдать вам расписание на определённый день и класс.\n\n"
            "Для дальнейшего использования пройдите обязательную регистрацию, нажав на кнопку ниже.",
            keyboard=keyboard
        )
    else:
        await message.answer(
            f"Здравствуй!\n"
            "Данный бот может выдать вам расписание на определённый день и класс.\n"
            "Для получения помощи напишите /help",
            keyboard=generate_mainkeyboard()
        )
        
        await message.answer(
            "Напишите класс, на который нужно выдать расписание (например: 8а, 8б):\n"
            "Или же воспользуйтесь клавиатурой снизу"
        )
    conn.close()

@bot.on.private_message(text="помощь")
@bot.on.private_message(command="help")
async def send_help(message: Message):
    help_text = f"""● Команды:
/start - перезапустить бота
/changes - посмотреть изменения в расписании
/settings - настройка рассылки
/id - ваш профиль в боте
Или пользуйтесь удобной клавиатурой снизу.

● Группа Школы №4 во ВКонтакте - {link_vkgroup}"""
    await message.answer(
        message=help_text
    )
    
@bot.on.private_message(text="прочее")
async def send_other(message: Message):
    is_admin = await isAdmin(bot, message.from_id)
    await message.answer(
        message="Выберите опцию из меню снизу",
        keyboard=generate_otherkeyboard(is_admin)
    )

@bot.on.private_message(text="Моё расписание")
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

@bot.on.private_message(text=["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"])
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

@bot.on.private_message(text=["5а", "5б", "6а", "6б", "7а", "7б", "8а", "8б", "9а", "9б", "10а", "11а"])
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

BELL_SCHEDULE = [
    ("08:20", "09:00", "10"),
    ("09:10", "09:50", "20"),
    ("10:10", "10:50", "20"),
    ("11:10", "11:50", "20"),
    ("12:10", "12:50", "15"),
    ("13:05", "13:45", "10"),
    ("13:55", "14:35", "5"),
    ("14:40", "15:20", "5"),
    ("15:25", "16:05", "5")
]

@bot.on.private_message(text="Звонки")
async def show_bells(message: Message):
    bells = "Звонки:\n" + "\n".join(
        f"{i}. {start} - {end} ({break_time}м)"
        for i, (start, end, break_time) in enumerate(BELL_SCHEDULE, 1)
    )
    await message.answer(bells)

@bot.on.private_message(text="Какой сейчас урок")
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

async def send_schedule_messages(send_type: int, message_prefix: str):
    cursor, conn = None
    try:
        cursor, conn = db.connect()
        cursor.execute("SELECT VK_id FROM users")
        users = cursor.fetchall()
        
        for user in users:
            try:
                notify, class_ = checkNotifyClass(user[0], send_type)
                if notify != 1:
                    continue
                    
                t = get_nextday(1 if send_type == 1 else 0)
                if t > 5 or (t == 5 and not has_saturday_classes(class_)):
                    continue
                    
                schedule_funcs = [monday, tuesday, wednesday, thursday, friday, saturday]
                msg = schedule_funcs[t](class_) if t < len(schedule_funcs) else ''
                
                if msg:
                    await bot.api.messages.send(
                        peer_id=user[0],
                        message=f'🔔 {message_prefix}:\n{msg}',
                        random_id=0
                    )
                    
            except Exception as e:
                logging.error(f"Error sending schedule to user {user[0]}: {str(e)}")
                continue
                
    except Exception as e:
        logging.error(f"Error in send_schedule_messages: {str(e)}")
    finally:
        if conn:
            conn.close()


lastdayrasp = ''
@lw.interval(minutes=20)
async def send_newschedule():
    """Проверяет и отправляет изменения в расписании"""
    global lastdayrasp
    paths = downloadimages()
    now = datetime.now()
    zavtra = (now + timedelta(days=1)).strftime("%d.%m")
    
    for path in paths:
        try:
            if zavtra != lastdayrasp and zavtra in path:
                cursor, conn = db.connect()
                cursor.execute("SELECT VK_id FROM users")
                users = cursor.fetchall()
                
                for user in users:
                    notify, _ = checkNotifyClass(user[0], 3)
                    if notify == 1:
                        photo = await upload_photo(path)    
                        await bot.api.messages.send(
                            peer_id=user[0],
                            message='🔔 Изменения на завтра',
                            attachment=f"photo{photo[0].owner_id}_{photo[0].id}",
                            random_id=0
                        )
                conn.close()
                lastdayrasp = zavtra
        finally:
            if os.path.exists(path):
                os.remove(path)


def schedule_jobs():
    """Инициализация и запуск планировщика задач"""
    jobs = [
        {'func': send_schedule_messages, 'args': (1, "Расписание на сегодня"), 'trigger': 'cron', 'hour': 7, 'minute': 0},
        {'func': send_schedule_messages, 'args': (2, "Расписание на завтра"), 'trigger': 'cron', 'hour': 21, 'minute': 0},
    ]
    
    for job in jobs:
        func = job.pop('func')
        args = job.pop('args', ())
        scheduler.add_job(
            func,
            job.pop('trigger'),
            args=args,
            **job,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )

def downloadimages():
    """
    Скачивает изображения с сайта школы
    """
    url = "https://shkola4-chepetsk.gosuslugi.ru/roditelyam-i-uchenikam/izmenenie-v-raspisanii/"
    base_url = "https://shkola4-chepetsk.gosuslugi.ru"
    cache_dir = os.path.join(os.getcwd(), 'files', 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        img_tags = soup.find_all("img")
        imgpaths = []
        
        now = datetime.now()
        dates = {
            'today': now.strftime("%d.%m"),
            'tomorrow': (now + timedelta(days=1)).strftime("%d.%m"),
            'day_after': (now + timedelta(days=2)).strftime("%d.%m")
        }
        
        for img_tag in img_tags:
            img_url = img_tag.get("src", "")
            if not img_url:
                continue
            img_name = img_url.split("/")[-1]
            if not re.match(r"\d{2}\.\d{2}(?:\.\d{2,4})?.png", img_name):
                continue
                
            date_part = img_name.split(".png")[0] 
            base_date = ".".join(date_part.split(".")[:2])
            loguru.logger.info(f"base_date: {base_date}")
            if not any(date == base_date for date in dates.values()):
                continue
                
            cache_path = os.path.join(cache_dir, img_name)
            if os.path.exists(cache_path) and (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))).seconds < 3600:
                imgpaths.append(cache_path)
                continue

            try:
                full_url = img_url if img_url.startswith('http') else base_url + img_url
                loguru.logger.info(f"img_url: {full_url}")
                img_response = requests.get(full_url)
                img_response.raise_for_status()
                
                with open(cache_path, "wb") as f:
                    f.write(img_response.content)
                imgpaths.append(cache_path)
                with Image.open(cache_path) as img:
                    img = img.convert('RGB')
                    img.save(cache_path, 'JPEG', quality=85, optimize=True)
                loguru.logger.info(f"img saved: {cache_path}")
            except Exception as e:
                logging.error(f"Error downloading image {img_name}: {str(e)}")
                continue
                
        return imgpaths
    except Exception as e:
        logging.error(f"Error in downloadimages: {str(e)}")
        return []

@bot.on.private_message(command="changes")
@bot.on.private_message(text="Изменения")
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
            photo = await upload_photo(path)
            await message.answer(
                message=f"🔔 Изменения на {day_name}",
                attachment=f"photo{photo[0].owner_id}_{photo[0].id}"
            )
        os.remove(path)
        
    if count == 0:
        await message.answer(f'😔 Изменений на {day_name} нет!')

@bot.on.private_message(payload={"command": "changes_now"})
async def changes_now(message: Message):
    await handle_changes(message, 0, "сегодня")

@bot.on.private_message(payload={"command": "changes_tomorrow"})
async def changes_tomorrow(message: Message):
    await handle_changes(message, 1, "завтра")

@bot.on.private_message(payload={"command": "changes_totomorrow"})
async def changes_totomorrow(message: Message):
    await handle_changes(message, 2, "послезавтра")

async def upload_photo(path: str):
    """Вспомогательная функция для загрузки фото в ВК"""
    upload_server = await bot.api.photos.get_messages_upload_server()
    with open(path, "rb") as img:
        response = requests.post(upload_server.upload_url, files={"photo": img})
    result = response.json()
    return await bot.api.photos.save_messages_photo(
        photo=result["photo"],
        server=result["server"],
        hash=result["hash"]
    )

@bot.on.private_message(command="settings")
@bot.on.private_message(text="Настройки")
@bot.on.private_message(payload={"command": "settings"})
async def settings_handler(message: Message):
    cursor, conn = db.connect()
    cursor.execute(f"SELECT send_newSchedule FROM users WHERE VK_id = {message.from_id}")
    r1 = cursor.fetchone()[0]
    cursor.execute(f"SELECT send_tomorrowSchedule FROM users WHERE VK_id = {message.from_id}")
    r2 = cursor.fetchone()[0]
    cursor.execute(f"SELECT send_todaySchedule FROM users WHERE VK_id = {message.from_id}")
    r3 = cursor.fetchone()[0]
    
    msg = f"""{'✅' if r1==1 else '❌'} Изменения в расписании:
Как только изменения появляются на сайте школы, они приходят Вам.
{'✅' if r2==1 else '❌'} Расписание на следующий день:
Приходит каждый день в 21:00
{'✅' if r3==1 else '❌'} Расписание на сегодняшний день:
Приходит каждый учебный день в 7:00"""
    
    keyboard = Keyboard(inline=True)
    keyboard.add(
        Text(
            f"{'✅' if r1==1 else '❌'} Изменения в расписании",
            payload={"setting": "newSchedule", "current": r1}
        )
    ).row()
    keyboard.add(
        Text(
            f"{'✅' if r2==1 else '❌'} Расписание на следующий день",
            payload={"setting": "tomorrowSchedule", "current": r2}
        )
    ).row()
    keyboard.add(
        Text(
            f"{'✅' if r3==1 else '❌'} Расписание на сегодняшний день",
            payload={"setting": "todaySchedule", "current": r3}
        )
    )
    
    await message.answer(msg)
    await message.answer("Выберите что включить или выключить...", keyboard=keyboard)
    conn.close()

@bot.on.private_message(PayloadMapRule({"setting": str, "current": int}))
async def toggle_schedule_setting(message: Message):
    try:
        payload = json.loads(message.payload)
        setting = payload["setting"]
        current = payload["current"]
        
        setting_map = {
            "newSchedule": "send_newSchedule",
            "tomorrowSchedule": "send_tomorrowSchedule",
            "todaySchedule": "send_todaySchedule"
        }
        
        if setting not in setting_map:
            return
            
        db_field = setting_map[setting]
        new_value = 0 if current == 1 else 1
        
        cursor, conn = db.connect()
        cursor.execute(f"UPDATE users SET {db_field} = ? WHERE VK_id = ?", (new_value, message.from_id))
        conn.commit()
        
        setting_names = {
            "newSchedule": "Уведомления об изменениях в расписании",
            "tomorrowSchedule": "Расписание на следующий день",
            "todaySchedule": "Расписание на сегодняшний день"
        }
        
        await message.answer(
            f"{setting_names[setting]} {'включены' if new_value == 1 else 'выключены'}!"
        )
        await settings_handler(message)
        
    except Exception as e:
        logging.error(f"Error in toggle_schedule_setting: {str(e)}")
        await message.answer("Произошла ошибка при изменении настройки. Попробуйте позже.")
    finally:
        if 'conn' in locals():
            conn.close()

def checkNotifyClass(iduser: int, send_type: int):
    return db.check_notify_class(iduser, send_type)

@bot.on.private_message(command="id")
@bot.on.private_message(text="Профиль")
async def profile(message: Message):
    try:
        cursor, conn = db.connect()
        
        query = """
            SELECT 
                BOT_id,
                VK_name,
                class,
                VK_sendNotify,
                VK_sendRassilka,
                send_newSchedule,
                send_tomorrowSchedule,
                send_todaySchedule
            FROM users 
            WHERE VK_id = ?
        """
        
        cursor.execute(query, (message.from_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            await message.answer("Профиль не найден. Пожалуйста, зарегистрируйтесь.")
            return
            
        notify = "✅" if user_data['VK_sendNotify'] == 1 else "❌"
        send = "✅" if user_data['VK_sendRassilka'] == 1 else "❌"
        
        msg = f"""╔ ID ВКонтакте: {message.from_id}
║ ID в боте: {user_data['BOT_id']}
║ Имя VK: {user_data['VK_name']}
║ Класс: {user_data['class']}
Подписка на рассылку: {send}
Подписка на уведомления: {notify}
"""
        
        keyboard = Keyboard(inline=True)
        keyboard.add(Text(f"{send} Рассылка", payload={"command": "toggle_send"}))
        keyboard.row()
        keyboard.add(Text(f"{notify} Уведомления", payload={"command": "toggle_notify"}))
        keyboard.row()
        keyboard.add(Text("⚙️ Настройка уведомлений", payload={"command": "settings"}))
        keyboard.row()
        keyboard.add(Text("❌ Удалить аккаунт", payload={"command": "delete_account_confirm"}), color=KeyboardButtonColor.NEGATIVE)
        
        await message.answer(msg, keyboard=keyboard)
        
    except Exception as e:
        logging.error(f"Error in profile: {str(e)}")
        await message.answer("Произошла ошибка при получении профиля. Попробуйте позже.")
    finally:
        conn.close()

@bot.on.private_message(payload={"command": "toggle_send"})
async def toggle_send(message: Message):
    try:
        cursor, conn = db.connect()
        cursor.execute(f"SELECT VK_sendRassilka FROM users WHERE VK_id = {message.from_id}")
        current = cursor.fetchone()['VK_sendRassilka']
        
        new_value = 0 if current == 1 else 1
        cursor.execute(f"UPDATE users SET VK_sendRassilka = {new_value} WHERE VK_id = {message.from_id}")
        conn.commit()
        keyboard = Keyboard(inline=True)
        keyboard.add(Text("Профиль"))
        await message.answer(f"Рассылка {'включена' if new_value == 1 else 'выключена'}!", keyboard=keyboard)
    finally:
        conn.close()

@bot.on.private_message(payload={"command": "toggle_notify"})
async def toggle_notify(message: Message):
    try:
        cursor, conn = db.connect()
        cursor.execute(f"SELECT VK_sendNotify FROM users WHERE VK_id = {message.from_id}")
        current = cursor.fetchone()['VK_sendNotify']
        
        new_value = 0 if current == 1 else 1
        cursor.execute(f"UPDATE users SET VK_sendNotify = {new_value} WHERE VK_id = {message.from_id}")
        conn.commit()
        keyboard = Keyboard(inline=True)
        keyboard.add(Text("Профиль"))
        await message.answer(f"Уведомления {'включены' if new_value == 1 else 'выключены'}!", keyboard=keyboard)
    finally:
        conn.close()

@bot.on.private_message(payload={"command": "delete_account_confirm"})
async def delete_account_confirm(message: Message):
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("❌ Да, удалить аккаунт", payload={"command": "delete_account_final"}), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("✅ Нет, оставить аккаунт", payload={"command": "cancel_delete"}), color=KeyboardButtonColor.POSITIVE)
    
    await message.answer(
        "⚠️ Вы уверены, что хотите удалить свой аккаунт?\n"
        "Это действие нельзя будет отменить, и все ваши настройки будут удалены.",
        keyboard=keyboard
    )

@bot.on.private_message(payload={"command": "delete_account_final"})
async def delete_account(message: Message):
    try:
        cursor, conn = db.connect()
        cursor.execute("DELETE FROM users WHERE VK_id = ?", (message.from_id,))
        conn.commit()
        
        keyboard = Keyboard(inline=True)
        keyboard.add(Text("Регистрация"), color=KeyboardButtonColor.PRIMARY)
        
        await message.answer(
            "✅ Ваш аккаунт успешно удален.\n"
            "Если вы захотите снова пользоваться ботом, вам нужно будет заново зарегистрироваться.",
            keyboard=keyboard
        )
    except Exception as e:
        logging.error(f"Error in delete_account: {str(e)}")
        await message.answer("Произошла ошибка при удалении аккаунта. Попробуйте позже.")
    finally:
        conn.close()

@bot.on.private_message(payload={"command": "cancel_delete"})
async def cancel_delete(message: Message):
    await profile(message)

@bot.on.private_message(command="upload_schedule")
async def upload_schedule(message: Message):
    try:
        if not message.attachments or message.attachments[0].doc is None:
            await message.answer("Пожалуйста, отправьте файл schedules.txt с расписанием")
            return
            
        doc = message.attachments[0].doc
        if doc.title != "schedules.txt":
            await message.answer("Пожалуйста, отправьте файл с названием schedules.txt")
            return
            
        response = requests.get(doc.url)
        response.encoding = 'utf-8'
        if response.status_code != 200:
            await message.answer("Не удалось скачать файл")
            return
            
        content = response.text
        logging.info(f"Получено содержимое файла, длина: {len(content)}")
        
        if not content.startswith("--start--") or not content.endswith("--end--"):
            logging.error(f"Неверные маркеры файла. Начало: {content[:20]}, Конец: {content[-20:]}")
            await message.answer("Неверный формат файла")
            return
            
        days_blocks = content.split("--day--")[1:]
        logging.info(f"Найдено блоков дней: {len(days_blocks)}")
        
        success_count = 0
        for i, block in enumerate(days_blocks, 1):
            try:
                if "--end day--" not in block:
                    continue
                    
                schedule_text = block.split("--end day--")[0].strip()
                lines = schedule_text.split('\n')
                if not lines:
                    continue
                    
                first_line = lines[0].strip().lower()
                class_name, day = first_line.split()
                
                if not is_valid_class(class_name):
                    continue
                    
                if day not in ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']:
                    continue
                    
                lessons = []
                for line in lines[1:]:
                    if not line.strip():
                        continue
                    match = re.match(r'(\d+)\.\s+(.+?)(?:\s+\((каб\.\s*)?(\d+(?:/[^/\s]+)?)\)(?:/(\w+))?)?$', line.strip())
                    if match:
                        num, subject, _, room, additional = match.groups()
                        if room and additional == "информ":
                            room = f"{room}/информ"
                        lessons.append({
                            'lesson_number': int(num),
                            'subject': subject.strip(),
                            'room': room if room else ''
                        })
                    else:
                        logging.error(f"Не удалось разобрать строку урока: '{line.strip()}'")
                
                if lessons:
                    db.save_schedule(class_name, day, lessons)
                    success_count += 1
                
            except Exception as e:
                logging.error(f"Ошибка при обработке блока {i}: {e}")
                continue
                
        if success_count > 0:
            await message.answer(f"Успешно загружено расписание для {success_count} дней")
        else:
            await message.answer("Не удалось загрузить расписание. Проверьте формат файла")
            
    except Exception as e:
        logging.error(f"Общая ошибка в upload_schedule: {str(e)}")
        await message.answer("Произошла ошибка при загрузке расписания")

@bot.on.private_message(PayloadMapRule({"command": str}))
async def handle_schedule_payload(message: Message):
    try:
        payload = json.loads(message.payload)
        command = payload["command"]
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

async def on_ready():
    schedule_jobs()
    scheduler.start()
    loguru.logger.info("Задачи запланированы...")

@bot.on.private_message(text="админ")
@bot.on.private_message(command="admin")
@bot.on.private_message(payload={"admin_command": "admin"})
async def admin_panel(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("📊 Статистика", payload={"admin_command": "stats"}))
    keyboard.row()
    keyboard.add(Text("📨 Рассылка", payload={"admin_command": "broadcast"}))
    keyboard.row()
    keyboard.add(Text("📝 Управление расписанием", payload={"admin_command": "schedule_manage"}))
    
    await message.answer(
        "🔐 Панель администратора\n"
        "Выберите действие:",
        keyboard=keyboard
    )

@bot.on.private_message(payload={"admin_command": "stats"})
async def admin_stats(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
        
    try:
        cursor, conn = db.connect()
        
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT class, COUNT(*) as count 
            FROM users 
            GROUP BY class 
            ORDER BY class
        """)
        class_stats = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                SUM(VK_sendNotify) as notify_enabled,
                SUM(VK_sendRassilka) as rassilka_enabled,
                SUM(send_newSchedule) as new_schedule_enabled,
                SUM(send_tomorrowSchedule) as tomorrow_enabled,
                SUM(send_todaySchedule) as today_enabled
            FROM users
        """)
        settings_stats = cursor.fetchone()
        
        stats_msg = f"""📊 Статистика бота:

👥 Всего пользователей: {total_users}

📚 По классам:
{chr(10).join(f"- {row['class']}: {row['count']} учеников" for row in class_stats)}

⚙️ Настройки пользователей:
- Уведомления включены: {settings_stats['notify_enabled']}
- Рассылка включена: {settings_stats['rassilka_enabled']}
- Изменения в расписании: {settings_stats['new_schedule_enabled']}
- Расписание на завтра: {settings_stats['tomorrow_enabled']}
- Расписание на сегодня: {settings_stats['today_enabled']}"""

        keyboard = Keyboard(inline=True)
        keyboard.add(Text("◀️ Назад к админ-панели", payload={"admin_command": "admin"}))
        
        await message.answer(stats_msg, keyboard=keyboard)
        
    except Exception as e:
        logging.error(f"Error in admin_stats: {str(e)}")
        await message.answer("Произошла ошибка при получении статистики")
    finally:
        conn.close()


@bot.on.private_message(payload={"admin_command": "broadcast"})
async def admin_broadcast(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    await bot.state_dispenser.set(message.from_id, "waiting_message")
    
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("❌ Отменить", payload={"admin_command": "cancel_broadcast"}))
    
    await message.answer(
        "📨 Введите сообщение для рассылки всем пользователям:\n"
        "Поддерживается разметка, можно прикрепить одно изображение.",
        keyboard=keyboard
    )

@bot.on.private_message(payload={"admin_command": "cancel_broadcast"})
async def cancel_broadcast(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    await bot.state_dispenser.delete(message.from_id)
    await admin_panel(message)

@bot.on.private_message(payload={"admin_command": "schedule_manage"})
async def admin_schedule(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("📤 Выгрузить расписание", payload={"admin_command": "export_schedule"}))
    keyboard.row()
    keyboard.add(Text("🗑 Очистить расписание", payload={"admin_command": "clear_schedule"}))
    keyboard.row()
    keyboard.add(Text("◀️ Назад к админ-панели", payload={"admin_command": "admin"}))
    
    await message.answer(
        "📝 Управление расписанием\n"
        "Выберите действие:",
        keyboard=keyboard
    )

@bot.on.private_message(HasBroadcastState())
async def handle_broadcast_message(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
        
    state = await bot.state_dispenser.get(message.from_id)
    if state and state.state == "waiting_message":
        try:
            cursor, conn = db.connect()
            cursor.execute("SELECT VK_id FROM users WHERE VK_sendRassilka = 1")
            users = cursor.fetchall()
            
            success_count = 0
            total_users = len(users)
            
            attachment = None
            if message.attachments and len(message.attachments) > 0:
                if message.attachments[0].photo:
                    photo = message.attachments[0].photo
                    largest_size = max(photo.sizes, key=lambda size: size.height * size.width)
                    photo_data = requests.get(largest_size.url).content
                    
                    upload_server = await bot.api.photos.get_messages_upload_server()
                    
                    with open('temp_photo.jpg', 'wb') as f:
                        f.write(photo_data)
                    
                    with open('temp_photo.jpg', 'rb') as f:
                        response = requests.post(upload_server.upload_url, files={'photo': f}).json()
                    
                    saved_photo = await bot.api.photos.save_messages_photo(
                        photo=response["photo"],
                        server=response["server"],
                        hash=response["hash"]
                    )
                    
                    os.remove('temp_photo.jpg')
                    
                    attachment = f"photo{saved_photo[0].owner_id}_{saved_photo[0].id}"
            
            for user in users:
                try:
                    await bot.api.messages.send(
                        peer_id=user['VK_id'],
                        message=f"📢 Сообщение от администрации:\n\n{message.text}",
                        attachment=attachment,
                        random_id=0
                    )
                    success_count += 1
                except Exception as e:
                    logging.error(f"Error sending broadcast to user {user['VK_id']}: {str(e)}")
                    continue
            
            await bot.state_dispenser.delete(message.from_id)
            
            await message.answer(
                f"✅ Рассылка завершена\n"
                f"Отправлено: {success_count} из {total_users} пользователей"
            )
            await admin_panel(message)
            
        except Exception as e:
            logging.error(f"Error in broadcast: {str(e)}")
            await message.answer("Произошла ошибка при выполнении рассылки")
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists('temp_photo.jpg'):
                os.remove('temp_photo.jpg')

@bot.on.private_message(payload={"admin_command": "clear_schedule"})
async def admin_clear_schedule(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("❌ Да, очистить", payload={"admin_command": "clear_schedule_confirm"}), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("✅ Нет, отменить", payload={"admin_command": "schedule_manage"}), color=KeyboardButtonColor.POSITIVE)
    
    await message.answer(
        "⚠️ Вы уверены, что хотите очистить всё расписание?\n"
        "Это действие нельзя будет отменить!",
        keyboard=keyboard
    )

@bot.on.private_message(payload={"admin_command": "clear_schedule_confirm"})
async def admin_clear_schedule_confirm(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    try:
        db.clear_schedule()
        
        await message.answer("✅ Расписание успешно очищено")
        await admin_schedule(message)
        
    except Exception as e:
        logging.error(f"Error in clear_schedule: {str(e)}")
        await message.answer("Произошла ошибка при очистке расписания")

@bot.on.private_message(payload={"admin_command": "export_schedule"})
async def admin_export_schedule(message: Message):
    if not await isAdmin(bot, message.from_id):
        return
    try:
        with open("schedules.txt", "w", encoding="utf-8") as f:
            f.write("--start--\n")
            
            cursor, conn = db.connect()
            cursor.execute("""
                SELECT class_name, day_of_week, lesson_number, subject, room_number
                FROM schedule
                ORDER BY class_name, day_of_week, lesson_number
            """)
            
            current_class = None
            current_day = None
            
            for row in cursor.fetchall():
                if current_class != row[0] or current_day != row[1]:
                    if current_class is not None:
                        f.write("--end day--\n")
                    f.write("--day--\n")
                    f.write(f"{row[0]} {row[1]}\n")
                    current_class = row[0]
                    current_day = row[1]
                
                room_str = f" (каб. {row[4]})" if row[4] else ""
                f.write(f"{row[2]}. {row[3]}{room_str}\n")
            
            if current_class is not None:
                f.write("--end day--\n")
            f.write("--end--")
        
        doc = await bot.api.docs.get_messages_upload_server(peer_id=message.peer_id)
        response = requests.post(doc.upload_url, files={'file': open('schedules.txt', 'rb')}).json()
        file = await bot.api.docs.save(file=response['file'], title='schedules.txt')
        os.remove('schedules.txt')
        
        await message.answer(
            "📤 Текущее расписание выгружено в файл:",
            attachment=f"doc{file.doc.owner_id}_{file.doc.id}"
        )
        
    except Exception as e:
        logging.error(f"Error in export_schedule: {str(e)}")
        await message.answer("Произошла ошибка при экспорте расписания")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    setup_logging()
    db = Database()
    loguru.logger.info("Бот запускается...")
    bot.loop_wrapper.on_startup.append(on_ready())
    bot.run_forever()