from vkbottle import Keyboard, Text, KeyboardButtonColor, EMPTY_KEYBOARD
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from vkbottle import Bot
from vkbottle.bot import Message
import sqlite3
import logging

async def isAdmin(bot: Bot, user_id: int) -> bool:
    try:
        groups = await bot.api.groups.get_by_id()
        group = groups.groups[0]
        managers = await bot.api.groups.get_members(group_id=group.id, filter="managers")
        for manager in managers.items:
            if manager.id == user_id:
                return True
        return False
    except Exception as e:
        logging.error(f"Ошибка при получении групп: {e}")
        return False