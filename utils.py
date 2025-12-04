import os
from base64 import b64decode, b64encode
from sys import stderr
from time import localtime, strftime

import machineid
from Crypto.Cipher import AES, DES
from Crypto.Hash import HMAC, SHA256
from Crypto.Random import get_random_bytes
from Crypto.Util import Padding
from Crypto.Util.Padding import pad, unpad
from loguru import logger
from questionary import Question


async def answer(question: Question):
    """获取用户输入"""

    answer = await question.ask_async()
    if not answer:
        raise KeyboardInterrupt

    return answer


def config_text_encrypt(text: str) -> str:
    """配置文本加密"""

    # 初始化明文和密钥
    data = text.encode("utf-8")
    machine_id = machineid.id()
    client_uuid_bytes = machine_id.replace("-", "").encode("utf-8")
    secret_key = client_uuid_bytes[:16]
    hmac_key = client_uuid_bytes[16:]

    # 加密
    iv = get_random_bytes(AES.block_size)
    cipher = AES.new(secret_key, AES.MODE_CBC, iv)
    padded_data = pad(data, AES.block_size)
    ciphertext = cipher.encrypt(padded_data)

    hmac = HMAC.new(hmac_key, digestmod=SHA256)
    hmac.update(iv + ciphertext)

    # 编码密文
    encrypted_data = iv + ciphertext + hmac.digest()
    encrypted_text = b64encode(encrypted_data).decode("utf-8")
    return encrypted_text


def config_text_decrypt(text: str) -> str:
    """配置文本解密"""

    # 初始化密文和密钥
    data = text.encode("utf-8")
    machine_id = machineid.id()
    client_uuid_bytes = machine_id.replace("-", "").encode("utf-8")
    secret_key = client_uuid_bytes[:16]
    hmac_key = client_uuid_bytes[16:]

    # 解码密文
    data = b64decode(data)
    iv = data[: AES.block_size]
    ciphertext = data[AES.block_size : -32]
    received_hmac = data[-32:]

    # 解密
    hmac = HMAC.new(hmac_key, digestmod=SHA256)
    hmac.update(iv + ciphertext)
    hmac.verify(received_hmac)

    cipher = AES.new(secret_key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    decrypted_data = unpad(decrypted, AES.block_size)
    decrypted_text = decrypted_data.decode("utf-8")
    return decrypted_text


def sync_text_encrypt(text: str) -> str:
    """sync接口文本加密"""

    # 初始化明文与密钥
    key = b"12345678"  # 前端逆向分析后得到
    data = text.encode("utf-8")

    # 创建 DES 加密对象
    cipher = DES.new(key, DES.MODE_ECB)

    # 填充数据并加密
    padded_data = Padding.pad(data, DES.block_size)
    encrypted_data = cipher.encrypt(padded_data)

    # Base64 编码
    encoded_data = b64encode(encrypted_data)
    encoded_text = encoded_data.decode("utf-8")

    return encoded_text


def sync_text_decrypt(text: str) -> str:
    """sync接口文本解密"""

    # 初始化密文与密钥
    key = b"12345678"
    data = b64decode(text.encode("utf-8"))

    # 创建 DES 解密对象
    cipher = DES.new(key, DES.MODE_ECB)

    # 解密数据并去除填充
    decrypted_data = cipher.decrypt(data)
    unpadded_data = Padding.unpad(decrypted_data, DES.block_size)

    # 解码数据
    decoded_text = unpadded_data.decode("utf-8")

    return decoded_text


def set_logger(debug=False, dir_name: str = "ulearning_logs") -> None:
    """设置日志"""

    # 创建日志目录
    log_dir = os.path.join(os.getcwd(), dir_name)
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)

    # 初始化日志配置
    start_time = strftime("%Y-%m-%d_%H-%M-%S", localtime())
    log_file = os.path.join(log_dir, f"{start_time}.log")
    log_level = "DEBUG" if debug else "INFO"
    log_format = "<green>{time:MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>"

    # 修改日志配置
    logger.remove()
    for sink, level in {stderr: log_level, log_file: "DEBUG"}.items():
        logger.add(sink=sink, level=level, format=log_format)
