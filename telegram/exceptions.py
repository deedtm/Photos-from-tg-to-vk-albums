class UserBotException(Exception):
    pass


class ChatAlreadyIn(UserBotException):
    def __str__(self):
        return "chat has already been added"
    