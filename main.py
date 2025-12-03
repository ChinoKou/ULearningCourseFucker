import asyncio
from collections.abc import Callable
from sys import exit
from traceback import format_exc
from typing import TYPE_CHECKING

import questionary
from loguru import logger

from config import Config
from services import ConfigManager, CourseManager, UserManager
from utils import answer, set_logger

if TYPE_CHECKING:
    from services import HttpClient


class Main:
    def __init__(self) -> None:
        self.config: Config = Config.load()
        self.active_client: "HttpClient | None" = None
        self.user_manager: UserManager = UserManager(self.config)
        self.choices: list[str] = [
            "进入课件管理",
            "进入账户管理",
            "进入配置管理",
            "退出",
        ]
        self.choices_map: dict[str, Callable] = {
            "进入课件管理": self.enter_course_manager,
            "进入账户管理": self.enter_user_manager,
            "进入配置管理": self.enter_config_manager,
            "退出": lambda: None,
        }
        set_logger(debug=self.config.debug)

    async def menu(self) -> None:
        """主菜单"""
        logger.debug("进入主菜单")

        while True:
            if not await self.user_manager.check_login_status():
                continue

            if not self.active_client:
                self.active_client = await self.user_manager.get_client()

            logger.info(f"当前用户: '{self.config.active_user}'")

            choice = await answer(
                questionary.select(
                    message="请选择 (上下箭头 - 切换 | 回车 - 确认)",
                    choices=self.choices,
                )
            )
            if choice == "退出":
                exit(0)

            await self.choices_map[choice]()

    async def enter_course_manager(self) -> None:
        """进入课件管理"""
        if not self.active_client:
            logger.error("未登录")
            return

        course_manager = CourseManager(
            self.config.active_user, self.config, self.active_client
        )
        await course_manager.menu()

    async def enter_user_manager(self) -> None:
        """进入账户管理"""
        await self.user_manager.menu()

    async def enter_config_manager(self) -> None:
        """进入配置管理"""
        if not self.active_client:
            logger.error("未登录")
            return

        config_manager = ConfigManager(self.config, self.active_client)
        await config_manager.menu()


if __name__ == "__main__":
    try:
        set_logger()
        logger.info("程序开源地址: https://github.com/ChinoKou/ULearningCourseFucker")
        main = Main()
        asyncio.run(main.menu())

    except KeyboardInterrupt as e:
        logger.info("用户强制退出")

    except Exception as e:
        logger.error(f"{format_exc()}\n程序出现未知错误: {e}")

    try:
        logger.info("按回车键退出...")
        input()

    except (KeyboardInterrupt, EOFError):
        pass

    finally:
        exit()
