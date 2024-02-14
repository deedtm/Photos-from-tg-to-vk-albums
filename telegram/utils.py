from datetime import timedelta, datetime
from pyrogram.types import Chat


def get_commands_descs(descriptions: dict):
    return "\n".join(
        [
            f"<code>.{command}</code> — <i>{desc}</i>"
            for command, desc in descriptions.items()
        ]
    )


def get_chats_descs(chats: list[Chat]):
    output = []
    for chat in chats:
        if chat.username:
            output.append(
                f'<b>•</b>  <a href="t.me/{chat.username}">{chat.title}</a>'
            )
        else:
            output.append(f"<b>•</b>  {chat.title} <i>(приватный)</i>")
    return "\n".join(output)


def format_usernames_list(usernames: list[str]):
    return "\n".join([f"<b>•</b>  {username}" for username in usernames])


def format_interval(seconds: int):
    formatted = datetime(1, 1, 1, 0, 0, 0, 0) + timedelta(seconds=seconds)
    if formatted.hour != 0:
        format = "%#H ч. %#M мин." if formatted.minute != 0 else "%#H ч."
        return formatted.strftime(format)
    else:
        if formatted.minute != 0:
            return formatted.strftime("%#M мин.")
