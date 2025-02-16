from typing import List
from utils.consts import CLASS_CONFIG

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
