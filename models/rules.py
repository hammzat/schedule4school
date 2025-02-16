from vkbottle import ABCRule
from vkbottle.bot import Message
from utils.other import isAdmin
from config import state_dispenser

class HasUserState(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        state = await state_dispenser.get(event.from_id)
        return state is not None
    
class HasBroadcastState(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        state = await state_dispenser.get(event.from_id)
        return state and state.state == "waiting_message"

class NeedAdmin(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        return await isAdmin(event, event.from_id) 