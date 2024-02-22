from vk_api.vk_api import VkApiMethod

class VkAlbumException(Exception):
    pass


class AccessDenied(VkAlbumException):
    def __init__(self, method: VkApiMethod):
        self.method = method
        
    def __str__(self):
        return f"Access denied while processing method {self.method} (maybe token has invalid rights)"
    