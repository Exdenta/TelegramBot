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

help_text = """
            Бот работает с ВКонтакте API.
            /audio - поиск музыки
            /document - поиск документов
            /generate - генерирование текста
            """

# /start command
def start(update: Update, _: CallbackContext) -> None:
    """Сообщает пользователю о возможностях бота"""
    update.message.reply_text(help_text)


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


# ============================ /generate ============================ #

from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch
import copy

# Состояния беседы с ботом при генерировании текста
GENERATE_TEXT_TOPIC = 0


def load_tokenizer_and_model(model_name_or_path):
    return (
        GPT2Tokenizer.from_pretrained(model_name_or_path),
        GPT2LMHeadModel.from_pretrained(model_name_or_path).cuda(),
    )


# модель, которая генерирует текст
tokenizer, model = load_tokenizer_and_model("sberbank-ai/rugpt3large_based_on_gpt2")

# to make the generated texts better, we remove "bad" tokens from the model, some junk symbols such as html tags, links etc.
bad_word_ids = [
    [203],  # \n
    [225],  # weird space 1
    [28664],  # weird space 2
    [13298],  # weird space 3
    [206],  # \r
    [49120],  # html
    [25872],  # http
    [3886],  # amp
    [38512],  # nbsp
    [10],  # &
    [5436],  # & (another)
    [5861],  # http
    [372],  # yet another line break
    [421, 4395],  # МСК
    [64],  # \
    [33077],  # https
    [1572],  # ru
    [11101],  # Источник
]


def gen_fragment(
    context,
    bad_word_ids=bad_word_ids,
    print_debug_output=False,
    temperature=1.0,
    max_length=75,
    min_length=50,
):
    input_ids = tokenizer.encode(
        context, add_special_tokens=False, return_tensors="pt"
    ).to("cuda")
    input_ids = input_ids[:, -1700:]
    input_size = input_ids.size(1)
    output_sequences = model.generate(
        input_ids=input_ids,
        max_length=max_length + input_size,
        min_length=min_length + input_size,
        top_p=0.95,
        do_sample=True,
        num_return_sequences=1,
        temperature=1.0,
        pad_token_id=0,
        eos_token_id=2,
        bad_words_ids=bad_word_ids,
        no_repeat_ngram_size=6,
    )
    if len(output_sequences.shape) > 2:
        output_sequences.squeeze_()
    generated_sequence = output_sequences[0].tolist()[input_size:]
    if print_debug_output:
        for idx in generated_sequence:
            print(
                idx, tokenizer.decode([idx], clean_up_tokenization_spaces=True).strip()
            )
    text = tokenizer.decode(generated_sequence, clean_up_tokenization_spaces=True)
    text = text[: text.find("</s>")]
    text = text[: text.rfind(".") + 1]
    return context + text


# /generate command
def generate(update: Update, _: CallbackContext) -> int:
    """Генерирование текста"""
    update.message.reply_text("Введите тему для текста или /cancel : ")

    return GENERATE_TEXT_TOPIC


def generate_text(update: Update, _: CallbackContext) -> int:
    """Вызывается когда пользователь ввел название темы для текста"""
    query = update.message.text
    text = gen_fragment(query, temperature=1.0, max_length=40)
    update.message.reply_text(text)
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
    update.message.reply_text(help_text)


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

    # Генерирование текста GPT-3 /generate
    generate_text_handler = ConversationHandler(
        entry_points=[CommandHandler("generate", generate)],
        states={
            GENERATE_TEXT_TOPIC: [
                MessageHandler(Filters.text & ~Filters.command, generate_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавляем команды в диспетчер
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(audio_search_handler)
    dispatcher.add_handler(document_search_handler)
    dispatcher.add_handler(generate_text_handler)
    dispatcher.add_handler(CommandHandler("help", help))

    # Запуск бота
    updater.start_polling()

    # Остановить сервер при нажатии "Crtl + C"
    updater.idle()


if __name__ == "__main__":

    vk_login = input("Введите логин ВКонтакте (+7xxxxxxxxxx): ")

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

    # Токен необходимо сгенерировать у отца ботов https://t.me/botfather
    telegram_token = "TOKEN"
    main(telegram_token)
