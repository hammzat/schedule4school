import logging, sys, loguru
from vkbottle import Bot
from config import VK_API_TOKEN
from handlers import labelers
from services.scheduler import schedule_jobs, scheduler
from config import state_dispenser
DEBUG = 1

def setup_logging():
    if DEBUG:
        loguru.logger.remove()
        loguru.logger.add(
            sys.stdout,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        logging.getLogger("apscheduler").setLevel(logging.DEBUG)
    else:
        loguru.logger.remove()
        loguru.logger.add(sys.stdout, level="ERROR")
        logging.getLogger("apscheduler").setLevel(logging.ERROR)

    loguru.logger.info("Логирование настроено")

bot = Bot(token=VK_API_TOKEN, state_dispenser=state_dispenser)
bot.labeler.vbml_ignore_case = True

for labeler in labelers:
    bot.labeler.load(labeler)
    loguru.logger.info(f"Загружен лейблер: {labeler}")

async def startup():
    setup_logging()
    schedule_jobs(bot)
    scheduler.start()
    loguru.logger.info("Бот запускается...")

if __name__ == "__main__":
    bot.loop_wrapper.on_startup.append(startup())
    bot.run_forever()