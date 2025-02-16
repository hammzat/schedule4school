import os
from dotenv import load_dotenv

load_dotenv()

VK_API_TOKEN = os.getenv('VK_API_TOKEN')

link_vkgroup = os.getenv('LINK_VKGROUP')
link_projectsite = os.getenv('LINK_PROJECTSITE') 