import os
from traceback import format_exc

import yaml
from loguru import logger

from models import ConfigModel
from utils import config_text_decrypt, config_text_encrypt


class Config(ConfigModel):
    """配置信息类"""

    def save(self, config_name: str = "ulearning_config.yaml") -> None:
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
                encrypted_text = config_text_encrypt(config_text)
                encrypted_config = {"encrypted_config": encrypted_text}

                with open(config_name, "w", encoding="utf-8") as f:
                    yaml.dump(encrypted_config, f, allow_unicode=True)

        except Exception as e:
            logger.error(f"{format_exc()}\n保存配置文件失败: {e}")

    def reload(self) -> bool:
        """从 YAML 文件重新加载配置信息"""

        try:
            # 读取配置文件
            new_config = self.load()

            # 赋值
            for field_name, field in Config.model_fields.items():
                setattr(self, field_name, getattr(new_config, field_name))

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n加载配置文件失败: {e}")
            return False

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
                        decrypted_text = config_text_decrypt(encrypted_text)
                    except Exception as e:
                        logger.error(f"解密配置文件失败, 可能是跨机器使用")
                        raise

                    config_dict = yaml.safe_load(decrypted_text)

                # 明文
                else:
                    config_dict = config_data

                return cls.model_validate(config_dict)

        except Exception as e:
            logger.error(f"{format_exc()}\n加载配置文件失败, 重新生成配置文件: {e}")
            if os.path.exists(config_name):
                os.remove(config_name)
            return cls.load(config_name)

    @classmethod
    def create_default_config(cls, config_name: str) -> "Config":
        """创建默认配置信息"""

        default_config = cls()
        default_config.save(config_name)
        return default_config
