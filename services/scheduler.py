from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import logging
import os
from utils.db import Database
from utils.date_util import monday, tuesday, wednesday, thursday, friday, saturday, get_nextday
from utils.image_utils import downloadimages, upload_photo
from utils.classes import has_saturday_classes

scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
db = Database()

async def send_schedule_messages(bot, send_type: int, message_prefix: str):
    cursor, conn = None
    try:
        cursor, conn = db.connect()
        cursor.execute("SELECT VK_id FROM users")
        users = cursor.fetchall()
        
        for user in users:
            try:
                notify, class_ = db.check_notify_class(user[0], send_type)
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
async def send_newschedule(bot):
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
                    notify, _ = db.check_notify_class(user[0], 3)
                    if notify == 1:
                        photo = await upload_photo(bot, path)    
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

def schedule_jobs(bot):
    """Инициализация и запуск планировщика задач"""
    jobs = [
        {'func': send_schedule_messages, 'args': (bot, 1, "Расписание на сегодня"), 'trigger': 'cron', 'hour': 7, 'minute': 0},
        {'func': send_schedule_messages, 'args': (bot, 2, "Расписание на завтра"), 'trigger': 'cron', 'hour': 21, 'minute': 0},
        {'func': send_newschedule, 'args': (bot,), 'trigger': 'interval', 'minutes': 20},
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