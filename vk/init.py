import time
import vk_api
import requests
import logging
from io import BytesIO
from PIL import Image
from vk.errors import AccessDenied


class VkAlbum:
    def __init__(self, token: str, retry_seconds: int, anti_flood_tries: int):
        self.session = vk_api.VkApi(token=token)
        self.vk = self.session.get_api()
        self.login_user = self.__get_login_user()
        self.login_user_id = self.login_user["id"]
        logging.info(
            msg=f"Logged in VK as {self.login_user['first_name']} {self.login_user['last_name']} @id{self.login_user_id}"
        )

        self.retry_seconds = retry_seconds
        self.anti_flood_tries = anti_flood_tries

    def create_album(self, title: str) -> dict[str]:
        return self.__call_vk_method(self.vk.photos.createAlbum, title=title)

    def remove_album(self, album_id: int):
        return self.__call_vk_method(self.vk.photos.deleteAlbum, album_id=album_id)

    def add_photo(self, album_id: int, photo: BytesIO, caption: str):
        image = Image.open(photo)
        image.save(photo, format="jpeg")
        photo.seek(0)
        image.close()
        del image

        return self.__upload_photo(album_id, photo, caption)
        # return self.__call_vk_method(
        #     self.upload.photo, album_id=album_id, photos=photo
        # )

    def __upload_photo(self, album_id: int, photo: BytesIO, caption: str):
        upload_url = self.vk.photos.getUploadServer(album_id=album_id)["upload_url"]
        files = {"file1": photo}
        res = requests.post(upload_url, files=files).json()

        self.vk.photos.save(
            album_id=album_id,
            server=res["server"],
            photos_list=res["photos_list"],
            hash=res["hash"],
            caption=caption[:2048],
        )
        del photo, res, upload_url
    
    def __upload_photo_wrapper(self, album_id: int, photo: BytesIO, caption: str):
        try:
            self.add_photo(album_id, photo, caption)
        except requests.exceptions.JSONDecodeError as err:
            logging.error(msg=f"Failed to decode json. Retrying in {self.retry_seconds // 10} seconds...")
            time.sleep(self.retry_seconds // 10)
            self.__upload_photo_wrapper(album_id, photo, caption)
            
        except vk_api.exceptions.ApiError as err:
            err_text = err.__str__()
            if '[100]' in err_text and 'photos_list is invalid' in err_text:
                logging.error(
                    msg=f"Failed to upload photo to album. Retrying in {self.retry_seconds // 10} seconds..."
                )
                time.sleep(self.retry_seconds // 10)
                self.__upload_photo_wrapper(album_id, photo, caption)
            else:
                self.__api_error_handler(err, self.add_photo, 1, album_id=album_id, photo=photo, caption=caption)
        
        except BaseException as err:
            logging.error(msg=f'{err.__class__.__name__}:{err}. Retrying in {self.retry_seconds // 1} seconds...')
            time.sleep(self.retry_seconds / 10)
            self.__upload_photo_wrapper(album_id, photo, caption)

    def add_photos(self, album_id: int, photos_data: tuple[BytesIO, str]):
        photos_amount = len(photos_data)
        logging.info(msg=f"Uploading {photos_amount} photos to {album_id}...")
        i = 0
        for photo, caption in photos_data:
            self.__upload_photo_wrapper(album_id, photo, caption)            
            time.sleep(1.5)
            i += 1
            logging.info(f"Uploaded {i}/{photos_amount}")
        del i, photos_amount

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

    def __anti_flood_control(self):
        for i in range(self.anti_flood_tries):
            logging.info(msg=f"Antiflood-control: Try {i + 1}")
            outputs = [
                self.__call_vk_method(self.vk.messages.getConversations),
                self.__call_vk_method(self.vk.friends.get),
                self.__call_vk_method(self.vk.wall.get),
                self.__call_vk_method(self.vk.newsfeed.get),
                self.__call_vk_method(self.vk.search.getHints, q="123))", limit=1),
            ]
            results = ", ".join(
                ["ok" if output["items"] else "bad" for output in outputs]
            )
            logging.info(msg=f"Results: {results}")

    def __call_vk_method(self, method, sleep_multiplier=0.9, **kwargs):
        try:
            output = method(**kwargs)
            return output
        except vk_api.exceptions.ApiError as err:
            self.__api_error_handler(err, method, sleep_multiplier, **kwargs)

    def __api_error_handler(
        self,
        err: vk_api.exceptions.ApiError,
        func: vk_api.vk_api.VkApiMethod,
        sleep_multiplier: float,
        **kwargs,
    ):
        err_text = err.__str__()
        try:
            method = func._method
        except AttributeError:
            method = func
        logging.error(msg=f"{err.__class__.__name__}:{method}:{err_text}")

        sleep_multiplier += 0.1
        retry_seconds = self.retry_seconds * sleep_multiplier

        if "[9]" in err_text:
            self.__anti_flood_control()
            logging.info(
                msg=f"Sleeping for {retry_seconds:0.1f} seconds and retrying..."
            )
            time.sleep(retry_seconds)
            self.__call_vk_method(func, sleep_multiplier, **kwargs)
        elif "[5]" in err_text:
            logging.error(
                msg="VK token was expired. Please update it in `config.ini` file"
            )
        elif "[200]" in err_text:
            raise AccessDenied(method)
