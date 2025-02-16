from vkbottle import Keyboard, Text, EMPTY_KEYBOARD, KeyboardButtonColor
from utils.consts import CLASS_CONFIG
from utils.classes import is_valid_class

def class_select(class_name: str) -> Keyboard:
    """
    Создает клавиатуру с днями недели для выбранного класса.
    
    Args:
        class_name (str): Название класса (например, "8а")
        
    Returns:
        Keyboard: Клавиатура VK с кнопками дней недели
    """
    if not is_valid_class(class_name):
        return EMPTY_KEYBOARD
        
    grade = class_name[:-1]
    letter = class_name[-1].lower()
    
    keyboard = Keyboard(inline=True)
    prefix = f"{'a' if letter == 'а' else 'b'}{grade}"
    
    day_layout = [
        [("Понедельник", "monday"), ("Вторник", "vtornik")],
        [("Среда", "sreda")],
        [("Четверг", "chetverg"), ("Пятница", "pyatnica")],
        [("Суббота", "sb")]
    ]
    
    for row in day_layout:
        for short_name, day_code in row:
            if short_name == "Суббота" and not CLASS_CONFIG[grade]['has_saturday']:
                continue
            keyboard.add(Text(
                short_name,
                payload={"schedule": f"{prefix}_{day_code}"}
            ))
        keyboard.row()
    
    return keyboard 

def generate_mainkeyboard() -> Keyboard:
    keyboard = Keyboard(one_time=False)
    keyboard.add(Text("Моё расписание"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Изменения"), color=KeyboardButtonColor.POSITIVE)
    keyboard.row()
    keyboard.add(Text("Звонки"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Какой сейчас урок"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Прочее"))
    return keyboard

def generate_otherkeyboard(is_Admin: bool = False) -> Keyboard:
    keyboard = Keyboard(inline=True)
    keyboard.add(Text("Профиль"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Настройки"), color=KeyboardButtonColor.PRIMARY).row()
    keyboard.add(Text("Помощь")).row()
    if is_Admin:
        keyboard.add(Text("Админ-Панель (только для админов)", payload={"admin_command": "admin"}), color=KeyboardButtonColor.NEGATIVE)
        
    return keyboard

def generate_profilekeyboard(send: str, notify: str) -> Keyboard:
    keyboard = Keyboard(inline=True)
    keyboard.add(Text(f"{send} Рассылка", payload={"command": "toggle_send"}))
    keyboard.row()
    keyboard.add(Text(f"{notify} Уведомления", payload={"command": "toggle_notify"}))
    keyboard.row()
    keyboard.add(Text("⚙️ Настройка уведомлений", payload={"command": "settings"}))
    return keyboard