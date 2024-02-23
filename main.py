import logging
from telegram.init import UserBot
from configparser import ConfigParser
from vk.init import VkAlbum

config = ConfigParser()
config.read("config.ini")
API_ID = int(config.get("telegram", "api_id"))
API_HASH = config.get("telegram", "api_hash")
SESSION_NAME = config.get("telegram", "session_name")
INTERVAL = int(config.get("telegram", "interval"))
CHANNELS_IDS = list(map(int, config.get("telegram", "channels_ids").split(', ')))
PHONE_NUMBER = config.get("telegram", "phone_number")
PASSWORD = config.get("telegram", "password")

VK_TOKEN = config.get("vk", "token")
RETRY_SECONDS = int(config.get("vk", "retry_seconds"))
ANTIFLOOD_TRIES = int(config.get("vk", "antiflood-control_tries"))

def main():
    vk_album = VkAlbum(VK_TOKEN, RETRY_SECONDS, ANTIFLOOD_TRIES)
    ub = UserBot(API_ID, API_HASH, SESSION_NAME, INTERVAL, CHANNELS_IDS, PHONE_NUMBER, PASSWORD, vk_album)
    logging.info('Disabling pyrogram session logging...')
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith('pyrogram.session') and isinstance(logger, logging.Logger):
            logging.info(f"Disabled {name}")
            logger.setLevel(logging.WARNING)
    logging.info('Logging was disabled')
    ub.app.run()    


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
    