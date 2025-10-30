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
        self.client: Client
        self.login_api: Login
        self.login_username: str = ""
        self.choices = ["进入刷课", "切换账号", "切换 Debug 模式", "退出"]
        self.choices_map = {
            "进入刷课": self.entry_rush_course,
            "切换账号": self.switch_account,
            "切换 Debug 模式": self.debug_mode,
            "退出": lambda: exit(0),
        }
        set_logger(debug=self.config.debug)

    def menu(self):
        while not hasattr(self, "login_api") or not hasattr(self, "login_username"):
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
                        message="请选择 (上下箭头 - 切换 | 回车 - 确认)",
                        choices=self.choices,
                    )
                ]
            )
            self.choices_map[choice["choice"]]()

    def create_client(self):
        logger.debug("创建 HTTP 客户端")
        client = Client(verify=not self.config.debug)
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

        logger.success("登录成功")
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
                        message="请选择用户 (上下箭头 - 切换 | 回车 - 确认)",
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
        choice = prompt(
            [
                inquirer.List(
                    name="choice",
                    message="请选择 Debug 模式 (上下箭头 - 切换 | 回车 - 确认)",
                    choices=["开启", "关闭", "取消"],
                )
            ]
        )["choice"]
        if (
            choice == "开启"
            and prompt(
                [
                    inquirer.Confirm(
                        name="confirm", message="是否要开启 Debug 模式?", default=False
                    )
                ]
            )["confirm"]
        ):
            self.config.debug = True
            self.config.save()
            set_logger(True)
            logger.debug("开启 Debug 模式")

        elif choice == "关闭":
            self.config.debug = False
            self.config.save()
            set_logger(False)
            logger.debug("关闭 Debug 模式")

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
        self.choices_map = {
            "配置刷课": self.configure_courses,
            "开始刷课": self.start_rush_course,
            "查看刷课信息": self.print_courses,
            "清理已刷完课程": self.prune_courses,
            "退出刷课": lambda: None,
            "解密": self.decrypt_text,
        }

        if self.config.debug:
            self.choices.extend(["解密"])

    def menu(self):
        try:
            while True:
                choice = prompt(
                    [
                        inquirer.List(
                            name="choice",
                            message="请选择 (上下箭头 - 切换 | 回车 - 确认)",
                            choices=self.choices,
                        )
                    ]
                )["choice"]

                if choice == "退出刷课":
                    break

                self.choices_map[choice]()

        except KeyboardInterrupt as e:
            logger.info("用户强制退出刷课")
            return

        except Exception as e:
            logger.error(f"未知错误: {e}\n{format_exc()}")

    def prune_courses(self, refresh: bool = True):
        logger.debug("清理已刷完课程")

        if not self.config.courses:
            logger.warning("未配置课程信息")
            return

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
        if not courses:
            logger.warning("未配置课程信息")
            return

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
            logger.warning("未选择课程")
            return

        course_ids = prompt(
            [
                inquirer.Checkbox(
                    name="course_ids",
                    message="请选择要刷的课程 (上下箭头 - 切换 | 空格 - 选中 | 回车 - 确认)",
                    choices=courses_choices,
                )
            ]
        )["course_ids"]

        # 从选择中提取课程 ID
        course_ids = [int(course_id.split(":")[0]) for course_id in course_ids]

        course_info = {}

        logger.warning("若课件量较大, 获取信息可能需要较长时间, 请耐心等待...")

        self.config.courses.clear()

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
                logger.warning(f'"{courses[course_id]["name"]}" 无课件可选择')
                continue

            textbook_ids = prompt(
                [
                    inquirer.Checkbox(
                        name="textbook_ids",
                        message="请选择要刷的教材 (上下箭头 - 切换 | 空格 - 选中 | 回车 - 确认)",
                        choices=textbooks_choices,
                    )
                ]
            )["textbook_ids"]

            # 从选择中提取教材 ID
            textbook_ids = [
                int(textbook_id.split(":")[0]) for textbook_id in textbook_ids
            ]

            course_info[course_id]["textbooks"] = {}
            for textbook_id in textbook_ids:
                textbook_info = self.course.append_record_info(textbooks[textbook_id])
                course_info[course_id]["textbooks"][textbook_id] = textbook_info

            self.config.courses.update(course_info)
            self.config.save()

        self.print_courses()

    def decrypt_text(self):
        encrypted_text = prompt(
            [
                inquirer.Text(
                    "encrypted_text",
                    message="请输入加密后的文本",
                    validate=lambda _, x: len(x) > 0,
                )
            ]
        )["encrypted_text"]
        print(self.course.sync_data_decrypt(encrypted_text))

    def start_rush_course(self):
        try:
            if not self.config.courses:
                logger.warning("未配置课程信息")
                return

            self.course.start_rush_course(self.config.courses)
            logger.success("刷课完成")

        except Exception as e:
            logger.error(f"刷课过程出错: {e}\n{format_exc()}")


if __name__ == "__main__":
    try:
        set_logger()
        main = Main()
        main.menu()

    except KeyboardInterrupt as e:
        logger.info("用户强制退出")

    except Exception as e:
        logger.error(format_exc())

    try:
        logger.info("按回车键退出...")
        input()

    except KeyboardInterrupt:
        pass

    finally:
        exit()
