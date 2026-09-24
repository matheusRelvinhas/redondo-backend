import sys
import os
import requests
from time import sleep
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import TeamsInfo, LeaguesInfo, PlayerStats12Months, PlayerStats6Months, PlayerStats3Months, PlayerStatsLastMonth
from loguru import logger
from app import create_app

current_script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_script_dir)

app = create_app()

BASE_IMG_PATH = os.path.join(backend_dir, 'img', 'imgs')

DIRS = {
    "team": os.path.join(BASE_IMG_PATH, 'teams'),
    "league": os.path.join(BASE_IMG_PATH, 'leagues'),
    "player": os.path.join(BASE_IMG_PATH, 'players'),
}

for path in DIRS.values():
    os.makedirs(path, exist_ok=True)

def download_img(url: str, path_img: str):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        with open(path_img, 'wb') as f:
            f.write(resp.content)
        logger.success(f"Donwload: {path_img}")
    except Exception as e:
        logger.error(f"Fail download - {url}: {e}")

def donwload_imgs(model, type_img: str):
    data = model.query.all()
    for item in data:
        url = getattr(item, 'image_url', None)
        slug = getattr(item, 'slug', None)
        if not url or not slug:
            continue
        ext = url.split('.')[-1].split('?')[0]
        filename = f"{slug}.{ext}"
        path_img = os.path.join(DIRS[type_img], filename)
        if os.path.exists(path_img):
            logger.info(f"Already exists ({type_img}): {filename}")
            os.remove(path_img)
        download_img(url, path_img)
        sleep(0.2)

with app.app_context():
    donwload_imgs(TeamsInfo, "team")
    donwload_imgs(LeaguesInfo, "league")
    donwload_imgs(PlayerStats12Months, "player")
    donwload_imgs(PlayerStats6Months, "player")
    donwload_imgs(PlayerStats3Months, "player")
    donwload_imgs(PlayerStatsLastMonth, "player")
