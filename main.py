import logging
import sys
from telegram import UserBot   
from configparser import ConfigParser
from vk import VkAlbum     

config = ConfigParser()
config.read("config.ini")
API_ID = int(config.get("telegram", "api_id"))
API_HASH = config.get("telegram", "api_hash")
SESSION_NAME = config.get("telegram", "session_name")
INTERVAL = int(config.get("telegram", "interval"))
PHONE_NUMBER = config.get("telegram", "phone_number")
PASSWORD = config.get("telegram", "password")

VK_TOKEN = config.get("vk", "token")
RETRY_SECONDS = int(config.get("vk", "retry_seconds"))

def main():
    vk_album = VkAlbum(VK_TOKEN, RETRY_SECONDS)
    ub = UserBot(API_ID, API_HASH, SESSION_NAME, INTERVAL, PHONE_NUMBER, PASSWORD, vk_album)
    logging.info('Disabling pyrogram logging...')
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith(('pyrogram.session', 'pyrogram.connection')) and isinstance(logger, logging.Logger):
            logging.info(f"Disabled {name}")
            logger.setLevel(logging.WARNING)
    logging.info('Logging was disabled')
    ub.app.run()    


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    