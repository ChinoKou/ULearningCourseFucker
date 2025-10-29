import time
from sys import exit

import inquirer
from httpx import Client
from loguru import logger

from api import *
from config import *
from utils import *


class Main:
    def __init__(self):
        self.config: Config = Config.load()
        self.client: Client = None
        self.login_api: Login = None
        self.login_username: str = ""
        self.choices = ["进入刷课", "切换账号", "开启 Debug 模式", "退出"]
        self.choices_map = {
            "进入刷课": self.entry_rush_course,
            "切换账号": self.switch_account,
            "开启 Debug 模式": self.debug_mode,
            "退出": lambda: exit(0),
        }

    def menu(self):
        while not self.login_api or not self.login_username:
            logger.info("请先登录")
            if not self.config.users:
                self.add_account()
            else:
                self.choose_account()

        while True:
            if not self.force_login(only_check=True):
                logger.error("登录失败, 请重新选择账号")
                self.choose_account()
                continue

            logger.info(f"当前用户: {self.login_username}")

            choice = prompt(
                [
                    inquirer.List(
                        "choice",
                        message="请选择",
                        choices=self.choices,
                    )
                ]
            )
            self.choices_map[choice["choice"]]()

    def create_client(self):
        logger.debug("创建 HTTP 客户端")
        client = Client()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
            "Authorization": self.config.users[self.login_username]["token"],
        }
        client.headers.update(headers)
        self.client = client

    def force_login(self, username: str = "", only_check: bool = False) -> bool:
        logger.debug("强制登录")

        if only_check and self.login_api.check_login_status():
            return True

        if username:
            self.login_api = Login(self.config, username)

        retry = 0

        while not self.login_api.check_login_status():
            if not self.login_api.login():
                logger.warning("执行登录并获取 Token 失败, 请检查账号信息是否正确")
                retry += 1
                if retry >= 3:
                    logger.error("重试次数过多, 请检查账号信息是否正确")
                    return False
                time.sleep(2)

        logger.info("登录成功")
        self.login_username = username if username else self.login_username
        self.create_client()

        return True

    def add_account(self):
        logger.debug("添加账号")
        while True:
            user_info = prompt(
                [
                    inquirer.Text(
                        "username",
                        message="请输入用户名",
                        validate=lambda _, x: len(x) > 0,
                    ),
                    inquirer.Password(
                        "password",
                        message="请输入密码",
                        validate=lambda _, x: len(x) > 0,
                    ),
                ]
            )
            self.config.users[user_info["username"]] = {
                "username": user_info["username"],
                "password": user_info["password"],
                "token": "A",  # 占位符
            }

            login_status = self.force_login(user_info["username"])
            if login_status:
                break

    def choose_account(self):
        logger.debug("选择用户")
        while True:
            username = prompt(
                [
                    inquirer.List(
                        "username",
                        message="请选择用户",
                        choices=list(self.config.users.keys()) + ["添加新用户"],
                    )
                ]
            )["username"]

            if username == "添加新用户":
                return self.add_account()

            login_status = self.force_login(username)
            if login_status:
                break

    def switch_account(self):
        self.choose_account()
        if self.config.courses:
            logger.warning("用户已切换, 已配置课程有可能会有出入")

    def entry_rush_course(self):
        logger.debug("进入刷课")
        rush_course = RushCourse(self.config, self.client)
        return rush_course.menu()

    def debug_mode(self):
        logger.warning("请确保你知道 Debug 模式的作用再开启!")
        if prompt(
            [
                inquirer.Confirm(
                    name="confirm", message="是否要开启 Debug 模式?", default=False
                )
            ]
        )["confirm"]:
            set_logger(True)
            logger.debug("开启 Debug 模式")
        else:
            logger.info("取消")


class RushCourse:
    def __init__(self, config: Config, client: Client):
        self.config = config
        self.client = client
        self.course = Course(client)
        self.choices = [
            "配置刷课",
            "开始刷课",
            "查看刷课信息",
            "清理已刷完课程",
            "退出刷课",
        ]

    def menu(self):
        while True:
            choice = prompt(
                [inquirer.List(name="choice", message="请选择", choices=self.choices)]
            )["choice"]
            if choice == "配置刷课":
                self.configure_courses()
            elif choice == "开始刷课":
                self.course.start_rush_course(self.config.courses)
            elif choice == "查看刷课信息":
                self.print_courses()
            elif choice == "清理已刷完课程":
                self.prune_courses(refresh=True)
            elif choice == "退出刷课":
                return

    def prune_courses(self, refresh: bool = False):
        logger.debug("清理已刷完课程")

        if refresh:
            logger.info("重新获取学习记录信息")
            for course_id, course_info in dict(self.config.courses).items():
                textbooks: dict = course_info.get("textbooks", {})
                for textbook_id, textbook_info in dict(textbooks).items():
                    modify_textbook_info = self.course.append_record_info(textbook_info)
                    course_info["textbooks"][textbook_id] = modify_textbook_info

                self.config.courses[course_id] = course_info
                self.config.save()

        courses = dict(self.config.courses)
        for course_id, course_info in dict(courses).items():
            textbooks: dict = course_info.get("textbooks", {})
            for textbook_id, textbook_info in dict(textbooks).items():
                chapters: dict = textbook_info.get("chapters", {})
                for chapter_id, chapter_info in dict(chapters).items():
                    items: dict = chapter_info.get("items", {})
                    for item_id, item_info in dict(items).items():
                        pages: dict = item_info.get("pages", {})
                        for page_id, page_info in dict(pages).items():
                            complete_status = page_info["is_complete"]
                            if complete_status:
                                pages.pop(page_id)
                                logger.info(
                                    f'[页面][{page_id}] 已刷完, 移除 "{page_info["name"]}"'
                                )
                        if not pages:
                            items.pop(item_id)
                            logger.info(
                                f'[项目][{item_id}] 已刷完, 移除 "{item_info["name"]}"'
                            )
                    if not items:
                        chapters.pop(chapter_id)
                        logger.info(
                            f'[章节][{chapter_id}] 已刷完, 移除 "{chapter_info["name"]}"'
                        )
                if not chapters:
                    textbooks.pop(textbook_id)
                    logger.info(
                        f'[教材][{textbook_id}] 已刷完, 移除 "{textbook_info["name"]}"'
                    )
            if not textbooks:
                courses.pop(course_id)
                logger.info(f'[课程][{course_id}] 已刷完, 移除 "{course_info["name"]}"')

        self.config.courses = courses
        self.config.save()
        self.print_courses()

    def print_courses(self):
        logger.debug("打印课程信息")
        courses = self.config.courses
        for course_id, course_info in courses.items():
            logger.info(f'课程: "{course_info["name"]}"')
            textbooks: dict = course_info.get("textbooks", {})
            for textbook_id, textbook_info in textbooks.items():
                logger.info(f' 教材: "{textbook_info["name"]}"')
                chapters: dict = textbook_info.get("chapters", {})
                for chapter_id, chapter_info in chapters.items():
                    logger.info(f'   章节: "{chapter_info["name"]}"')
                    items: dict = chapter_info.get("items", {})
                    for item_id, item_info in items.items():
                        logger.info(f'     项目: "{item_info["name"]}"')
                        pages: dict = item_info.get("pages", {})
                        for page_id, page_info in pages.items():
                            complete_status = page_info["is_complete"]
                            if complete_status:
                                logger.info(f'       [✓] "{page_info["name"]}"')
                            else:
                                logger.info(f'       [✕] "{page_info["name"]}"')

    def configure_courses(self):
        logger.debug("配置课程")

        courses = self.course.get_courses()

        courses_choices = [
            f"{course_id}: {course_info["name"]}"
            for course_id, course_info in courses.items()
        ]
        if not courses_choices:
            return

        course_ids = prompt(
            [
                inquirer.Checkbox(
                    name="course_ids",
                    message="请选择要刷的课程",
                    choices=courses_choices,
                )
            ]
        )["course_ids"]

        # 从选择中提取课程 ID
        course_ids = [int(course_id.split(":")[0]) for course_id in course_ids]

        course_info = {}

        logger.warning("若课件量较大, 获取信息可能需要较长时间, 请耐心等待...")

        textbooks = {}
        for course_id in course_ids:
            course_info[course_id] = courses[course_id]
            textbooks = self.course.get_textbooks(
                course_id, courses[course_id]["class_id"]
            )

        textbooks_choices = [
            f"{textbook_id}: {textbook_info["name"]}"
            for textbook_id, textbook_info in textbooks.items()
        ]
        if not textbooks_choices:
            return

        textbook_ids = prompt(
            [
                inquirer.Checkbox(
                    name="textbook_ids",
                    message="请选择要刷的教材",
                    choices=textbooks_choices,
                )
            ]
        )["textbook_ids"]

        # 从选择中提取教材 ID
        textbook_ids = [int(textbook_id.split(":")[0]) for textbook_id in textbook_ids]

        course_info[course_id]["textbooks"] = {}
        for textbook_id in textbook_ids:
            textbook_info = self.course.append_record_info(textbooks[textbook_id])
            course_info[course_id]["textbooks"][textbook_id] = textbook_info

        self.config.courses = course_info
        self.config.save()

        self.print_courses()


if __name__ == "__main__":
    set_logger()
    main = Main()
    main.menu()
