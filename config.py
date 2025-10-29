import os

from pydantic import BaseModel


class Config(BaseModel):
    debug: bool = False
    users: dict[str, dict[str, str]] = {}
    courses: dict = {}

    def save(self, path: str = "ulearning.json"):
        """保存配置到 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load(cls, path: str = "ulearning.json") -> "Config":
        """从 JSON 文件加载配置"""
        if not os.path.exists(path):
            default_config = cls()
            default_config.save(path)
            return default_config

        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
