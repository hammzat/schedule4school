from vkbottle.bot import Message, BotLabeler
from models.states import RegistrationState
from models.rules import HasUserState
from utils.db import Database
from config import state_dispenser
from utils.keyboards import generate_mainkeyboard
from utils.classes import is_valid_class
import logging


bl = BotLabeler()
bl.vbml_ignore_case = True

db = Database()

@bl.private_message(text="Регистрация")
async def start_registration(message: Message):
    await state_dispenser.set(message.from_id, RegistrationState.WAITING_CLASS)
    await message.answer(
        "Напишите ваш класс (например: 8а, 8б):"
    )

@bl.private_message(HasUserState(), text=["5а", "5б", "6а", "6б", "7а", "7б", "8а", "8б", "9а", "9б", "10а", "11а"])
async def handle_registration(message: Message):
    state = await state_dispenser.get(message.from_id)
    if not state:
        return
    
    if state.state == RegistrationState.WAITING_CLASS:
        text = message.text.lower().replace('a', 'а')
        if not is_valid_class(text):
            await message.answer("Неверный формат класса. Пример: 8а, 8б")
            return
            
        try:
            user_info = await message.get_user()
            full_name = f"{user_info.first_name} {user_info.last_name}"
            db.register_user(
                message.from_id,
                full_name,
                text
            )
            
            await state_dispenser.delete(message.from_id)
            
            await message.answer(
                "Регистрация успешно завершена!",
                keyboard=generate_mainkeyboard()
            )
        except Exception as e:
            logging.error(f"Error during registration: {str(e)}")
            await message.answer("Произошла ошибка при регистрации. Попробуйте позже.") 