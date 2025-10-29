import os
from sys import stderr
from time import localtime, strftime

from inquirer import prompt as inquirer_prompt
from loguru import logger


def prompt(data):
    data = inquirer_prompt(data)
    if data is None:
        raise KeyboardInterrupt
    return data


def set_logger(debug=False):
    LOG_DIR = "./ulearning_logs"
    START_TIME = strftime("%Y-%m-%d", localtime())
    if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)
    LOG_FILE_NAME = os.path.join(LOG_DIR, f"{START_TIME}.log")
    log_level = "DEBUG" if debug else "INFO"
    log_format = "<green>{time:MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>"

    logger.remove()
    for sink in [stderr, LOG_FILE_NAME]:
        logger.add(
            sink,
            level=log_level,
            format=log_format,
        )
