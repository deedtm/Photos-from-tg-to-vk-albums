import asyncio
import time
import vk_api
import requests
import logging
from vk.errors import AccessDenied, OutOfTries


class VkAlbum:
    def __init__(
        self, token: str, retry_seconds: int, anti_flood_retry_hours: int = 12
    ):
        self.retry_seconds = retry_seconds
        self.anti_flood_retry_hours = anti_flood_retry_hours

        self.session = vk_api.VkApi(token=token)
        self.vk = self.session.get_api()
        self.login_user = self.__get_login_user()
        self.login_user_id = self.login_user["id"]
        logging.info(
            msg=f"Logged in VK as {self.login_user['first_name']} {self.login_user['last_name']} @id{self.login_user_id}"
        )

    def create_album(self, title: str) -> dict[str]:
        return self.__call_vk_method(
            self.vk.photos.createAlbum, title=title, privacy_view=["only_me"]
        )

    def remove_album(self, album_id: int):
        return self.__call_vk_method(self.vk.photos.deleteAlbum, album_id=album_id)

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

    def __upload_photo_wrapper(
        self, album_id: int, path_to_photo: str, caption: str, trying: int = 0
    ):
        try:
            self.__upload_photo(album_id, path_to_photo, caption)
        except requests.exceptions.JSONDecodeError as err:
            if trying >= 5:
                raise OutOfTries("uploading photos")

            logging.error(
                msg=f"Failed to decode json. Retrying in {self.retry_seconds // 10} seconds..."
            )
            time.sleep(self.retry_seconds / 10)

            trying += 1
            self.__upload_photo_wrapper(album_id, path_to_photo, caption)

        except vk_api.exceptions.ApiError as err:
            if trying >= 5:
                raise OutOfTries("uploading photos")

            err_text = err.__str__()
            if "[100]" in err_text and "photos_list is invalid" in err_text:
                logging.error(
                    msg=f"Failed to upload photo to album. Retrying in {self.retry_seconds // 10} seconds..."
                )
                time.sleep(self.retry_seconds / 10)
            elif "[200]" in err_text:
                logging.error(
                    msg=f"Access denied while uploading photo. Retrying in {self.retry_seconds // 5} seconds..."
                )
                time.sleep(self.retry_seconds / 5)
            else:
                return self.__api_error_handler(
                    err,
                    self.__upload_photo,
                    1,
                    album_id=album_id,
                    path_to_photo=path_to_photo,
                    caption=caption,
                )

            trying += 1
            self.__upload_photo_wrapper(album_id, path_to_photo, caption, trying)

        except BaseException as err:
            if trying >= 5:
                raise OutOfTries("uploading photos")

            logging.error(
                msg=f"{err.__class__.__name__}:{err}. Retrying in {self.retry_seconds} seconds..."
            )
            time.sleep(self.retry_seconds)

            trying += 1
            self.__upload_photo_wrapper(album_id, path_to_photo, caption)

    def add_photos(self, album_id: int, photos_data: list[tuple[str, str]]):
        photos_amount = len(photos_data)
        logging.info(msg=f"Uploading {photos_amount} photos to {album_id}...")
        i = 0
        for path, caption in photos_data:
            try:
                self.__upload_photo_wrapper(album_id, path, caption)
            except OutOfTries as err:
                logging.info(msg=err.__str__())
            time.sleep(1.5)
            i += 1
            logging.info(f"Uploaded {i}/{photos_amount}")

    def get_albums(self):
        return self.__call_vk_method(
            self.vk.photos.getAlbums, owner_id=self.login_user_id
        )

    def get_album_by_title(self, name: str):
        albums = self.get_albums()
        for album in albums["items"]:
            if name in album["title"]:
                return album

    def __get_login_user(self):
        return self.__call_vk_method(self.vk.users.get)[0]

    def __call_vk_method(self, method, **kwargs):
        try:
            output = method(**kwargs)
            return output
        except vk_api.exceptions.ApiError as err:
            self.__api_error_handler(err, method, **kwargs)

    async def __api_error_handler(
        self,
        err: vk_api.exceptions.ApiError,
        func: vk_api.vk_api.VkApiMethod,
        **kwargs,
    ):
        err_text = err.__str__()
        try:
            method = func._method.__str__()
        except AttributeError:
            method = func.__str__()
        logging.error(msg=f"{err.__class__.__name__}:{method}:{err_text}")

        if "[9]" in err_text:
            logging.info(
                msg=f"Sleeping for {self.anti_flood_retry_hours:0.1f} hours and retrying..."
            )
            await asyncio.sleep(self.anti_flood_retry_hours * 3600)
            self.__call_vk_method(func, **kwargs)
        elif "[5]" in err_text:
            logging.error(
                msg="VK token was expired. Please update it in `config.ini` file"
            )
        elif "[200]" in err_text:
            raise AccessDenied(method)
