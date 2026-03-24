import asyncio
import logging
import sys

from config.telegram import UB_ARGS
from config.vk import ALBUM_ARGS
from telegram import UserBot
from vk import VkAlbum


async def main():
    vk_album = VkAlbum(*ALBUM_ARGS)
    ub = UserBot(*UB_ARGS, vk_album)
    logging.info("Disabling pyrogram logging...")
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith(("pyrogram.session", "pyrogram.connection")) and isinstance(
            logger, logging.Logger
        ):
            logging.info(f"Disabled {name}")
            logger.setLevel(logging.WARNING)
    logging.info("Logging was disabled")
    # ub.app.run()
    await ub.app.start()
    try:
        # Устанавливаем флаг и запускаем один раз
        ub.is_started = True 
        await asyncio.gather(
            ub._start_reposting(), # Обратите внимание на name mangling, если метод приватный
            asyncio.Event().wait()
        )
    finally:
        await ub.app.stop()


if __name__ == "__main__":
    is_debug = sys.argv[1:] and sys.argv[1] == "-d"
    logging_lvl = logging.DEBUG if is_debug else logging.INFO
    logging.basicConfig(level=logging)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
