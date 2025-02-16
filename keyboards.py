from vkbottle import Keyboard, KeyboardButtonColor, Text, EMPTY_KEYBOARD


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