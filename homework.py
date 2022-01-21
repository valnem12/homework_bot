import os
import sys
import requests
import telegram
from telegram.error import TelegramError
import time
from dotenv import load_dotenv
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s -%(levelname)s - %(name)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()

logger.info('bot started')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_RETRY_TIME = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message): # noqa
    """.
    Функция send_message() отправляет сообщение в Telegram чат,
    определяемый переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as e:
        logger.exception('Chat message has failed with the following error:'
                         f'\n {e}')
    logger.info('Message sent to the chat')


def get_api_answer(current_timestamp):
    """.
    Функция get_api_answer() делает запрос к единственному
    эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    logger = logging.getLogger('get_api_answer')
    logger.info('get_api_answer')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            logger.error('No server response')
            raise
        logger.info('Successfully connected to the server')
    except requests.exceptions.RequestException as e:
        logger.exception(e)
        raise
    return response.json()


def check_response(response):
    """
    Функция проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    if not issubclass(type(response), dict):
        raise TypeError('Type is not a dictionary')

    if not response.get('homeworks'):
        raise ValueError('No homeworks were found so far')

    return response.get('homeworks')[0]


def parse_status(homework):
    """.
    Функция parse_status() извлекает из информации о конкретной домашней работе
    статус этой работы. В качестве параметра функция получает только один
    элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES
    """
    if not {'homework_name', 'status'}.issubset(homework):
        missing_keys = []
        for k in {'homework_name', 'status'}:
            logger.info(f'{k}')
            if k not in homework:
                missing_keys.append(k)
        raise KeyError('Response is missing the following keys: '
                       f'{missing_keys}')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_STATUSES:
        raise ValueError(f'Unknown status data: "{status}".')

    verdict = HOMEWORK_STATUSES[status]
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{verdict}')


def check_tokens():
    """.
    Функция check_tokens() проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    logger = logging.getLogger('check_tokens')
    if None in {PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID}:
        token_names = []
        for n in globals():
            if (eval(n) in (PRACTICUM_TOKEN,
                            TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
               and eval(n) is None and '__' not in n):
                token_names.append(n)        
        logger.critical(f'Missing tokens are {token_names}.')
        return False
    return True


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger(__name__)

    if not check_tokens():
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.info('response was received')
            message = parse_status(check_response(response))
            logger.info('parsing was completed')
            send_message(bot, message)
            logger.info('message was sent to Telegram chat '
                        f'{TELEGRAM_CHAT_ID}')
            current_timestamp = response.get('current_date')
            time.sleep(TELEGRAM_RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            print('ERROR: ', error.args)
            if str(error) != str(previous_error):
                send_message(bot, message)
                previous_error = error
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    main()
