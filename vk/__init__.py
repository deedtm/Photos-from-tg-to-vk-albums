import asyncio
import vk_api
import requests
import logging
from .errors import AccessDenied, OutOfTries


class VkAlbum:
    def __init__(
        self,
        token: str,
        retry_seconds: int,
        json_decode_retry_seconds: int,
        upload_fail_retry_seconds: int,
        pack_fail_retry_seconds: int,
        access_denied_retry_seconds: int,
        anti_flood_retry_seconds: int,
        photo_upload_max_tries: int,
        pack_upload_max_tries: int,
    ):
        self.RETRY_SECONDS = retry_seconds
        self.JSON_DECODE_RETRY = json_decode_retry_seconds
        self.UPLOAD_FAIL_RETRY = upload_fail_retry_seconds
        self.PACK_FAIL_RETRY = pack_fail_retry_seconds
        self.ACCESS_DENIED_RETRY = access_denied_retry_seconds
        self.ANTI_FLOOD_RETRY = anti_flood_retry_seconds
        self.PHOTO_UPLOAD_MT = photo_upload_max_tries
        self.PACK_UPLOAD_MT = pack_upload_max_tries

        self.session = vk_api.VkApi(token=token)
        self.vk = self.session.get_api()
        self.login_user = self.__get_login_user()
        self.login_user_id = self.login_user["id"]
        logging.info(
            msg=f"Logged in VK as {self.login_user['first_name']} {self.login_user['last_name']} @id{self.login_user_id}"
        )

    async def create_album(self, title: str) -> dict[str]:
        return await self.__call_vk_method(
            self.vk.photos.createAlbum, title=title, privacy_view=["only_me"]
        )

    async def remove_album(self, album_id: int):
        return await self.__call_vk_method(
            self.vk.photos.deleteAlbum, album_id=album_id
        )

    def __upload_photo(self, album_id: int, path_to_photo: str, caption: str):
        upload_url = self.vk.photos.getUploadServer(album_id=album_id)["upload_url"]
        with open(path_to_photo, "rb") as file:
            files = {"file1": file}
            with requests.post(upload_url, files=files) as res:
                data = res.json()

        self.vk.photos.save(
            album_id=album_id,
            server=data["server"],
            photos_list=data["photos_list"],
            hash=data["hash"],
            caption=caption[:2048],
        )

    async def __upload_photo_wrapper(
        self, album_id: int, path_to_photo: str, caption: str, trying: int = 0
    ):
        try:
            self.__upload_photo(album_id, path_to_photo, caption)
        except requests.exceptions.JSONDecodeError as err:
            if trying >= self.PHOTO_UPLOAD_MT:
                raise OutOfTries("uploading photos")

            logging.error(
                msg=f"Failed to decode json. Retrying in {self.JSON_DECODE_RETRY} seconds..."
            )
            await asyncio.sleep(self.JSON_DECODE_RETRY)

            trying += 1
            await self.__upload_photo_wrapper(album_id, path_to_photo, caption)

        except vk_api.exceptions.ApiError as err:
            if trying >= self.PHOTO_UPLOAD_MT:
                raise OutOfTries("uploading photos")

            err_text = err.__str__()
            if "[100]" in err_text and "photos_list is invalid" in err_text:
                logging.error(
                    msg=f"Failed to upload photo to album. Retrying in {self.UPLOAD_FAIL_RETRY} seconds..."
                )
                await asyncio.sleep(self.UPLOAD_FAIL_RETRY)
            elif "[200]" in err_text:
                logging.error(
                    msg=f"Access denied while uploading photo. Retrying in {self.ACCESS_DENIED_RETRY} seconds..."
                )
                await asyncio.sleep(self.ACCESS_DENIED_RETRY)
            else:
                return await self.__api_error_handler(
                    err,
                    "__upload_photo",
                    album_id=album_id,
                    path_to_photo=path_to_photo,
                    caption=caption,
                )

            trying += 1
            await self.__upload_photo_wrapper(album_id, path_to_photo, caption, trying)

        except BaseException as err:
            if trying >= self.PHOTO_UPLOAD_MT:
                raise OutOfTries("uploading photos")

            logging.error(
                msg=f"{err.__class__.__name__}:{err}. Retrying in {self.RETRY_SECONDS} seconds..."
            )
            await asyncio.sleep(self.RETRY_SECONDS)

            trying += 1
            await self.__upload_photo_wrapper(album_id, path_to_photo, caption)

    async def __upload_pack(
        self, album_id: int, photos_data: list[tuple[str, str]], trying: int = 0
    ):
        photos_amount = len(photos_data)
        logging.info(msg=f"Uploading {photos_amount} photos to {album_id}...")
        i = 0
        for ind, data in enumerate(photos_data):
            path, caption = data
            try:
                await self.__upload_photo_wrapper(album_id, path, caption)
                await asyncio.sleep(1.5)
                i += 1
                logging.debug(f"Uploaded {i}/{photos_amount}")
            except OutOfTries as err:
                logging.info(msg=err.__str__())
                return photos_data[ind:]

    async def upload_photos_pack(
        self, album_id: int, photos_data: list[tuple[str, str]], trying: int = 0
    ):        
        left = photos_data
        while trying < self.PACK_UPLOAD_MT:
            left = await self.__upload_pack(album_id, left)
            if left is None:
                break
            logging.error(f"Failed to upload pack to {album_id} ({trying}). Retrying in {self.PACK_FAIL_RETRY} seconds...")
            trying += 1
            await asyncio.sleep(self.PACK_FAIL_RETRY)

        if trying >= self.PACK_UPLOAD_MT:
            logging.info(f"Skipping uploading to {album_id}: out of tries")
            return

    async def get_albums(self):
        return await self.__call_vk_method(
            self.vk.photos.getAlbums, owner_id=self.login_user_id
        )

    async def get_album_by_title(self, name: str):
        albums = await self.get_albums()
        for album in albums["items"]:
            if name in album["title"]:
                return album

    def __get_login_user(self):
        return self.vk.users.get()[0]

    async def __call_vk_method(self, method, **kwargs):
        try:
            output = method(**kwargs)
            return output
        except vk_api.exceptions.ApiError as err:
            await self.__api_error_handler(err, method, **kwargs)

    async def __api_error_handler(
        self,
        err: vk_api.exceptions.ApiError,
        func: vk_api.vk_api.VkApiMethod | str,
        **kwargs,
    ):
        err_text = err.__str__()
        if isinstance(func, vk_api.vk_api.VkApiMethod):
            method = func._method
        else:
            method = func
        logging.error(msg=f"{err.__class__.__name__}:{method}:{err_text}")

        if "[9]" in err_text:
            logging.info(
                msg=f"Sleeping for {self.ANTI_FLOOD_RETRY // 3600:0.1f} hours and retrying..."
            )
            await asyncio.sleep(self.ANTI_FLOOD_RETRY)
            self.__call_vk_method(func, **kwargs)
        elif "[5]" in err_text:
            logging.error(
                msg="VK token was expired. Please update it in `config.ini` file"
            )
        elif "[200]" in err_text:
            raise AccessDenied(method)
