import loguru
from vkbottle.bot import Message, BotLabeler
from vkbottle import Keyboard, Text, KeyboardButtonColor
from utils.db import Database
from utils.keyboards import generate_mainkeyboard, generate_otherkeyboard
from config import link_vkgroup
from utils.other import isAdmin
import json
from vkbottle.dispatch.rules.base import PayloadMapRule

bl = BotLabeler()
bl.vbml_ignore_case = True

db = Database()

@bl.private_message(command="start")
@bl.private_message(text="начать")
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

@bl.private_message(text="помощь")
@bl.private_message(command="help")
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
    
@bl.private_message(text="прочее")
async def send_other(message: Message):
    is_admin = await isAdmin(message, message.from_id)
    await message.answer(
        message="Выберите опцию из меню снизу",
        keyboard=generate_otherkeyboard(is_admin)
    ) 
    
@bl.private_message(command="id")
@bl.private_message(text="Профиль")
@bl.private_message(payload={"command": "cancel_delete"})
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
        loguru.logger.error(f"Error in profile: {str(e)}")
        await message.answer("Произошла ошибка при получении профиля. Попробуйте позже.")
    finally:
        conn.close()
        
@bl.private_message(command="settings")
@bl.private_message(text="Настройки")
@bl.private_message(payload={"command": "settings"})
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
    
@bl.private_message(payload={"command": "delete_account_confirm"})
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

@bl.private_message(payload={"command": "delete_account_final"})
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
        loguru.logger.error(f"Error in delete_account: {str(e)}")
        await message.answer("Произошла ошибка при удалении аккаунта. Попробуйте позже.")
    finally:
        conn.close()
        
@bl.private_message(payload={"command": "toggle_send"})
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

@bl.private_message(payload={"command": "toggle_notify"})
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
        
@bl.private_message(PayloadMapRule({"setting": str, "current": int}))
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
        loguru.logger.error(f"Error in toggle_schedule_setting: {str(e)}")
        await message.answer("Произошла ошибка при изменении настройки. Попробуйте позже.")
    finally:
        if 'conn' in locals():
            conn.close()