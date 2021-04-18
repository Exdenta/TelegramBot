import requests
import vk_api
from vk_api.audio import VkAudio
from concurrent.futures import ThreadPoolExecutor

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

# сессия ВКонтакте
vk_session = None

# ============================ /start ============================ #

# /start command
def start(update: Update, _: CallbackContext) -> None:
    """Сообщает пользователю о возможностях бота"""
    update.message.reply_text(
        "Бот работает с ВКонтакте API.\n "
        "/audio - поиск музыки\n "
        "/document - поиск документов "
    )


# ============================ /audio ============================ #

# Состояния беседы с ботом при поиске музыки
AUDIO_NAME = 0

# /audio command
def audio(update: Update, _: CallbackContext) -> int:
    """Поиск и скачивание музыки"""
    update.message.reply_text("Введите название трека или /cancel : ")
    return AUDIO_NAME


def get_track(params) -> None:
    track = params["track"]
    update = params["update"]

    # скачивает аудио
    doc = requests.get(track["url"].split("mp3")[0] + "mp3")

    # добавляет аудио элемент
    # работает медленно из-за ожидания telegram API
    # https://github.com/python-telegram-bot/python-telegram-bot/issues/2352
    # обещают исправить в v14 python-telegram-bot
    update.message.reply_audio(
        doc.content,
        duration=track["duration"],
        performer=track["artist"],
        title=track["title"],
    )


def show_audio(update: Update, _: CallbackContext) -> int:
    """Вызывается когда пользователь ввел название аудио"""
    query = update.message.text
    vkaudio = VkAudio(vk_session)
    # количество треков для просмотра
    n_tracks = 5
    tracks = vkaudio.search(q=query, count=n_tracks)

    # для ускорения создается несколько потоков
    with ThreadPoolExecutor(n_tracks) as ex:
        ex.map(get_track, [{"update": update, "track": track} for track in tracks])

    return ConversationHandler.END


# ============================ /document ============================ #

# Состояния беседы с ботом при поиске документов
DOCUMENT_NAME = 0
# Разрешения файлов для поиска
document_ext = ["fb2", "epub", "pdf", "doc", "docx"]

# /audio command
def document(update: Update, _: CallbackContext) -> int:
    """Поиск и скачивание документов"""
    update.message.reply_text("Введите название документа или /cancel : ")

    return DOCUMENT_NAME


def get_document(params) -> None:
    document = params["document"]
    update = params["update"]

    # скачивает документ
    doc = requests.get(document["url"])

    # добавляет документ
    update.message.reply_document(doc.content, document["title"])


def show_documents(update: Update, _: CallbackContext) -> int:
    """Вызывается когда пользователь ввел название документа"""
    query = update.message.text
    # количество документов для просмотра
    n_documents_to_show = 5
    # какое-то количество будет неверного формата
    n_documents_to_load = 20

    with vk_api.VkRequestsPool(vk_session) as pool:
        # https://vk.com/dev/docs.search
        doc = pool.method(
            "docs.search", {"q": query, "search_own": 0, "count": n_documents_to_load}
        )

    # отфильтровываем ненужные форматы файлов
    documents = list(filter(lambda x: x["ext"] in document_ext, doc.result["items"]))
    documents = documents[: min(len(documents), n_documents_to_show)]

    # для ускорения создается несколько потоков
    with ThreadPoolExecutor(n_documents_to_show) as ex:
        ex.map(
            get_document,
            [{"update": update, "document": document} for document in documents],
        )

    return ConversationHandler.END


# ============================ /cancel ============================ #

# /cancel command
def cancel(update: Update, _: CallbackContext) -> int:
    """Отменяет действие"""
    update.message.reply_text("Действие отменено")

    return ConversationHandler.END


# ============================ /help ============================ #


def help(update: Update, _: CallbackContext) -> None:
    """Отображает доступные комманды"""
    update.message.reply_text(
        "Бот работает с ВКонтакте API. "
        "/audio - поиск музыки"
        "/document - поиск документов"
    )


# ============================ MAIN ============================ #


def main(telegram_token) -> None:
    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher

    # Поиск музыки /audio
    audio_search_handler = ConversationHandler(
        entry_points=[CommandHandler("audio", audio)],
        states={
            AUDIO_NAME: [
                MessageHandler(Filters.text & ~Filters.command, show_audio),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Поиск документов /document
    document_search_handler = ConversationHandler(
        entry_points=[CommandHandler("document", document)],
        states={
            DOCUMENT_NAME: [
                MessageHandler(Filters.text & ~Filters.command, show_documents),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавляем команды в диспетчер
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(audio_search_handler)
    dispatcher.add_handler(document_search_handler)
    dispatcher.add_handler(CommandHandler("help", help))

    # Запуск бота
    updater.start_polling()

    # Остановить сервер при нажатии "Crtl + C"
    updater.idle()


if __name__ == "__main__":

    # vk_login = input("Введите логин ВКонтакте (+7xxxxxxxxxx): ")
    vk_login = "+79099392858"  ############################################################### TODO: Delete !
    # Права доступа https://vk.com/dev/permissions
    vk_session = vk_api.VkApi(vk_login, "", scope="docs,audio")
    try:
        # пытаемся авторизоваться без пароля (по сохраненному токену)
        vk_session.auth()
    except:
        # исключение выбросится в случае если токен еще не был сгенерирован
        # (логин введен впервые) в этом случае запрашиваем пароль
        vk_password = input(
            "Введите пароль ВКонтакте (единожды для авто генерации токена): "
        )
        vk_session = vk_api.VkApi(vk_login, vk_password)
        vk_session.auth()

    telegram_token = "1724864470:AAGWvuVwHZUS9TDx85N_6rayPac8wktx4Zo"
    main(telegram_token)
