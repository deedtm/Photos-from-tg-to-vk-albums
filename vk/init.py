import time
import vk_api
import logging
from io import BytesIO
from PIL import Image


class VkAlbum:
    def __init__(self, token: str, retry_seconds: int, anti_flood_tries: int):
        self.session = vk_api.VkApi(token=token)
        self.vk = self.session.get_api()
        self.upload = vk_api.VkUpload(self.vk)
        self.user_id = self.__get_user_id()

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
        return self.__call_vk_method(
            self.upload.photo, photos=photo, album_id=album_id, caption=caption
        )

    def get_albums(self):
        return self.__call_vk_method(self.vk.photos.getAlbums, owner_id=self.user_id)

    def get_album_by_title(self, name: str):
        albums = self.get_albums()
        for album in albums["items"]:
            if name in album["title"]:
                return album

    def __get_user_id(self):
        return self.__call_vk_method(self.vk.users.get)[0]["id"]

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
            results = ', '.join(['ok' if output['items'] else 'bad' for output in outputs])
            logging.info(msg=f'Results: {results}')

    def __call_vk_method(self, method, sleep_multiplier = 0.9, **kwargs):
        try:
            output = method(**kwargs)
            return output
        except vk_api.exceptions.ApiError as err:
            self.__api_error_handler(err, method, sleep_multiplier, **kwargs)

    def __api_error_handler(
        self, err: vk_api.exceptions.ApiError, func: vk_api.vk_api.VkApiMethod, sleep_multiplier: float, **kwargs
    ):
        err_text = err.__str__()
        try:
            method = func._method
        except AttributeError:
            method = func
        logging.error(msg=f"{err.__class__.__name__}:{method}:{err_text}")

        if "[9]" in err_text:
            sleep_multiplier += 0.1
            retry_seconds = self.retry_seconds * sleep_multiplier
            self.__anti_flood_control()
            logging.warning(
                msg=f"Sleeping for {retry_seconds:0.1f} seconds and retrying..."
            )
            time.sleep(retry_seconds)

            self.__call_vk_method(func, sleep_multiplier, **kwargs)
        elif "[5]" in err_text:
            logging.error(msg="VK token was expired. Please update it in `config.ini` file")
        else:
            logging.error(msg=f"There is a problem with VK API: {err_text}")
