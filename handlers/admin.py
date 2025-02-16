from vkbottle.bot import Message, BotLabeler
from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle.dispatch.rules.base import PayloadMapRule
from utils.classes import is_valid_class
from utils.db import Database
from utils.other import isAdmin
from config import state_dispenser
from models.rules import NeedAdmin, HasBroadcastState
import loguru
import os
import requests
import re

db = Database()
bl = BotLabeler()
bl.vbml_ignore_case = True
@bl.private_message(text="админ")
@bl.private_message(command="admin")
@bl.private_message(PayloadMapRule({"admin_command": "admin"}))
async def admin_panel(message: Message):
    if not await isAdmin(message, message.from_id):
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

@bl.private_message(PayloadMapRule({"admin_command": "stats"}))
async def admin_stats(message: Message):
    if not await isAdmin(message, message.from_id):
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

📚 По классам:..
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
        loguru.logger.error(f"Error in admin_stats: {str(e)}")
        await message.answer("Произошла ошибка при получении статистики")
    finally:
        conn.close()

@bl.private_message(PayloadMapRule({"admin_command": "broadcast"}))
async def admin_broadcast(message: Message):
    if not await isAdmin(message, message.from_id):
        return
    await state_dispenser.set(message.from_id, "waiting_message")
    
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("❌ Отменить", payload={"admin_command": "cancel_broadcast"}))
    
    await message.answer(
        "📨 Введите сообщение для рассылки всем пользователям:\n"
        "Поддерживается разметка, можно прикрепить одно изображение.",
        keyboard=keyboard
    )

@bl.private_message(HasBroadcastState())
async def handle_broadcast_message(message: Message):
    if not await isAdmin(message, message.from_id):
        return
        
    state = await state_dispenser.get(message.from_id)
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
                    
                    upload_server = await message.ctx_api.photos.get_messages_upload_server()
                    
                    with open('temp_photo.jpg', 'wb') as f:
                        f.write(photo_data)
                    
                    with open('temp_photo.jpg', 'rb') as f:
                        response = requests.post(upload_server.upload_url, files={'photo': f}).json()
                    
                    saved_photo = await message.ctx_api.photos.save_messages_photo(
                        photo=response["photo"],
                        server=response["server"],
                        hash=response["hash"]
                    )
                    
                    os.remove('temp_photo.jpg')
                    
                    attachment = f"photo{saved_photo[0].owner_id}_{saved_photo[0].id}"
            
            for user in users:
                try:
                    await message.ctx_api.messages.send(
                        peer_id=user['VK_id'],
                        message=f"📢 Сообщение от администрации:\n\n{message.text}",
                        attachment=attachment,
                        random_id=0
                    )
                    success_count += 1
                except Exception as e:
                    loguru.logger.error(f"Error sending broadcast to user {user['VK_id']}: {str(e)}")
                    continue
            
            await state_dispenser.delete(message.from_id)
            
            await message.answer(
                f"✅ Рассылка завершена\n"
                f"Отправлено: {success_count} из {total_users} пользователей"
            )
            await admin_panel(message)
            
        except Exception as e:
            loguru.logger.error(f"Error in broadcast: {str(e)}")
            await message.answer("Произошла ошибка при выполнении рассылки")
        finally:
            if 'conn' in locals():
                conn.close()
            if os.path.exists('temp_photo.jpg'):
                os.remove('temp_photo.jpg') 

@bl.private_message(command="upload_schedule")
async def upload_schedule_txt(message: Message):
    if not await isAdmin(message, message.from_id):
        return
        
    try:
        if not message.attachments or message.attachments[0].doc is None:
            await message.answer("Пожалуйста, отправьте файл schedules.txt с расписанием")
            return
            
        doc = message.attachments[0].doc
        response = requests.get(doc.url)
        response.encoding = 'utf-8'
        if response.status_code != 200:
            await message.answer("Не удалось скачать файл")
            return
            
        content = response.text
        loguru.logger.info(f"Получено содержимое файла, длина: {len(content)}")
        
        if not content.startswith("--start--") or not content.endswith("--end--"):
            loguru.logger.error(f"Неверные маркеры файла. Начало: {content[:20]}, Конец: {content[-20:]}")
            await message.answer("Неверный формат файла")
            return
            
        days_blocks = content.split("--day--")[1:]
        loguru.logger.info(f"Найдено блоков дней: {len(days_blocks)}")
        
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
                        loguru.logger.error(f"Не удалось разобрать строку урока: '{line.strip()}'")
                
                if lessons:
                    db.save_schedule(class_name, day, lessons)
                    success_count += 1
                
            except Exception as e:
                loguru.logger.error(f"Ошибка при обработке блока {i}: {e}")
                continue
                
        if success_count > 0:
            await message.answer(f"Успешно загружено расписание для {success_count} дней")
        else:
            await message.answer("Не удалось загрузить расписание. Проверьте формат файла")
            
    except Exception as e:
        loguru.logger.error(f"Общая ошибка в upload_schedule: {str(e)}")
        await message.answer("Произошла ошибка при загрузке расписания")

@bl.private_message(PayloadMapRule({"admin_command": "cancel_broadcast"}))
async def cancel_broadcast(message: Message):
    if not await isAdmin(message, message.from_id):
        return
    await state_dispenser.delete(message.from_id)
    await admin_panel(message)

@bl.private_message(PayloadMapRule({"admin_command": "schedule_manage"}))
async def admin_schedule(message: Message):
    if not await isAdmin(message, message.from_id):
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

@bl.private_message(PayloadMapRule({"admin_command": "clear_schedule"}))
async def admin_clear_schedule(message: Message):
    if not await isAdmin(message, message.from_id):
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

@bl.private_message(PayloadMapRule({"admin_command": "clear_schedule_confirm"}))
async def admin_clear_schedule_confirm(message: Message):
    if not await isAdmin(message, message.from_id):
        return
    try:
        db.clear_schedule()
        
        await message.answer("✅ Расписание успешно очищено")
        await admin_schedule(message)
        
    except Exception as e:
        loguru.logger.error(f"Error in clear_schedule: {str(e)}")
        await message.answer("Произошла ошибка при очистке расписания")

@bl.private_message(PayloadMapRule({"admin_command": "export_schedule"}))
async def admin_export_schedule(message: Message):
    if not await isAdmin(message, message.from_id):
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
        
        doc = await message.ctx_api.docs.get_messages_upload_server(peer_id=message.peer_id)
        response = requests.post(doc.upload_url, files={'file': open('schedules.txt', 'rb')}).json()
        file = await message.ctx_api.docs.save(file=response['file'], title='schedules.txt')
        os.remove('schedules.txt')
        
        await message.answer(
            "📤 Текущее расписание выгружено в файл:",
            attachment=f"doc{file.doc.owner_id}_{file.doc.id}"
        )
        
    except Exception as e:
        loguru.logger.error(f"Error in export_schedule: {str(e)}")
        await message.answer("Произошла ошибка при экспорте расписания")
    finally:
        if 'conn' in locals():
            conn.close()