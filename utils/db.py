import inspect
import sqlite3
import logging
from typing import Optional, Tuple, List, Dict, Any

class Database:
    def __init__(self, db_name: str = 'schedule.db'):
        self.db_name = db_name
        self.init_db()
        self.init_schedule_db()

    def init_db(self) -> None:
        """Инициализация базы данных SQLite"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    BOT_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    VK_id INTEGER UNIQUE,
                    VK_name TEXT,
                    class TEXT,
                    VK_sendNotify INTEGER DEFAULT 1,
                    VK_sendRassilka INTEGER DEFAULT 1,
                    send_newSchedule INTEGER DEFAULT 1,
                    send_tomorrowSchedule INTEGER DEFAULT 1,
                    send_todaySchedule INTEGER DEFAULT 1
                )
            ''')
            conn.commit()

    def init_schedule_db(self) -> None:
        """Инициализация таблицы расписания"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT,
                    day_of_week TEXT,
                    lesson_number INTEGER,
                    subject TEXT,
                    room_number TEXT,
                    UNIQUE(class_name, day_of_week, lesson_number)
                )
            ''')
            conn.commit()

    def connect(self) -> Tuple[sqlite3.Cursor, sqlite3.Connection]:
        """
        Подключение к базе данных SQLite.
        
        Returns:
            tuple: (cursor, connection)
        """
        try:
            caller_name = inspect.currentframe().f_back.f_code.co_name
            lg = f' call by {caller_name} ||'
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.row_factory = sqlite3.Row
            
            return cursor, conn
        except Exception as ex:
            logging.error(f'{lg} Connection refused: {str(ex)}')
            raise

    def add_user(self, vk_id: int, vk_name: str, user_class: str) -> None:
        """Добавление нового пользователя"""
        cursor, conn = self.connect()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (VK_id, VK_name, class)
                VALUES (?, ?, ?)
            ''', (vk_id, vk_name, user_class))
            conn.commit()
        finally:
            conn.close()

    def get_user(self, vk_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе"""
        cursor, conn = self.connect()
        try:
            cursor.execute('SELECT * FROM users WHERE VK_id = ?', (vk_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

    def update_user_settings(self, vk_id: int, **settings) -> None:
        """Обновление настроек пользователя"""
        cursor, conn = self.connect()
        try:
            set_clause = ', '.join([f'{key} = ?' for key in settings.keys()])
            query = f'UPDATE users SET {set_clause} WHERE VK_id = ?'
            values = tuple(settings.values()) + (vk_id,)
            cursor.execute(query, values)
            conn.commit()
        finally:
            conn.close()

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получение списка всех пользователей"""
        cursor, conn = self.connect()
        try:
            cursor.execute('SELECT * FROM users')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_user(self, vk_id: int) -> None:
        """Удаление пользователя"""
        cursor, conn = self.connect()
        try:
            cursor.execute('DELETE FROM users WHERE VK_id = ?', (vk_id,))
            conn.commit()
        finally:
            conn.close()

    def register_user(self, vk_id: int, vk_name: str, class_: str) -> None:
        """Регистрация пользователя VK"""
        cursor, conn = self.connect()
        try:
            cursor.execute('''
                INSERT INTO users 
                (VK_id, VK_name, class, VK_sendNotify, VK_sendRassilka, 
                send_newSchedule, send_tomorrowSchedule, send_todaySchedule)
                VALUES (?, ?, ?, 1, 1, 1, 1, 1)
            ''', (vk_id, vk_name, class_))
            conn.commit()
        finally:
            conn.close()

    def check_notify_class(self, vk_id: int, send_type: int) -> Tuple[int, Optional[str]]:
        """
        Проверяет настройки уведомлений пользователя.
        
        Args:
            vk_id (int): ID пользователя в VK
            send_type (int): Тип отправки (1 - сегодня, 2 - завтра, 3 - изменения)
        
        Returns:
            tuple: (notify_enabled, class_name)
        """
        notify_types = {
            1: 'send_todaySchedule',
            2: 'send_tomorrowSchedule',
            3: 'send_newSchedule'
        }
        
        try:
            cursor, conn = self.connect()
            query = f'''
                SELECT 
                    {notify_types.get(send_type, 'VK_sendNotify')} as notify,
                    class
                FROM users 
                WHERE VK_id = ?
            '''
            
            cursor.execute(query, (vk_id,))
            result = cursor.fetchone()
            
            if not result:
                logging.warning(f"User {vk_id} not found in database")
                return 0, None
                
            return result['notify'], result['class']
            
        except Exception as e:
            logging.error(f"Error in check_notify_class for user {vk_id}: {str(e)}")
            return 0, None
        finally:
            conn.close()

    def save_schedule(self, class_name: str, day: str, lessons: List[Dict]) -> None:
        """Сохранение расписания для класса на определенный день"""
        cursor, conn = self.connect()
        try:
            cursor.execute('DELETE FROM schedule WHERE class_name = ? AND day_of_week = ?',
                         (class_name, day))
            
            for lesson in lessons:
                cursor.execute('''
                    INSERT INTO schedule 
                    (class_name, day_of_week, lesson_number, subject, room_number)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    class_name,
                    day,
                    lesson['lesson_number'],
                    lesson['subject'],
                    lesson['room']
                ))
            conn.commit()
        finally:
            conn.close()

    def get_schedule(self, class_name: str, day: str) -> List[Dict[str, Any]]:
        """Получение расписания для класса на определенный день"""
        cursor, conn = self.connect()
        try:
            cursor.execute('''
                SELECT lesson_number, subject, room_number
                FROM schedule
                WHERE class_name = ? AND day_of_week = ?
                ORDER BY lesson_number
            ''', (class_name, day))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def clear_schedule(self) -> None:
        """Очистка всего расписания"""
        cursor, conn = self.connect()
        try:
            cursor.execute("DELETE FROM schedule")
            conn.commit()
        finally:
            conn.close()

    def export_schedule(self) -> List[Dict[str, Any]]:
        """Экспорт всего расписания"""
        cursor, conn = self.connect()
        try:
            cursor.execute("""
                SELECT class_name, day_of_week, lesson_number, subject, room_number
                FROM schedule
                ORDER BY class_name, day_of_week, lesson_number
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()