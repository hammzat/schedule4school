import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from PIL import Image
import logging
import loguru

def downloadimages():
    url = "https://shkola4-chepetsk.gosuslugi.ru/roditelyam-i-uchenikam/izmenenie-v-raspisanii/"
    base_url = "https://shkola4-chepetsk.gosuslugi.ru"
    cache_dir = os.path.join(os.getcwd(), 'files', 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        img_tags = soup.find_all("img")
        imgpaths = []
        
        now = datetime.now()
        dates = { 'today': now.strftime("%d.%m"), 'tomorrow': (now + timedelta(days=1)).strftime("%d.%m"), 'day_after': (now + timedelta(days=2)).strftime("%d.%m") }
        for img_tag in img_tags:
            img_url = img_tag.get("src", "")
            if not img_url:
                continue
            img_name = img_url.split("/")[-1]
            if not re.match(r"\d{2}\.\d{2}(?:\.\d{2,4})?.png", img_name):
                continue
                
            date_part = img_name.split(".png")[0] 
            base_date = ".".join(date_part.split(".")[:2])
            loguru.logger.info(f"base_date: {base_date}")
            if not any(date == base_date for date in dates.values()):
                continue
                
            cache_path = os.path.join(cache_dir, img_name)
            if os.path.exists(cache_path) and (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))).seconds < 3600:
                imgpaths.append(cache_path)
                continue

            try:
                full_url = img_url if img_url.startswith('http') else base_url + img_url
                loguru.logger.info(f"img_url: {full_url}")
                img_response = requests.get(full_url)
                img_response.raise_for_status()
                
                with open(cache_path, "wb") as f:
                    f.write(img_response.content)
                imgpaths.append(cache_path)
                with Image.open(cache_path) as img:
                    img = img.convert('RGB')
                    img.save(cache_path, 'JPEG', quality=85, optimize=True)
                loguru.logger.info(f"img saved: {cache_path}")
            except Exception as e:
                logging.error(f"Error downloading image {img_name}: {str(e)}")
                continue
                
        return imgpaths
    except Exception as e:
        logging.error(f"Error in downloadimages: {str(e)}")
        return []

async def upload_photo(bot, path: str):
    """Вспомогательная функция для загрузки фото в ВК"""
    upload_server = await bot.api.photos.get_messages_upload_server()
    with open(path, "rb") as img:
        response = requests.post(upload_server.upload_url, files={"photo": img})
    result = response.json()
    return await bot.api.photos.save_messages_photo(
        photo=result["photo"],
        server=result["server"],
        hash=result["hash"]
    ) 