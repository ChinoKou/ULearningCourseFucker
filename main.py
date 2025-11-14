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
        self.choices = ["进入刷课", "切换账号", "切换站点", "切换 Debug 模式", "退出"]
        self.choices_map = {
            "进入刷课": self.entry_rush_course,
            "切换账号": self.switch_account,
            "切换站点": self.switch_site,
            "切换 Debug 模式": self.debug_mode,
            "退出": lambda: exit(0),
        }
        set_logger(debug=self.config.debug)

    def menu(self):
        while not hasattr(self, "login_api") or not self.login_username:
            logger.info("请先登录")
            if not self.config.users:
                self.switch_site()
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
            logger.info(f"当前站点: {self.config.site}")
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

            is_switch_site = prompt(
                [
                    inquirer.Confirm(
                        name="confirm",
                        message="登录失败, 是否要切换站点?"
                    )
                ]
            )["confirm"]

            if is_switch_site:
                self.switch_site()

    def choose_account(self):
        logger.debug("选择用户")

        while True:
            logger.info(f"当前站点: {self.config.site}")
            username = prompt(
                [
                    inquirer.List(
                        "username",
                        message="请选择用户 (上下箭头 - 切换 | 回车 - 确认)",
                        choices=list(self.config.users.keys())
                        + ["添加新用户", "切换站点"],
                    )
                ]
            )["username"]

            if username == "添加新用户":
                return self.add_account()

            if username == "切换站点":
                self.switch_site()
                return self.choose_account()

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

    def switch_site(self):
        logger.debug("切换站点")

        sites = {
            "主站": {"name": "ulearning", "url": "ulearning.cn"},
            "东莞理工学院": {"name": "dgut", "url": "lms.dgut.edu.cn"},
        }

        while True:
            choice_site = prompt(
                [
                    inquirer.List(
                        name="site",
                        message="请选择站点 (上下箭头 - 切换 | 回车 - 确认)",
                        choices=[k for k, v in sites.items()],
                    )
                ]
            )["site"]

            site_info = sites[choice_site]
            self.config.site = site_info["name"]
            self.config.save()

            if self.login_username:
                if hasattr(self, "login_api"):
                    delattr(self, "login_api")

                login_status = self.force_login(self.login_username)
                if login_status:
                    break

            else:
                break

            logger.warning("站点切换失败")

        logger.info(
            f"设置站点成功, 当前站点为 {site_info["name"]}, 站点地址为 {site_info["url"]}"
        )


class RushCourse:
    def __init__(self, config: Config, client: Client):
        self.config = config
        self.client = client
        self.course = Course(config, client)
        self.choices = [
            "配置刷课",
            "开始刷课",
            "查看刷课信息",
            "修改刷课上报时长",
            "清理已刷完课程",
            "退出刷课",
        ]
        self.choices_map = {
            "配置刷课": self.configure_courses,
            "开始刷课": self.start_rush_course,
            "查看刷课信息": self.print_courses,
            "修改刷课上报时长": self.modify_study_time,
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
        study_time = self.get_study_time()
        if not courses:
            logger.warning("未配置课程信息")
            return

        logger.info("已配置课程信息:")
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
                                logger.info(
                                    f'       [✓] "{page_info["name"]}" (已刷完)'
                                )
                            else:
                                logger.info(
                                    f'       [✕] "{page_info["name"]}" (未刷完)'
                                )

        print("")
        logger.info("已配置的刷课上报时长:")
        for _study_time in study_time:
            logger.info(_study_time)

    def configure_courses(self):
        logger.debug("配置课程")

        courses = self.course.get_courses()

        courses_choices = [
            f"{course_id}: {course_info["name"]}"
            for course_id, course_info in courses.items()
        ]

        course_ids = prompt(
            [
                inquirer.Checkbox(
                    name="course_ids",
                    message="请选择要刷的课程 (上下箭头 - 切换 | 空格 - 选中 | 回车 - 确认)",
                    choices=courses_choices,
                    validate=lambda _, x: x,  # type: ignore
                )
            ]
        )["course_ids"]

        if not course_ids:
            logger.warning("未选择课程")
            return

        # 从选择中提取课程 ID
        course_ids = [int(course_id.split(":")[0]) for course_id in course_ids]

        course_info = {}

        logger.warning("若课件量较大, 获取信息可能需要较长时间, 请耐心等待...")

        self.config.courses.clear()
        self.config.save()

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
                        validate=lambda _, x: x,  # type: ignore
                    )
                ]
            )["textbook_ids"]

            if not textbook_ids:
                logger.warning(f"未选择教材")
                continue

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
        logger.debug("开始刷课")

        try:
            if not self.config.courses:
                logger.warning("未配置课程信息")
                return

            self.course.start_rush_course(self.config.courses)
            logger.success("刷课完成")

        except Exception as e:
            logger.error(f"刷课过程出错: {e}\n{format_exc()}")

    def get_study_time(self) -> list:
        logger.debug("获取已配置的刷课上报时长")

        name = {
            "question": "题目",
            "office": "PPT/Word/PDF",
            "content": "文本",
        }
        current_study_time = self.config.study_time
        return [
            f"{key}-{name[key]} (当前值: {value["min"]}~{value["max"]} 秒)"
            for key, value in current_study_time.items()
        ]

    def modify_study_time(self):
        logger.debug("修改刷课上报时长")

        while True:
            type_choices = self.get_study_time() + ["返回"]

            type_choice = prompt(
                [
                    inquirer.List(
                        name="type_choice",
                        message="请选择要修改的刷课上报时长类型 (上下箭头 - 切换 | 回车 - 确认)",
                        choices=type_choices,
                    )
                ]
            )["type_choice"]
            if type_choice == "返回":
                return

            study_time = prompt(
                [
                    inquirer.Text(
                        name="min",
                        message="请输入 最小 上报时长 (单位: 秒)",
                        validate=lambda _, x: x.isdigit(),
                    ),
                    inquirer.Text(
                        name="max",
                        message="请输入 最大 上报时长 (单位: 秒)",
                        validate=lambda _, x: x.isdigit(),
                    ),
                ]
            )
            element_type = type_choice.split("-")[0]
            element_name = type_choice.split("-")[1].split(" ")[0]

            min_study_time = int(study_time["min"])
            max_study_time = int(study_time["max"])
            if min_study_time > max_study_time:
                logger.warning(
                    f"修改 {element_name} 的学习时长上报范围失败, 最小上报时长不能大于最大上报时长!"
                )
                continue

            self.config.study_time[element_type] = {
                "min": min_study_time,
                "max": max_study_time,
            }
            self.config.save()

            logger.info(
                f"成功修改 {element_name} 的学习时长上报范围: {min_study_time}~{max_study_time} 秒"
            )


if __name__ == "__main__":
    try:
        set_logger()
        logger.info("程序开源地址: https://github.com/ChinoKou/ULearningCourseFucker")
        main = Main()
        main.menu()

    except KeyboardInterrupt as e:
        logger.info("用户强制退出")

    except Exception as e:
        logger.error(f"程序出现未知错误: {e}\n{format_exc()}")

    try:
        logger.info("按回车键退出...")
        input()

    except (KeyboardInterrupt, EOFError):
        pass

    finally:
        exit()
