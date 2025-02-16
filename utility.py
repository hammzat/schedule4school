from vkbottle import Keyboard, Text, KeyboardButtonColor, EMPTY_KEYBOARD
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from vkbottle import Bot
from vkbottle.bot import Message
import sqlite3
import logging

from main import connect_db

WEEKDAYS = {
    'ПН': 'monday',
    'ВТ': 'vtorn',
    'СР': 'sreda',
    'ЧТ': 'chetverg',
    'ПТ': 'pyatnica',
    'СБ': 'sb'
}

CLASS_CONFIG = {
    '5': {'letters': ['а', 'б'], 'has_saturday': False},
    '6': {'letters': ['а', 'б'], 'has_saturday': False},
    '7': {'letters': ['а', 'б'], 'has_saturday': False},
    '8': {'letters': ['а', 'б'], 'has_saturday': True},
    '9': {'letters': ['а', 'б'], 'has_saturday': True},
    '10': {'letters': ['а'], 'has_saturday': True},
    '11': {'letters': ['а'], 'has_saturday': True}
}

def get_nextday(add_days: int = 0) -> int:
    """
    Определяет следующий учебный день с учетом смещения.
    
    Args:
        add_days (int): Количество дней для смещения вперед (0 - сегодня, 1 - завтра и т.д.)
        
    Returns:
        int: Номер дня недели (0 - понедельник, 6 - воскресенье)
    """
    current_date = datetime.now() + timedelta(days=add_days)
    weekday = current_date.weekday()
    
    if weekday == 6:
        return 0
    return weekday

def class_select(class_name: str) -> Keyboard:
    """
    Создает клавиатуру с днями недели для выбранного класса.
    
    Args:
        class_name (str): Название класса (например, "8а")
        
    Returns:
        Keyboard: Клавиатура VK с кнопками дней недели
    """
    if not class_name or len(class_name) < 2:
        return EMPTY_KEYBOARD
        
    grade = class_name[:-1]
    letter = class_name[-1].lower()
    
    if (grade not in CLASS_CONFIG or 
        letter not in CLASS_CONFIG[grade]['letters']):
        return EMPTY_KEYBOARD
        
    keyboard = Keyboard(inline=True)
    prefix = f"{'a' if letter == 'а' else 'b'}{grade}"
    
    day_layout = [
        [("ПН", "monday"), ("ВТ", "vtorn")],
        [("СР", "sreda")],
        [("ЧТ", "chetverg"), ("ПТ", "pyatnica")],
        [("СБ", "sb")]
    ]
    
    for row in day_layout:
        for short_name, day_code in row:
            if short_name == "СБ" and not CLASS_CONFIG[grade]['has_saturday']:
                continue
            keyboard.add(Text(
                short_name,
                payload={"command": f"{prefix}_{day_code}"}
            ))
        keyboard.row()
    
    return keyboard

def get_class_list() -> List[str]:
    """
    Возвращает список всех доступных классов.
    
    Returns:
        List[str]: Список классов в формате ["5а", "5б", ...]
    """
    classes = []
    for grade, config in CLASS_CONFIG.items():
        for letter in config['letters']:
            classes.append(f"{grade}{letter}")
    return classes

def is_valid_class(class_name: str) -> bool:
    """
    Проверяет, существует ли указанный класс.
    
    Args:
        class_name (str): Название класса для проверки
        
    Returns:
        bool: True если класс существует, False в противном случае
    """
    if not class_name or len(class_name) < 2:
        return False
        
    grade = class_name[:-1]
    letter = class_name[-1].lower()
    
    return (grade in CLASS_CONFIG and 
            letter in CLASS_CONFIG[grade]['letters'])

def has_saturday_classes(class_name: str) -> bool:
    """
    Проверяет, есть ли у класса занятия по субботам.
    
    Args:
        class_name (str): Название класса для проверки
        
    Returns:
        bool: True если у класса есть занятия по субботам, False в противном случае
    """
    if not is_valid_class(class_name):
        return False
        
    grade = class_name[:-1]
    return CLASS_CONFIG[grade]['has_saturday']
