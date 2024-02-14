# Перед первым запуском
- Установите зависимости из файла `requirements.txt` с помощью `pip install -r requirements.txt` в консоли
- Вставьте в файл `config.ini`:
    1. Ваши **api_id** и **api_hash**  _(ниже объяснено, как их получить)_
    2. Ваши **номер телефона** _(в интернациональном формате)_ и **пароль** _(если включен облачный пароль в настройках)_ от аккаунта в телеграм
    3. Ваш **токен** от аккаунта вк _(ниже объяснено, как его получить)_

## api_id и api_hash 
- Авторизуйтесь на сайте [my.telegram.org](https://my.telegram.org)
- Нажмите `API development tools`
- Создание приложения:
    - В поле `App title` введите название (например, _userbot_)
    - В поле `App short name` введите краткое название (например, _userb_)
    - В поле `URL` введите `www.telegram.org`
    - Поля `Platform` и `Description` необязательны к заполнению
    - Нажмите `Create Application`
- В полях `App api_id` и `App api_hash` указаны требуемые данные

## Токен ВК
***Никому не передавайте ваш токен, иначе вы можете потерять аккаунт***
- Авторизуйтесь в вашем браузере в ВК
- Перейдите на сайт [vkhost.github.io](https://vkhost.github.io/)
- Нажмите `Настройки »`
- В поле права выберите только: `друзья`, `фотографии`, `стена`, `доступ в любое время`, `группы`
- Нажмите `Получить`
- Нажмите `Разрешить`
- Скопируйте из адресной строки ваш токен _(после `access_token=` до `&expires_in=0`, ***не включительно***)_

###
# Про самого юзербота
Юзербот поддерживает и каналы, и группы. При запуске скрипта, в бота уже будут добавлены некоторые чаты.

Бот управляется при помощи специальных команд. Все команды принимаются только в `Избранном`
### Про команды:
- Для получения списка, введите `.help`.
- Каждую из команд можно скопировать прямо из списка, нажав на нее
- В фигурных скобках указан аргумент команды, необходимый для указания. 
- Интервал нужно указывать в минутах (если нужно указать _n_ часов, то нужно ввести в качестве аргумента _n * 60_)
- В списке чатов можно перейти в каждый из чатов, нажав на него _(исключение: приватные чаты, подписанные в списке)_
- Знак `|` обозначает `или`
- В `.add` и `.rem` юзернеймы нужно вписывать с `@`
- Можно добавлять чаты, на которые вы не подписаны _(исключение: приватные чаты)_
- Юзернеймом (= имя пользователя) является идентификатор чата, начинающийся с `@` (в ссылке он идет после `t.me/`)
- Если чат приватный (в профиле чата нет юзернейма/ссылки), то вместо юзернейма в `.add` и `.rem` можно вписать название чата
- `.add` и `.rem` могут принимать несколько юзернеймов сразу _(но без названий)_. Для этого нужно разделить юзернеймы пробелом

### Важные моменты:
- Альбомы в ВК создаются сами, по мере добавления новых чатов
- Если переименовать альбомы, то юзербот создаст новый, с прошлым названием
- После добавления/удаления чатов можно не перезапускать автовыгрузку. Изменения входят в силу сразу 
- При удалении чатов, удаляются также и соответствующие альбомы
- Список чатов сбросится, если перезапустить скрипт. Однако, если добавить те же чаты, что и до перезапуска, то юзербот будет репостить фотки в те же альбомы, что прежде.
- Изменение значения интервала принимается только после следующей выгрузки по старому интервалу
- Лимит сообщений менять не рекомендуется. Увеличивать его значение стоит только тогда, когда юзербот пропускает подписи к изображениям или сами изображения у некоторых чатов