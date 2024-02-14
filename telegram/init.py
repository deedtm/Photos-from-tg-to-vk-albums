import asyncio
import json
import telegram.utils as utils
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers.message_handler import MessageHandler
from pyrogram.errors.exceptions import bad_request_400, flood_420
from vk.init import VkAlbum
from telegram.exceptions import ChatAlreadyIn

with open("telegram/commands.json", "r") as f:
    bot_texts: dict = json.load(f)
with open("telegram/errors.json") as f:
    bot_errors: dict = json.load(f)


class UserBot:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        interval: int,
        chats_ids: list[int],
        limit: int,
        phone_number: str,
        password: str,
        vk_album: VkAlbum,
    ):
        self.posted = {ch_id: [] for ch_id in chats_ids}
        self.albums_ids = {}
        self.is_started = False
        self.chats_ids = chats_ids
        self.interval = interval
        self.limit = limit
        self.vk_album = vk_album
        self.session_name = session_name
        self.app = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone_number,
            password=password,
        )

        self.__add_handlers()

    async def __help_handler(self, client: Client, msg: Message):
        commands = utils.get_commands_descs(bot_texts["descriptions"])
        interval = utils.format_interval(self.interval)

        try:
            await msg.edit(
                bot_texts["help"].format(commands=commands, interval=interval, limit=self.limit)
            )
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __chats_handler(self, client: Client, msg: Message):
        chats = [await client.get_chat(id) for id in self.chats_ids]
        chats_descs = utils.get_chats_descs(chats)
        try:
            await msg.edit(
                bot_texts["chats"].format(chats=chats_descs),
                disable_web_page_preview=True,
            )
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __start_handler(self, client: Client, msg: Message):
        if self.is_started:
            try:
                await msg.edit(bot_errors["already_started"])
            except flood_420.FloodWait as err:
                seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
                await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))
        else:
            for chat_id in self.chats_ids:
                await self.__add_chat(chat_id)
            try:
                self.is_started = True
                await msg.edit(bot_texts["start"])
                await self.__start_reposting()
            except flood_420.FloodWait as err:
                seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
                await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __stop_handler(self, client: Client, msg: Message):
        if not self.is_started:
            try:
                await msg.edit(bot_errors["not_started"])
            except flood_420.FloodWait as err:
                seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
                await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))
        else:
            try:
                self.is_started = False
                interval = utils.format_interval(self.interval)
                await msg.edit(bot_texts["stop"].format(interval=interval))
            except flood_420.FloodWait as err:
                seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
                await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __interval_handler(self, client: Client, msg: Message):
        _, arg = tuple(msg.text.split(" ", 1))
        prev = utils.format_interval(self.interval)
        self.interval = int(arg) * 60
        cur = utils.format_interval(self.interval)

        await msg.edit(bot_texts["interval"].format(prev=prev, cur=cur))

    async def __limit_handler(self, client: Client, msg: Message):
        _, arg = tuple(msg.text.split(" ", 1))
        prev = self.limit
        self.limit = int(arg)

        await msg.edit(bot_texts["limit"].format(prev=prev, cur=self.limit))

    async def __add_handler(self, client: Client, msg: Message):
        _, arg = tuple(msg.text.split(" ", 1))
        if not arg.startswith("@"):
            async for mes in client.search_global(arg):
                if mes.chat.title == arg:
                    chat_id = mes.chat.id
                    break
        else:
            usernames = arg.split()
            if len(usernames) > 1:
                await msg.edit(await self.__multiple_add(usernames))
                return
            else:
                chat_id = arg
        try:
            await self.__add_chat(chat_id)
            logging.info(msg=f"Added new chat: {chat_id}")
            text = bot_texts["add"].format(username=chat_id)

        except (bad_request_400.UsernameInvalid, bad_request_400.UsernameNotOccupied):
            text = bot_errors["invalid_username"].format(username=chat_id)

        try:
            await msg.edit(text)
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __multiple_add(self, usernames: list[str]):
        successful = []
        unsuccessful = []
        for username in usernames:
            try:
                res = await self.__add_chat(username)
                if res:
                    logging.info(msg=f"Added new chat: {username}")
                    successful.append(username)
                    await asyncio.sleep(1.25)
            except (
                bad_request_400.UsernameInvalid,
                bad_request_400.UsernameNotOccupied,
            ):
                unsuccessful.append(username)

        template = bot_texts["multiple_add"].split("\n", 2)
        text = (
            template[0]
            + "\n"
            + template[1].format(successful=utils.format_usernames_list(successful))
            if not unsuccessful
            else bot_texts["multiple_add"].format(
                successful=utils.format_usernames_list(successful),
                unsuccessful=utils.format_usernames_list(unsuccessful),
            )
        )
        return text

    async def __rem_handler(self, client: Client, msg: Message):
        _, arg = tuple(msg.text.split(" ", 1))
        if not arg.startswith("@"):
            for mes in await client.search_global(arg):
                if mes.chat.title == arg:
                    chat_id = mes.chat.id
                    break
        else:
            usernames = arg.split()
            if len(usernames) > 1:
                await msg.edit(await self.__multiple_rem(usernames))
                return
            else:
                chat_id = arg
            chat_id = arg
        try:
            await self.__remove_chat(chat_id)
            text = bot_texts["rem"].format(username=chat_id)

            logging.info(msg=f"Removed chat: {chat_id}")

        except (bad_request_400.UsernameInvalid, bad_request_400.UsernameNotOccupied):
            text = bot_errors["invalid_username"].format(username=chat_id)
        except KeyError:
            text = bot_errors["not_found"].format(username=chat_id)

        try:
            await msg.edit(text)
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __multiple_rem(self, usernames: list[str]):
        successful = []
        unsuccessful = []
        for username in usernames:
            try:
                await self.__remove_chat(username)
                logging.info(msg=f"Removed chat: {username}")
                successful.append(username)
            except (
                bad_request_400.UsernameInvalid,
                bad_request_400.UsernameNotOccupied,
                KeyError,
            ):
                unsuccessful.append(username)

        template = bot_texts["multiple_rem"].split("\n", 2)
        text = (
            template[0]
            + "\n"
            + template[1].format(successful=utils.format_usernames_list(successful))
            if not unsuccessful
            else bot_texts["multiple_rem"].format(
                successful=utils.format_usernames_list(successful),
                unsuccessful=utils.format_usernames_list(unsuccessful),
            )
        )
        return text

    async def __add_chat(self, chat_id: int | str):
        try:
            chat = await self.app.get_chat(chat_id)
            is_added = False
            if chat_id not in self.chats_ids:
                self.chats_ids.append(chat.id)
                is_added = True
            if chat_id not in self.posted:
                self.posted.setdefault(chat.id, [])
                is_added = True
            if chat_id not in self.albums_ids:
                album = self.vk_album.get_album_by_title(chat.title)
                if not album:
                    album = self.vk_album.create_album(chat.title)
                    logging.info(f"Created new album: {chat.title}")
                elif album and chat_id not in self.albums_ids:
                    pass
                else:
                    return
                self.albums_ids.setdefault(chat.id, album["id"])
                is_added = True
                
            return is_added
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await asyncio.sleep(seconds)
            await self.__add_chat(chat_id)

    async def __remove_chat(self, chat_id: int | str):
        chat = await self.app.get_chat(chat_id)
        album = self.vk_album.get_album_by_title(chat.title)
        if album:
            self.vk_album.remove_album(album["id"])
        self.albums_ids.pop(chat.id)
        self.posted.pop(chat.id)
        self.chats_ids.remove(chat.id)

    async def __start_reposting(self):
        logging.info(msg=f'Reposting was started')
        while self.is_started:
            await asyncio.gather(
                self.__repost_to_album(),
                asyncio.sleep(self.interval),
            )
        logging.info(msg=f'Reposting was stopped')

    async def __repost_to_album(self):
        logging.info("Started reposting")

        for ch_id in self.chats_ids:
            if not (ch_id in self.chats_ids and ch_id in self.albums_ids and ch_id in self.posted):
                continue
            logging.info(f"Uploading {ch_id}...")
            
            messages: list[Message] = [
                mes
                async for mes in self.app.get_chat_history(ch_id, self.limit)
                if mes.id not in self.posted[ch_id]
            ]
            album_id = self.albums_ids[ch_id]
            if not messages:
                logging.info(f"No photos to upload from {ch_id}")
            else:
                try:
                    for ind, mes in enumerate(messages):
                        if mes.photo:
                            caption = await self.__get_caption(ch_id, ind, messages)
                            byted_photo = await self.app.download_media(mes, in_memory=True)
                            self.vk_album.add_photo(album_id, byted_photo, caption)

                        self.posted[ch_id].append(mes.id)
                    logging.info(f"Uploaded {ch_id}")
                except KeyError:
                    pass
        logging.info(msg="Finished reposting")

    async def __get_caption(self, channel_id: int, ind: int, messages: list[Message]):
        mes = messages[ind]
        i = 1
        media_group = None
        try:
            caption = mes.caption
            if not caption:
                caption = (await self.app.get_media_group(channel_id, mes.id))[0].caption
                while not caption:
                    try:
                        mes = messages[ind + i]
                        caption = mes.caption
                        if mes.photo and not caption:
                            caption = (
                                await self.app.get_media_group(channel_id, mes.id)
                            )[0].caption
                        if not caption:
                            caption = mes.text
                        i += 1 if not media_group else len(media_group)
                    except IndexError:
                        i = 1
                        while not caption:
                            try:
                                mes = messages[ind - i]
                                caption = mes.caption
                                if mes.photo and not caption:
                                    caption = (
                                        await self.app.get_media_group(channel_id, mes.id)
                                    )[0].caption
                                if not caption:
                                    caption = mes.text
                                i += 1
                            except IndexError:
                                logging.warning(
                                    msg=f"Не найдено описание для {channel_id}, {messages[ind].id}"
                                )
                                return
            return caption
        except ValueError as err:
            err_text = err.__str__()
            logging.error(msg=err_text)
            return

    def __add_handlers(self):
        self.app.add_handler(
            MessageHandler(self.__help_handler, filters.me & filters.regex("\\.help"))
        )
        self.app.add_handler(
            MessageHandler(
                self.__limit_handler, filters.me & filters.regex("\\.limit \d+")
            )
        )
        self.app.add_handler(
            MessageHandler(
                self.__interval_handler, filters.me & filters.regex("\\.interval \d+")
            )
        )
        self.app.add_handler(
            MessageHandler(self.__start_handler, filters.me & filters.regex("\\.start"))
        )
        self.app.add_handler(
            MessageHandler(self.__stop_handler, filters.me & filters.regex("\\.stop"))
        )
        self.app.add_handler(
            MessageHandler(self.__chats_handler, filters.me & filters.regex("\\.chats"))
        )
        self.app.add_handler(
            MessageHandler(self.__add_handler, filters.me & filters.regex("\\.add .+"))
        )
        self.app.add_handler(
            MessageHandler(self.__rem_handler, filters.me & filters.regex("\\.rem .+"))
        )
