import os
import sys
import requests
import telegram
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

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

CURRENT_STATUS = None


def send_message(bot, message): # noqa
    """.
    Функция send_message() отправляет сообщение в Telegram чат,
    определяемый переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    logger = logging.getLogger('send_message')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Message sent to the chat')
    except Exception as e:
        logger.exception('Chat message has failed with the following error:'
                         f'\n {e}')


def get_api_answer(current_timestamp):
    """.
    Функция get_api_answer() делает запрос к единственному
    эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    logger = logging.getLogger('get_api_answer')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        logger.error('No server response')
        raise 'No server alive'
    logger.info('Successfully connected to the server')
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
    logger = logging.getLogger('check_response')
    if type(response) != dict:
        raise TypeError('Warning is not a dictionary')
    try:
        res = response.get('homeworks')[0]
        logger.info('Homework was found')
        return res
    except IndexError as e:
        logger.error('No homeworks were found so far')
        logger.exception(f'Exception is {e}')
        raise IndexError('Dictionary is empty')
        return {}


def parse_status(homework):
    """.
    Функция parse_status() извлекает из информации о конкретной домашней работе
    статус этой работы. В качестве параметра функция получает только один
    элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES
    """
    global CURRENT_STATUS
    logger = logging.getLogger('parse_status')
    try:
        homework_name = homework.get('homework_name')
        logger.info(f'homework name is {homework_name}')

        homework_status = homework.get('status')
        logger.info(f'homework status is {homework_status}')

        if CURRENT_STATUS != homework_status:
            try:
                verdict = HOMEWORK_STATUSES[homework_status]
                CURRENT_STATUS = homework_status
                logger.debug('No updates with homework status')
                return (f'Изменился статус проверки работы "{homework_name}".'
                        f'{verdict}')
            except KeyError as k:
                logger.error(f'No such key existing {k}')
                return {}
    except Exception as e:
        logger.warning('No homework found')
        logger.error('There is at least one Homework API key missing')
        raise KeyError('HOMEWORK NAME ERROR', e)
        return {}


def check_tokens():
    """.
    Функция check_tokens() проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    logger = logging.getLogger('check_tokens')
    try:
        if (PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
            logger.info('Tokens are all set')
            return True
        logger.critical('Token value isn\'t set')
        return False
    except NameError:
        logger.critical('Token is missing')
        return False


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger('main')
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        previous_error = None
        while True:
            try:
                response = get_api_answer(current_timestamp)
                logger.info('response was received')
                parse_status(check_response(response))
                logger.info('parsing was completed')
                current_timestamp += RETRY_TIME
                time.sleep(RETRY_TIME)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                if error == previous_error:
                    send_message(bot, message)
                time.sleep(RETRY_TIME)
            else:
                logger.error('test')
    else:
        raise ValueError('There is an issue with the tokens!')


if __name__ == '__main__':
    main()
