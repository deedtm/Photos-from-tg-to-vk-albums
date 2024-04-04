from vk_api.vk_api import VkApiMethod

class VkAlbumException(Exception):
    pass


class MethodException(VkAlbumException):
    def __init__(self, method: VkApiMethod):
        self.method = method


class AccessDenied(MethodException):
    def __str__(self):
        return f"Access denied while processing method {self.method} (maybe token has invalid rights)"


class OutOfTries(MethodException):
    def __str__(self):
        return f"Out of tries while processing {self.method}"
        