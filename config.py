import os
from base64 import b64decode, b64encode
from traceback import format_exc

import machineid
import yaml
from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from loguru import logger
from pydantic import BaseModel


class Config(BaseModel):
    debug: bool = False
    users: dict[str, dict[str, str]] = {}
    courses: dict = {}

    def save(self, config_name: str = "ulearning_config.yaml"):
        """保存配置信息到 YAML 文件"""
        try:
            # 转为字典
            config_dict = self.model_dump()

            # 明文保存
            if self.debug:
                with open(config_name, "w", encoding="utf-8") as f:
                    yaml.dump(config_dict, f, allow_unicode=True)

            # 加密保存
            else:
                config_text = yaml.dump(config_dict, allow_unicode=True)
                encrypted_text = self.encrypt_config(config_text)
                encrypted_config = {"encrypted_config": encrypted_text}

                with open(config_name, "w", encoding="utf-8") as f:
                    yaml.dump(encrypted_config, f, allow_unicode=True)

        except Exception as e:
            logger.error(f"保存配置文件失败: {e}\n{format_exc()}")

    @classmethod
    def load(cls, config_name: str = "ulearning_config.yaml") -> "Config":
        """从 YAML 文件加载配置信息"""
        try:
            # 创建默认配置文件
            if not os.path.exists(config_name):
                return cls.create_default_config(config_name)

            with open(config_name, "r", encoding="utf-8") as f:
                file_content = f.read().strip()

                # 空文件, 创建默认配置文件
                if not file_content:
                    return cls.create_default_config(config_name)

                config_data = yaml.safe_load(file_content)

                # 解密
                if isinstance(config_data, dict) and "encrypted_config" in config_data:
                    encrypted_text = config_data["encrypted_config"]
                    try:
                        decrypted_text = cls.decrypt_config(encrypted_text)
                    except Exception as e:
                        logger.error(f"解密配置文件失败, 可能是跨机器使用")
                        raise

                    config_dict = yaml.safe_load(decrypted_text)

                # 明文
                else:
                    config_dict = config_data

                return cls.model_validate(config_dict)

        except Exception as e:
            logger.error(f"加载配置文件失败, 重新生成配置文件: {e}\n{format_exc()}")
            if os.path.exists(config_name):
                os.remove(config_name)
            return cls.load(config_name)

    @classmethod
    def create_default_config(cls, config_name: str) -> "Config":
        """创建默认配置信息"""
        default_config = cls()
        default_config.save(config_name)
        return default_config

    @staticmethod
    def encrypt_config(text: str) -> str:
        """加密配置文件"""
        data = text.encode("utf-8")
        machine_id = machineid.id()
        client_uuid_bytes = machine_id.replace("-", "").encode("utf-8")
        secret_key = client_uuid_bytes[:16]
        hmac_key = client_uuid_bytes[16:]

        iv = get_random_bytes(AES.block_size)
        cipher = AES.new(secret_key, AES.MODE_CBC, iv)
        padded_data = pad(data, AES.block_size)
        ciphertext = cipher.encrypt(padded_data)

        hmac = HMAC.new(hmac_key, digestmod=SHA256)
        hmac.update(iv + ciphertext)

        encrypted_data = iv + ciphertext + hmac.digest()
        encrypted_text = b64encode(encrypted_data).decode("utf-8")
        return encrypted_text

    @staticmethod
    def decrypt_config(text: str) -> str:
        """解密数据"""
        data = text.encode("utf-8")
        machine_id = machineid.id()
        client_uuid_bytes = machine_id.replace("-", "").encode("utf-8")
        secret_key = client_uuid_bytes[:16]
        hmac_key = client_uuid_bytes[16:]

        data = b64decode(data)
        iv = data[: AES.block_size]
        ciphertext = data[AES.block_size : -32]
        received_hmac = data[-32:]

        hmac = HMAC.new(hmac_key, digestmod=SHA256)
        hmac.update(iv + ciphertext)
        hmac.verify(received_hmac)

        cipher = AES.new(secret_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(ciphertext)

        decrypted_data = unpad(decrypted, AES.block_size)
        decrypted_text = decrypted_data.decode("utf-8")
        return decrypted_text
