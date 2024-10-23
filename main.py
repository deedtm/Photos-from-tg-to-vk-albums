import logging
import sys
from telegram import UserBot   
from vk import VkAlbum
from config.telegram import UB_ARGS
from config.vk import ALBUM_ARGS


def main():
    vk_album = VkAlbum(*ALBUM_ARGS)
    ub = UserBot(*UB_ARGS, vk_album)
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
    