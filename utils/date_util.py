import datetime as dt
import sqlite3
import re
from typing import Dict, List, Tuple

def get_nextday(next=False):
    '''0 - понедельник 1 - вторник 2 - среда 3 - четверг 4 - пятница 5 - суббота 6 - воскресенье'''
    today = dt.datetime.today().weekday()
    return today if not next else (0 if today + 1 == 7 else today + 1)

WEEKDAY_NAMES = {
    0: 'понедельник',
    1: 'вторник',
    2: 'среда',
    3: 'четверг',
    4: 'пятница',
    5: 'суббота',
    6: 'воскресенье'
}

def preobraze():
    return WEEKDAY_NAMES[get_nextday()]

# Классы с занятиями по субботам
SATURDAY_CLASSES = {'8а', '8б', '9а', '9б', '10а', '11а'}
ALL_CLASSES = {
    '5а', '5б', '6а', '6б', '7а', '7б',
    '8а', '8б', '9а', '9б', '10а', '11а'
}

def init_schedule_db():
    """Инициализация таблицы расписания"""
    with sqlite3.connect('schedule.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                day_of_week TEXT NOT NULL,
                lesson_number INTEGER NOT NULL,
                subject TEXT NOT NULL,
                room_number TEXT,
                UNIQUE(class_name, day_of_week, lesson_number)
            )
        ''')
        conn.commit()

def parse_schedule_line(line: str) -> Tuple[int, str, str]:
    """
    Парсит строку расписания.
    
    Args:
        line (str): Строка вида "1 Английский 34/29"
        
    Returns:
        Tuple[int, str, str]: (номер урока, предмет, кабинет)
    """
    match = re.match(r'(\d+)\s+([^0-9]+?)\s*([0-9/-]+)?$', line.strip())
    if not match:
        return None
    
    lesson_num = int(match.group(1))
    subject = match.group(2).strip()
    room = match.group(3) if match.group(3) else ''
    
    return (lesson_num, subject, room)

def parse_schedule_text(text: str) -> List[Dict]:
    """
    Парсит текст расписания.
    
    Args:
        text (str): Текст расписания
        
    Returns:
        List[Dict]: Список уроков с их параметрами
    """
    lessons = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        parsed = parse_schedule_line(line)
        if parsed:
            lessons.append({
                'lesson_number': parsed[0],
                'subject': parsed[1],
                'room': parsed[2]
            })
    
    return lessons

def save_schedule(class_name: str, day: str, lessons: List[Dict]):
    """
    Сохраняет расписание в БД.
    
    Args:
        class_name (str): Название класса
        day (str): День недели
        lessons (List[Dict]): Список уроков
    """
    with sqlite3.connect('schedule.db') as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM schedule WHERE class_name = ? AND day_of_week = ?", (class_name, day))
        
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

def get_schedule(class_name: str, day: str) -> str:
    """
    Возвращает расписание для класса на указанный день.
    
    Args:
        class_name (str): Название класса
        day (str): День недели
        
    Returns:
        str: Отформатированное расписание
    """
    if day == 'суббота' and class_name not in SATURDAY_CLASSES:
        return 'У вашего класса нет занятий в субботу'
    if class_name not in ALL_CLASSES:
        return 'Неверный класс'
        
    day_formatted = day[:-1] + 'у' if day.endswith('а') else day
    with sqlite3.connect('schedule.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT lesson_number, subject, room_number
            FROM schedule
            WHERE class_name = ? AND day_of_week = ?
            ORDER BY lesson_number
        ''', (class_name, day))
        
        lessons = cursor.fetchall()
        if not lessons:
            return f'Расписание для {class_name} на {day_formatted} не найдено'
            
        result = [f"Расписание {class_name} на {day_formatted}:"]
        for lesson in lessons:
            num, subj, room = lesson
            room_str = f" (каб. {room})" if room else ""
            result.append(f"{num}. {subj}{room_str}")
            
        return '\n'.join(result)

def monday(clas): return get_schedule(clas, 'понедельник')
def tuesday(clas): return get_schedule(clas, 'вторник')
def wednesday(clas): return get_schedule(clas, 'среда')
def thursday(clas): return get_schedule(clas, 'четверг')
def friday(clas): return get_schedule(clas, 'пятница')
def saturday(clas): return get_schedule(clas, 'суббота')

