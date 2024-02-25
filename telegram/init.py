import asyncio
import json
import os
import telegram.utils as utils
import logging
from datetime import timedelta
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import Message, Chat
from pyrogram.handlers.message_handler import MessageHandler
from pyrogram.errors.exceptions import bad_request_400, flood_420
from vk.errors import AccessDenied
from vk.init import VkAlbum

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
        phone_number: str,
        password: str,
        vk_album: VkAlbum,
    ):
        if "chats_data.json" not in os.listdir("telegram"):
            self.__update_chats_data({"posted": [], "albums_ids": []})
        self.chats_ids = chats_ids
        self.chats = {chat_id: None for chat_id in chats_ids}
        self.albums_ids = self.__get_albums_ids()
        self.interval = interval
        self.vk_album = vk_album
        self.retry_seconds = 30
        self.is_started = False
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
                bot_texts["help"].format(commands=commands, interval=interval)
            )
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __chats_handler(self, client: Client, msg: Message):
        if None in self.chats.values():
            self.chats = await self.__get_chats()
        chats_descs = utils.get_chats_descs(self.chats.values())
        try:
            await msg.edit(
                bot_texts["chats"].format(chats=chats_descs),
                disable_web_page_preview=True,
            )
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __start_handler(self, client: Client, msg: Message):
        if None in self.chats.values():
            self.chats = await self.__get_chats()
        if self.is_started:
            try:
                await msg.edit(bot_errors["already_started"])
            except flood_420.FloodWait as err:
                seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
                await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))
        else:
            for chat in self.chats.values():
                await self.__add_chat(chat=chat)
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

    async def __add_handler(self, client: Client, msg: Message):
        if None in self.chats.values():
            self.chats = await self.__get_chats()
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
        except UnboundLocalError:
            text = bot_errors["invalid_argument"].format(arg=", ".join(arg.split()))

        try:
            await msg.edit(text)
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await msg.edit(bot_errors["flood_wait"].format(seconds=seconds))

    async def __multiple_add(self, usernames: list[str]):
        if None in self.chats.values():
            self.chats = await self.__get_chats()
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

    async def __add_chat(
        self, chat_id: int | str | None = None, chat: Chat | None = None
    ):
        if chat_id is None and chat is None:
            raise AttributeError("chat_id or chat must be filled")
        try:
            if chat is None:
                chat = await self.app.get_chat(chat_id)

            posted = self.__get_posted()
            is_added = False
            if chat.id not in self.chats:
                self.chats.setdefault(chat.id, chat)
                is_added = True
            if str(chat.id) not in posted:
                posted.setdefault(chat.id, [])
                self.__save_posted(posted)
                is_added = True

            album = self.vk_album.get_album_by_title(chat.title)
            if album is None:
                album = self.vk_album.create_album(chat.title)
                logging.info(f"Created new album: {chat.title}")
            if str(chat.id) in self.albums_ids:
                self.albums_ids[str(chat.id)] = album["id"]
                is_added = True
            else:
                self.albums_ids.setdefault(str(chat.id), album["id"])
                is_added = True
            self.__save_albums_ids()

            return is_added
        except flood_420.FloodWait as err:
            seconds = int(err.__str__().split("of ", 1)[-1].split()[0])
            await asyncio.sleep(seconds)
            await self.__add_chat(chat_id)
        except ValueError:
            await self.app.send_message(
                "me", bot_errors["not_joined"].format(chat_id=chat_id)
            )

    async def __remove_chat(self, chat_id: int | str):
        chat = await self.app.get_chat(chat_id)
        album = self.vk_album.get_album_by_title(chat.title)
        if album:
            self.vk_album.remove_album(album["id"])
        self.chats.pop(chat.id)

        self.albums_ids.pop(str(chat.id))
        self.__save_albums_ids()

        posted = self.__get_posted()
        posted.pop(str(chat.id))
        self.__save_posted(posted)

    async def __start_reposting(self):
        logging.info(msg=f"Reposting was started")
        try:
            while self.is_started:
                await asyncio.gather(
                    self.__repost_to_album(),
                    asyncio.sleep(self.interval),
                )
            logging.info(msg=f"Reposting was stopped")
        except AccessDenied as err:
            logging.error(err)
            self.is_started = False
            await self.app.send_message("me", bot_errors["access_denied"])

    async def __repost_to_album(self):
        logging.info("Started reposting")
        posted = self.__get_posted()
        for chat_id in self.chats:
            chat_id = str(chat_id)
            logging.info(f"Uploading {chat_id}...")
            if chat_id not in posted:
                posted.setdefault(chat_id, [])

            if not posted[chat_id]:
                limit = 20
            else:
                limit = abs(
                    [mes async for mes in self.app.get_chat_history(chat_id, 1)][0].id
                    - max(posted[chat_id])
                )
                # print([mes async for mes in self.app.get_chat_history(chat_id, 1)][0].id, '-', max(posted[chat_id]), '=', limit)
                if limit == 0:
                    logging.info(msg=f"No new messages in {chat_id}")
                    continue
            messages: list[Message] = [
                mes
                async for mes in self.app.get_chat_history(chat_id, limit)
                if mes.id not in posted[str(chat_id)]
            ]
            album_id = self.albums_ids[chat_id]
            if not messages:
                logging.info(f"No photos to upload from {chat_id}")
                continue
            messages = await self.__refill_messages(messages)
            photos_data = await self.__get_photos_data(messages)
            self.vk_album.add_photos(album_id, photos_data)
            logging.info(f"Uploaded {chat_id}")
        logging.info(msg="Finished reposting")

    async def __refill_messages(self, messages: list[Message]):
        try:
            mg = await self.app.get_media_group(messages[-1].chat.id, messages[-1].id)
            dif = messages[-1].id - mg[0].id
            if dif != 0:
                messages.extend(
                    [
                        mes
                        async for mes in self.app.get_chat_history(
                            messages[0].chat.id, dif, len(messages)
                        )
                    ]
                )
        except ValueError:
            pass
        return messages

    async def __get_photos_data(self, messages: list[Message]):
        data = []
        ids = []
        for ind, mes in enumerate(messages):
            if mes.photo:
                caption = await self.__get_photo_caption(ind, messages)
                photo = await self.app.download_media(mes, in_memory=True)
                data.append((photo, caption))
            ids.append(mes.id)
        posted = self.__get_posted()
        posted[str(mes.chat.id)].extend(ids)
        self.__save_posted(posted)
        return data

    async def __get_photo_caption(self, ind: int, messages: list[Message]):
        mes = messages[ind]
        caption = await self.__get_caption(None, messages, ind)
        if caption is None:
            msg = f"Not found caption for {mes.id}"
            caption = ""
        else:
            msg = f"Found caption for {mes.id}:\n{caption}"
        logging.info(msg=msg)
        return caption

    async def __get_caption(
        self,
        mes: Message | None = None,
        messages: list[Message] | None = None,
        ind: int | None = None,
        try_num: int = 1,
    ):
        if try_num >= 40:
            return
        if mes is None and (messages is None or ind is None):
            raise ValueError("mes or messages and ind must be filled")
        if mes is None:
            mes = messages[ind]
        logging.info(f"Try {try_num} to get caption for {mes.id} ({mes.chat.id})...")

        if mes.text:
            return mes.text
        if mes.caption:
            return mes.caption

        try:
            media_group = await self.app.get_media_group(mes.chat.id, mes.id)
            for mes in media_group:
                if mes.caption:
                    return mes.caption
        except ValueError:  # не нашлось подписи и медиагруппы у данного сообщения
            media_group = None

        if messages is None and ind is None:
            raise ValueError("caption was not found. messages and ind must be filled")

        ind = await self.__method_wrapper(
            self.__get_new_message_ind,
            True,
            messages=messages,
            ind=ind,
            media_group=media_group,
        )
        if ind is None:
            ind = 0
        return await self.__get_caption(None, messages, ind, try_num + 1)

    async def __get_new_message_ind(
        self,
        messages: list[Message],
        ind: int,
        media_group: list[Message] | None = None,
    ):
        if media_group is None:
            next_mes_ind = ind - 1
            prev_mes_ind = ind + 1
        else:
            ids_and_chats = [(mes.id, mes.chat.id) for mes in messages]
            next_mes_ind = (
                ids_and_chats.index((media_group[-1].id, media_group[-1].chat.id)) - 1
            )
            prev_mes_ind = (
                ids_and_chats.index((media_group[0].id, media_group[0].chat.id)) + 1
            )

        next_mes = messages[next_mes_ind]
        if prev_mes_ind != len(messages):
            prev_mes = messages[prev_mes_ind]
            mes = messages[ind]
            dif_prev = abs(mes.date - prev_mes.date)
            dif_next = abs(mes.date - next_mes.date)
        # try:
        #     print(f"{prev_mes_ind >= len(messages)} or (({timedelta(0, 0, 0, 0, 1) > dif_next} or {dif_next < dif_prev}) and {next_mes_ind >= 0})")
        # except UnboundLocalError:
        #     print(f"{prev_mes_ind >= len(messages)} or (None and {next_mes_ind >= 0})")
        is_fits_err = (
            timedelta(0, 0, 0, 0, 1) > dif_next or dif_next < dif_prev
        ) # подходит под погрешность 
        is_fits_video_err = (
            next_mes.media == MessageMediaType.VIDEO
            and timedelta(0, 30, 0, 0, 7) > dif_next
        ) # подходит под погрешность видео
        if prev_mes_ind >= len(messages) or ((is_fits_err or is_fits_video_err) and next_mes_ind >= 0):  # берем подпись в качестве след. сообщения
            return next_mes_ind
        else:  # берем подпись в качестве пред. сообщения
            return prev_mes_ind

    async def __get_chats(self):
        chats = {}
        for chat_id in self.chats_ids:
            try:
                chats.setdefault(chat_id, await self.app.get_chat(chat_id))
            except (bad_request_400.ChannelInvalid, bad_request_400.ChatInvalid, bad_request_400.ChatIdInvalid):
                logging.warning(msg=f"User did not subscribed on {chat_id}")
                chats.setdefault(chat_id, chat_id)
        return chats

    async def __method_wrapper(self, func, is_async: bool, try_num: int = 1, **kwargs):
        try:
            return await func(**kwargs) if is_async else func(**kwargs)
        except BaseException as e:
            logging.error(msg=f"Try {try_num}:{e.__class__.__name__}:{e.__str__()}")
            retry_seconds = (
                self.retry_seconds if e.__class__.__name__ != "IndexError" else 1
            )
            if try_num < 5:
                logging.info(msg=f"Retrying in {retry_seconds} seconds...")
                await asyncio.sleep(retry_seconds)
                return await self.__method_wrapper(
                    func, is_async, try_num + 1, **kwargs
                )
            else:
                args = ", ".join([k for k in kwargs.keys()])
                logging.info(msg=f"Out of tries. Skipping {func.__name__}({args})")

    def __get_chats_data(self) -> dict[str, dict[int, int]]:
        with open("telegram/chats_data.json") as f:
            return json.load(f)

    def __update_chats_data(self, value: dict):
        with open("telegram/chats_data.json", "w") as f:
            json.dump(value, f, indent=4)

    def __save_posted(self, posted: dict[int, int]):
        data = self.__get_chats_data()
        data["posted"] = posted
        self.__update_chats_data(data)

    def __save_albums_ids(self):
        data = self.__get_chats_data()
        data["albums_ids"] = self.albums_ids
        self.__update_chats_data(data)

    def __get_posted(self):
        data = self.__get_chats_data()
        saved_posted = data["posted"].items()
        posted = {chat_id: value for chat_id, value in saved_posted}
        data["posted"] = posted
        return posted

    def __get_albums_ids(self):
        data = self.__get_chats_data()
        saved_albums_ids = data["albums_ids"].items()
        albums_ids = {chat_id: value for chat_id, value in saved_albums_ids}
        data["albums_ids"] = albums_ids
        return albums_ids

    def __add_handlers(self):
        self.app.add_handler(
            MessageHandler(self.__help_handler, filters.me & filters.regex("\\.help"))
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
