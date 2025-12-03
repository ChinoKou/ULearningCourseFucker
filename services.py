import asyncio
import json
import random
import time
from collections.abc import Callable
from traceback import format_exc
from typing import TYPE_CHECKING

import httpx
import questionary
from loguru import logger

from api import CourseAPI, GeneralAPI, LoginAPI
from models import (
    ChapterInfoAPIResponse,
    ConfigModel,
    CourseListAPIResponse,
    CourseWareChapter,
    CourseWarePage,
    CourseWareSection,
    ElementContent,
    ElementDocumen,
    ElementQuestion,
    ElementVideo,
    GeneralAPIUserInfoAPIResponse,
    ModelCourse,
    ModelTextbook,
    StudyRecordAPIResponse,
    SyncStudyRecordAPIRequest,
    TextbookInfoAPIResponse,
    TextbookListAPIResponse,
    UserAPI,
    UserConfig,
)
from utils import answer, set_logger, sync_text_decrypt

if TYPE_CHECKING:
    from config import Config


class HttpClient:
    def __init__(
        self, token: str = "a", cookies: dict = {}, debug: bool = False
    ) -> None:
        self.debug = debug
        self.__client = httpx.AsyncClient(verify=not self.debug)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
        }
        if token != "a":
            headers["Authorization"] = token

        self.__client.headers.update(headers)
        self.__client.cookies.update(cookies)

    async def get(
        self, url: str, params: dict | None = None, timeout: int = 15, retry: int = 0
    ) -> httpx.Response | None:
        """
        发送GET请求

        :param url: 请求的URL
        :type url: str
        :param params: 请求头的Params
        :type params: dict | None
        :param timeout: 请求超时时间
        :type timeout: int
        :param retry: 递归调用重试次数
        :type retry: int
        :return: 响应体
        :rtype: Response | None
        """
        logger.debug(f"GET: {url}")

        try:
            return await self.__client.get(url, params=params, timeout=timeout)

        except httpx.TransportError as e:
            logger.error(f"网络错误: {e}")
            if retry >= 3:
                logger.error("请求重试次数过多")
                return None

            await asyncio.sleep(0.5)
            logger.info("正在重试...")
            return await self.get(url, params=params, timeout=timeout, retry=retry + 1)

        except Exception as e:
            logger.error(f"{format_exc()}\n请求失败: {e}")
            return None

    async def post(
        self,
        url: str,
        content: str | None = None,
        params: dict | None = None,
        json: dict | None = None,
        data: dict | None = None,
        timeout: int = 15,
        retry: int = 0,
    ) -> httpx.Response | None:
        """
        发送POST请求

        :param url: 请求的URL
        :type url: str
        :param content: 请求体的内容
        :type content: str | None
        :param params: 请求头的Params
        :type params: dict | None
        :param json: 请求体的JSON数据
        :type json: dict | None
        :param data: 请求体的urlencoded数据
        :type data: dict | None
        :param timeout: 请求超时时间
        :type timeout: int
        :param retry: 递归调用重试次数
        :type retry: int
        :return: 响应体
        :rtype: Response | None
        """
        logger.debug(f"POST: {url}")

        try:
            return await self.__client.post(
                url=url,
                content=content,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
            )

        except httpx.TransportError as e:
            logger.error(f"网络错误: {e}")
            if retry >= 3:
                logger.error("请求重试次数过多")
                return None

            await asyncio.sleep(0.5)
            logger.info("正在重试...")
            return await self.post(
                url=url,
                content=content,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
                retry=retry + 1,
            )

        except Exception as e:
            logger.error(f"{format_exc()}\n请求失败: {e}")
            return None

    def set_token(self, token: str) -> bool:
        """
        设置token

        :param token: 鉴权令牌
        :type token: str
        :return: 是否设置成功
        :rtype: bool

        """
        logger.debug(f"设置token")

        try:
            # 更新客户端请求头的Authorization属性
            self.__client.headers.update({"Authorization": token})
            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n设置token失败: {e}")
            return False

    def set_cookies(self, cookies: dict) -> bool:
        """
        设置cookies

        :param cookies: Cookies字典对象
        :type cookies: dict
        :return: 是否设置成功
        :rtype: bool

        """
        logger.debug("设置cookies")

        try:
            # 更新客户端的Cookie
            self.__client.cookies.update(cookies)
            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n设置cookies失败: {e}")
            return False

    def get_cookies(self) -> dict:
        """
        获取cookies

        :return: Cookies字典对象
        :rtype: dict[Any, Any]

        """
        logger.debug("获取cookies")

        try:
            # 获取内部客户端的Cookie
            return dict(self.__client.cookies)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取cookies失败: {e}")
            return {}

    def copy_client(self) -> "HttpClient | None":
        """
        复制Http客户端

        :return: HttpClient对象
        :rtype: HttpClient | None
        """
        logger.debug("复制Http客户端")

        try:
            # 获取当前鉴权令牌
            token = self.__client.headers.get("Authorization")

            # 创建新的HttpClient
            new_http_client = HttpClient(
                token=token, cookies=self.get_cookies(), debug=self.debug
            )
            return new_http_client

        except Exception as e:
            logger.error(f"{format_exc()}\n复制Http客户端失败: {e}")
            return None

    async def re_create_client(
        self, token: str = "a", cookies: dict = {}, debug: bool = False
    ) -> bool:
        """
        重新创建内部Http客户端

        :param token: 鉴权令牌
        :type token: str
        :param cookies: Cookies字典对象
        :type cookies: dict
        :param debug: 是否为调试模式
        :type debug: bool
        :return: 是否重新创建成功
        :rtype: bool

        """
        logger.debug("重新创建内部Http客户端")

        try:
            # 创建新的内部客户端AsyncClient
            new_client = httpx.AsyncClient(verify=not debug)

            # 初始化请求头和Cookie
            if token != "a":
                self.__client.headers.update({"Authorization": token})

            new_client.headers.update(self.__client.headers)
            new_client.cookies.update(self.__client.cookies)

            if cookies:
                new_client.cookies.update(cookies)

            # 关闭旧的内部客户端并替换为新的内部客户端
            await self.__client.aclose()
            self.__client = new_client

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n重新创建内部Http客户端失败: {e}")
            return False


class UserManager:
    def __init__(self, config: "Config") -> None:
        self.config: "Config" = config
        self.active_client: HttpClient
        self.users: dict[str, UserAPI] = {}
        self.sites: dict[str, dict[str, str]] = {
            "主站": {"name": "ulearning", "url": "ulearning.cn"},
            "东莞理工学院": {"name": "dgut", "url": "lms.dgut.edu.cn"},
        }

    async def menu(self) -> None:
        """用户管理菜单"""
        logger.debug("进入用户管理菜单")
        choices: list[str] = [
            "添加用户",
            "切换用户",
            "删除用户",
            "修改用户信息",
            "刷新登录状态",
            "检查登录状态",
            "返回",
        ]
        choices_map: dict[str, Callable] = {
            "添加用户": self.__add_user,
            "切换用户": self.__switch_user,
            "删除用户": self.__remove_user,
            "修改用户信息": self.__modify_user,
            "刷新登录状态": self.refresh_login_status,
            "检查登录状态": self.check_login_status,
            "返回": lambda: None,
        }

        try:
            while True:
                # retry = 0
                # while not await self.check_login_status():
                #     login_status = await self.refresh_login_status()
                #     if login_status:
                #         break
                #     if retry >= 3:
                #         logger.error("登录状态检查失败，请检查网络")
                #         return

                #     retry += 1

                choice = await answer(questionary.select("请选择", choices=choices))

                if choice == "返回":
                    return None

                await choices_map[choice]()

        except KeyboardInterrupt as e:
            logger.info("强制退出用户管理")
            return None

        except Exception as e:
            logger.error(f"{format_exc()}\n用户管理出现异常: {e}")
            return None

    async def __login(self, user_config: UserConfig) -> bool:
        """登录"""
        logger.debug(f"登录用户: {user_config.username}")

        try:
            # 创建Http客户端
            http_client = HttpClient(debug=self.config.debug)

            # 设置Cookie
            if user_config.cookies:
                http_client.set_cookies(cookies=user_config.cookies)

            # 设置Token
            if user_config.token != "a":
                http_client.set_token(token=user_config.token)

            # 创建登录API
            login_api = LoginAPI(
                username=user_config.username, config=self.config, client=http_client
            )

            # 检查登录状态
            if await login_api.check_login_status():
                # 设置活跃用户和Http客户端
                self.config.active_user = user_config.username
                self.config.save()
                # copy_client = http_client.copy_client()
                # if not copy_client:
                #     raise
                # self.active_client = copy_client
                self.active_client = http_client

                # 设置用户API
                self.users[user_config.username] = UserAPI(
                    user_config=user_config, login_api=login_api
                )
                return True

            # 登录
            user_info_resp = await login_api.login()

            # 保存用户信息
            if user_info_resp:
                # 设置活跃用户和Http客户端
                self.config.active_user = user_config.username
                # copy_client = http_client.copy_client()
                # if not copy_client:
                #     raise
                # self.active_client = copy_client
                self.active_client = http_client

                # # 创建用户信息
                # user_info = UserInfo(
                #     login_name=user_info_resp.loginName,
                #     user_id=user_info_resp.userId,
                #     token=user_info_resp.authorization,
                #     student_id=user_info_resp.studentId,
                #     name=user_info_resp.name,
                # )

                # 设置用户API
                self.users[user_config.username] = UserAPI(
                    user_config=user_config,
                    login_api=login_api,
                    # user_info=user_info,
                )

                # 保存用户信息
                cookies = http_client.get_cookies()
                user_config.cookies = cookies
                # user_config.token = user_info.token
                user_config.token = user_info_resp.authorization
                # self.config.users[user_config.username] = user_config
                self.config.active_user = user_config.username
                self.config.save()

                logger.success(f"登录成功: {user_config.username}")

                return True

            else:
                logger.error("登录失败")

            return False

        except Exception as e:
            logger.error(f"{format_exc()}\n登录失败: {e}")
            return False

    async def __add_user(self) -> bool:
        """添加账号"""
        logger.debug("添加账号")

        try:
            while True:
                # 获取站点和用户名
                site: str = await answer(
                    questionary.select(
                        message="请选择站点", choices=[k for k, v in self.sites.items()]
                    )
                )
                username: str = await answer(
                    questionary.text(
                        message="请输入用户名",
                        validate=lambda x: len(x) > 0 or "用户名不可为空",
                    )
                )

                # 覆盖确认
                if username in self.config.users:
                    if not await answer(
                        questionary.confirm(
                            message="用户已存在, 是否覆盖?", default=False
                        )
                    ):
                        break

                # 获取密码
                password: str = await answer(
                    questionary.password(
                        message="请输入密码",
                        validate=lambda x: len(x) > 0 or "密码不可为空",
                    )
                )

                # 初始化用户配置信息实例
                user_config = UserConfig(
                    username=username, password=password, site=self.sites[site]["name"]
                )

                self.config.users[user_config.username] = user_config

                retry = 0
                while True:
                    # 登录
                    if await self.__login(user_config=user_config):
                        return True

                    if retry >= 3:
                        break

                    retry += 1

                self.config.users.pop(user_config.username)

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n添加用户失败: {e}")
            return False

    async def __remove_user(self) -> bool:
        logger.debug("删除账号")

        try:
            while True:
                # 初始化用户选择
                username_choices = [k for k, v in self.config.users.items()]
                username_choices.remove(self.config.active_user)
                username_choices.append("返回")

                # 获取用户选择
                username: str = await answer(
                    questionary.select(
                        message="请选择要删除的账号",
                        choices=username_choices,
                    )
                )

                if username == "返回":
                    return True

                if username == self.config.active_user:
                    logger.warning("不允许删除当前登录的账号")
                    continue

                # 删除用户信息
                self.config.users.pop(username)
                self.config.save()

                if username in self.users:
                    self.users.pop(username)

        except Exception as e:
            logger.error(f"{format_exc()}\n删除用户失败: {e}")
            return False

    async def __switch_user(self) -> bool:
        logger.debug("选择用户")

        try:
            while True:
                # 获取用户选择
                username: str = await answer(
                    questionary.select(
                        message="请选择用户",
                        choices=[k for k, v in self.config.users.items()]
                        + ["添加新账号", "返回"],
                    )
                )

                if username == "添加新账号":
                    return await self.__add_user()

                if username == "返回":
                    return False

                user = self.config.users[username]
                if await self.__login(user):
                    break

                logger.warning("登录失败")

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n选择用户失败: {e}")
            return False

    async def __modify_user(self) -> bool:
        logger.debug("修改用户信息")

        try:
            while True:
                # 获取用户选择
                username: str = await answer(
                    questionary.select(
                        message="请选择要修改的用户",
                        choices=[k for k, v in self.config.users.items()] + ["返回"],
                    )
                )

                if username == "返回":
                    break

                # 获取 UserConfig 实例
                user = self.config.users[username]

                while True:
                    # 初始化属性选择
                    attr_choices = []
                    for field_name, field_info in UserConfig.model_fields.items():
                        if (
                            field_name == "token"
                            or field_name == "cookies"
                            or field_name == "courses"
                        ):
                            continue

                        attr_choices.append(
                            f"{field_name}: {field_info.title} (当前值: {getattr(user, field_name)})"
                        )
                    attr_choices.append("返回")

                    # 获取属性选择
                    attr: str = await answer(
                        questionary.select(
                            message="请选择要修改的属性",
                            choices=attr_choices,
                        )
                    )
                    if attr == "返回":
                        break

                    attr_name = attr.split(":")[0].strip()

                    # 获取属性值
                    attr_value = questionary.text(
                        message=f"请输入属性 {attr_name} 的值",
                        validate=lambda x: x or "属性值不可为空",
                    )

                    # 设置属性值
                    setattr(user, attr_name, attr_value)
                    user.token = "a"
                    user.cookies.clear()

                    if await self.__login(user):
                        logger.success(f"成功修改属性 {attr_name} 的值为 {attr_value}")

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n修改用户信息失败: {e}")
            return False

    async def refresh_login_status(self) -> bool:
        """刷新登录状态"""
        logger.debug("刷新登录状态")

        try:
            return await self.__login(self.config.users[self.config.active_user])

        except Exception as e:
            logger.error(f"{format_exc()}\n刷新登录状态失败: {e}")
            return False

    async def check_login_status(self) -> bool:
        """检查登录状态"""
        logger.debug("检查登录状态")

        try:
            if self.config.active_user in self.users:

                login_api = self.users[self.config.active_user].login_api
                if not login_api:
                    raise

                login_status = await login_api.check_login_status()
                return login_status

            elif self.config.active_user in self.config.users:
                return await self.refresh_login_status()

            elif not self.config.users:
                return await self.__add_user()

            else:
                return await self.__switch_user()

            return False

        except Exception as e:
            logger.error(f"{format_exc()}\n检查登录状态失败: {e}")
            return False

    async def get_client(self) -> HttpClient | None:
        """获取 HttpClient 对象"""
        logger.debug("获取 HttpClient 对象")

        try:
            if hasattr(self, "active_client") and self.active_client:
                return self.active_client

            return None

        except Exception as e:
            logger.error(f"{format_exc()}\n获取 HttpClient 对象失败: {e}")
            return None


class ConfigManager:
    def __init__(self, config: "Config", client: HttpClient) -> None:
        self.config = config
        self.client = client

    async def menu(self) -> None:
        """配置管理菜单"""
        logger.debug("配置管理菜单")
        choices = ["修改调试模式", "返回"]
        choices_map = {
            "修改调试模式": self.__change_debug_mode,
            "返回": lambda: None,
        }

        try:
            while True:
                choice = await answer(
                    questionary.select(message="请选择", choices=choices)
                )

                if choice == "返回":
                    return None

                await choices_map[choice]()

        except Exception as e:
            logger.error(f"{format_exc()}\n配置管理彩蛋失败: {e}")
            return None

    async def __change_debug_mode(self) -> None:
        """修改调试模式"""
        logger.debug("修改调试模式")

        try:
            choice = await answer(
                questionary.select(
                    message="请选择调试模式",
                    choices=["开启", "关闭", "返回"],
                )
            )
            if choice == "返回":
                return None

            if choice == "开启":
                self.config.debug = True
                self.config.save()
                set_logger(True)
                if not await self.client.re_create_client(debug=True):
                    raise

                logger.success("已开启调试模式")

            elif choice == "关闭":
                self.config.debug = False
                self.config.save()
                set_logger(False)
                if not await self.client.re_create_client(debug=False):
                    raise

                logger.success("已关闭调试模式")

        except Exception as e:
            logger.error(f"{format_exc()}\n修改调试模式失败: {e}")
            return None


class CourseManager:
    def __init__(self, username: str, config: "Config", client: "HttpClient") -> None:
        self.user_config = config.users[username]
        self.config = config
        self.client = client
        self.course_api = CourseAPI(username=username, config=config, client=client)
        self.general_api = GeneralAPI(username=username, config=config, client=client)
        self.data_manager = DataManager()

    async def menu(self) -> None:
        """课程管理菜单"""
        logger.debug("课程管理菜单")
        choices: list[str] = [
            "课件配置",
            "开始刷课",
            "查看刷课信息",
            "修改刷课上报时长",
            "清理已刷完课程",
            "返回",
        ]
        choices_map: dict[str, Callable] = {
            "课件配置": self.__course_ware_config,
            "开始刷课": self.__start_course_ware,
            "查看刷课信息": self.__print_course_ware_info,
            "修改刷课上报时长": self.__modify_study_time,
            "清理已刷完课程": self.__prune_empty_course_ware,
            "解密同步学习记录请求数据": self.__decrypt_sync_study_record_request,
            "返回": lambda: None,
        }

        if self.config.debug:
            choices.append("解密同步学习记录请求数据")

        try:
            while True:
                choice = await answer(
                    questionary.select(message="请选择", choices=choices)
                )

                if choice == "返回":
                    return None

                await choices_map[choice]()

        except KeyboardInterrupt as e:
            logger.info("用户强制退出课程管理")
            return None

        except Exception as e:
            logger.error(f"{format_exc()}\n课程管理菜单出现异常: {e}")
            return None

    async def __course_ware_config(self) -> None:
        """课件配置"""
        logger.debug("课件配置")

        try:
            # 获取用户的课程列表
            courses = await self.course_api.get_courses()
            if not courses:
                return None

            # 生成课程选项 list["[课程ID] 课程名称"]
            course_choices = [
                f"[{course.id}] {course.name}" for course in courses.courseList
            ]

            # 获取用户选择的课程
            raw_selected_course_ids: list[str] = await answer(
                questionary.checkbox(
                    message="请选择要刷的课程",
                    choices=course_choices,
                    validate=lambda x: len(x) > 0 or "不可为空, 请选择",
                )
            )

            selected_course_ids: list[int]

            # 解析选择的课程为课程ID列表
            selected_course_ids = [
                int(course_id.split("]")[0].split("[")[1].strip())
                for course_id in raw_selected_course_ids
            ]

            # 转换课程ID列表为课程信息对象字典
            selected_course_infos: dict[int, CourseListAPIResponse._Course] = {
                course.id: course
                for course in courses.courseList
                if course.id in selected_course_ids
            }

            # 初始化已选择的课程的所有教材列表{课程ID: {教材ID: 教材信息}}
            selected_course_textbook_infos: dict[
                int, dict[int, TextbookListAPIResponse.TextbookInfo]
            ] = {}

            # 解析每个课程的教材
            for (
                selected_course_id,
                selected_course_info,
            ) in selected_course_infos.items():

                # 获取教材
                textbooks = await self.course_api.get_textbooks(
                    course_id=selected_course_id,
                    class_id=selected_course_info.classId,
                )

                if not textbooks:
                    logger.warning(f"课程 {selected_course_info.name} 没有课件")
                    continue

                # 初始化已选择的课程的教材列表
                selected_course_textbook_infos[selected_course_id] = {}
                selected_course_textbooks = selected_course_textbook_infos[
                    selected_course_id
                ]
                # 添加教材信息
                for textbook in textbooks.textbooks:
                    selected_course_textbooks[textbook.courseId] = textbook

            # 生成教材选项
            textbook_choices = [
                f"[{selected_course_infos[course_id].name}] {textbook_id}. {textbook_info.name}"
                for course_id, selected_course_textbook_info in selected_course_textbook_infos.items()
                for textbook_id, textbook_info in selected_course_textbook_info.items()
            ]

            # 获取用户选择的教材
            raw_selected_textbook_ids: list[str] = await answer(
                questionary.checkbox(
                    message="请选择要刷的教材",
                    choices=textbook_choices,
                    validate=lambda x: len(x) > 0 or "不可为空, 请选择",
                )
            )

            # 解析选择的教材为ID列表
            selected_textbook_ids: list[int] = [
                int(textbook_id.split(".")[0].split("]")[1].strip())
                for textbook_id in raw_selected_textbook_ids
            ]

            # 转换教材ID列表为教材信息对象字典
            selected_textbook_infos: dict[int, TextbookListAPIResponse.TextbookInfo] = {
                textbook_id: textbook_info
                for course_id, selected_course_textbook_info in selected_course_textbook_infos.items()
                for textbook_id, textbook_info in selected_course_textbook_info.items()
                if textbook_id in selected_textbook_ids
            }

            # 初始化课件配置对象从已选中的课程中
            course_config: dict[int, ModelCourse] = {
                course_id: ModelCourse(
                    course_id=course_id,
                    course_name=course_info.name,
                    class_id=course_info.classId,
                    class_user_id=course_info.classUserId,
                    textbooks={
                        selected_textbook_id: ModelTextbook(
                            textbook_id=selected_textbook_id,
                            textbook_name=selected_textbook_info.name,
                            status=selected_textbook_info.status,
                            limit=selected_textbook_info.limit,
                        )
                        for selected_textbook_id, selected_textbook_info in selected_textbook_infos.items()
                        if selected_textbook_id
                        in selected_course_textbook_infos[course_id].keys()
                    },
                )
                for course_id, course_info in selected_course_infos.items()
            }

            await self.__complete_course_ware(course_config)

            self.user_config.courses = course_config
            self.config.save()

        except Exception as e:
            logger.error(f"{format_exc()}\n课件配置失败: {e}")
            return None

    async def __complete_course_ware(
        self, course_config: dict[int, ModelCourse]
    ) -> None:
        """获取教材详细信息, 章节信息, 节信息, 答案信息, 视频信息补全课程配置对象"""

        # 遍历课程
        for course_id, course_info in course_config.items():
            # 创建引用
            textbooks = course_info.textbooks

            # 遍历教材
            for textbook_id, textbook_info in textbooks.items():

                # 获取教材信息
                resp_textbook_info = await self.course_api.get_textbook_info(
                    textbook_id=textbook_id, class_id=course_info.class_id
                )

                # 跳过获取失败的教材信息
                if not resp_textbook_info:
                    logger.warning(
                        f"尝试获取教材 '{textbook_info.textbook_name}' 详细信息失败, 跳过"
                    )
                    continue

                # 解析教材信息
                self.data_manager.parse_textbook_info(
                    course_config=course_config[course_id],
                    textbook_info=resp_textbook_info,
                )

                # 创建引用
                chapters = textbook_info.chapters

                # 遍历章节
                for chapter_id, chapter_info in chapters.items():
                    # 获取章节信息
                    resp_chapter_info = await self.course_api.get_chapter_info(
                        chapter_id=chapter_id
                    )

                    # 跳过获取失败的章节信息
                    if not resp_chapter_info:
                        logger.warning(
                            f"尝试获取章节 '{chapter_info.chapter_name}' 详细信息失败, 跳过"
                        )
                        continue

                    # 解析章节信息
                    self.data_manager.parse_chapter_info(
                        course_config=course_config[course_id],
                        textbook_id=textbook_id,
                        chapter_info=resp_chapter_info,
                    )

                    # 创建引用
                    sections = chapter_info.sections

                    # 遍历节
                    for section_id, section_info in sections.items():
                        # 创建引用
                        section_name = section_info.section_name
                        resp_status, resp_study_record_info = (
                            await self.course_api.get_study_record_info(
                                section_id=section_id
                            )
                        )

                        # 跳过获取失败的学习记录
                        if not resp_status:
                            logger.warning(
                                f"尝试获取学习记录 '{section_name}' 失败, 跳过"
                            )
                            continue

                        # 未学习 跳过
                        if not resp_study_record_info:
                            continue

                        # 解析学习记录信息
                        self.data_manager.parse_study_record_info(
                            course_config=course_config[course_id],
                            textbook_id=textbook_id,
                            study_record_info=resp_study_record_info,
                        )

                        # 创建引用
                        pages: dict[int, CourseWarePage] = section_info.pages

                        # 遍历页面
                        for page_id, page_info in pages.items():
                            # 如果页面类型为题目
                            if page_info.page_content_type == 7:
                                elements = page_info.elements

                                # 遍历元素
                                for element_info in elements:
                                    if not isinstance(element_info, ElementQuestion):
                                        raise

                                    # 遍历问题元素的所有问题
                                    for question_info in element_info.questions:
                                        question_id = question_info.question_id

                                        # 获取问题答案列表
                                        resp_question_answer_list = await self.course_api.get_question_answer_list(
                                            question_id=question_id,
                                            parent_id=page_id,
                                        )

                                        # 答案获取失败
                                        if not resp_question_answer_list:
                                            logger.warning(
                                                f"尝试获取问题 ID-{question_id} 答案列表失败"
                                            )
                                            raise

                                        # 补全答案列表
                                        question_info.question_answer_list = (
                                            resp_question_answer_list.correctAnswerList
                                        )

    async def __start_course_ware(self) -> None:
        """开始刷课"""
        logger.debug("开始刷课")

        try:
            if not self.user_config.courses:
                logger.warning("当前用户未配置课程")
                return None

            user_info = await self.general_api.get_user_info()
            if not user_info:
                logger.warning("获取用户信息失败")
                return None

            # 创建引用
            courses = self.user_config.courses
            for course_id, course_info in courses.items():
                # 创建引用
                class_id = course_info.class_id
                textbooks = course_info.textbooks

                for textbook_id, textbook_info in textbooks.items():
                    # 创建引用
                    chapters = textbook_info.chapters

                    for chapter_id, chapter_info in chapters.items():
                        # 创建引用
                        sections = chapter_info.sections

                        for section_id, section_info in sections.items():
                            study_start_time = await self.course_api.initialize_section(
                                section_id=section_id
                            )
                            if not study_start_time:
                                logger.warning(
                                    f"初始化节 '{section_info.section_name}' 失败, 跳过"
                                )
                                continue

                            # 创建引用
                            pages = section_info.pages

                            for page_id, page_info in pages.items():
                                if page_info.page_content_type == 6:
                                    for element_info in page_info.elements:
                                        if not isinstance(element_info, ElementVideo):
                                            continue

                                        video_id = element_info.video_id

                                        watch_status = await self.course_api.watch_video_behavior(
                                            class_id=class_id,
                                            textbook_id=textbook_id,
                                            chapter_id=chapter_id,
                                            video_id=video_id,
                                        )

                                        if not watch_status:
                                            logger.warning(f"上报视频观看行为失败")

                            retry = 0
                            while True:
                                study_record_info = (
                                    self.data_manager.build_sync_study_record_request(
                                        study_start_time=study_start_time,
                                        section_info=section_info,
                                        user_info=user_info,
                                        study_time_config=self.config.study_time,
                                    )
                                )

                                if not study_record_info:
                                    logger.warning(f"构建请求信息失败, 跳过")
                                    break

                                sync_status = await self.course_api.sync_study_record(
                                    study_record_info=study_record_info
                                )

                                if not sync_status:
                                    logger.warning(f"同步学习记录失败")
                                    continue

                                if retry >= 3:
                                    logger.warning(f"尝试重试同步学习记录失败, 跳过")
                                    break

                                retry += 1

        except Exception as e:
            logger.error(f"{format_exc()}\n刷课过程出现异常: {e}")
            return None

    async def __print_course_ware_info(self) -> None:
        """查看刷课信息"""
        logger.debug("查看刷课信息")

        try:
            if not self.user_config.courses:
                logger.warning("当前用户未配置课程")
                return None

            # 创建引用
            courses = self.user_config.courses
            for course_id, course_info in courses.items():
                logger.info(f"课程: {course_info.course_name}")

                # 创建引用
                textbooks = course_info.textbooks

                for textbook_id, textbook_info in textbooks.items():
                    logger.info(f" 教材: {textbook_info.textbook_name}")

                    # 创建引用
                    chapters = textbook_info.chapters

                    for chapter_id, chapter_info in chapters.items():
                        logger.info(f"  章节: {chapter_info.chapter_name}")

                        # 创建引用
                        sections = chapter_info.sections

                        for section_id, section_info in sections.items():
                            logger.info(f"   节: {section_info.section_name}")

                            # 创建引用
                            pages = section_info.pages

                            for page_id, page_info in pages.items():
                                logger.info(f"    页面: {page_info.page_name}")

        except Exception as e:
            logger.error(f"{format_exc()}\n查看刷课信息失败: {e}")
            return None

    async def __modify_study_time(self) -> None:
        """修改刷课上报时长"""
        logger.debug("修改刷课上报时长")

        try:
            study_time = self.config.study_time

        except Exception as e:
            logger.error(f"{format_exc()}\n修改刷课上报时长失败: {e}")
            return None

    async def __prune_empty_course_ware(self) -> None:
        """清理已刷完课程"""
        logger.debug("清理已刷完课程")

        try:
            if not self.user_config.courses:
                logger.warning("当前用户未配置课程")
                return None

            for course_id, course_info in dict(self.user_config.courses).items():
                course_info.prune()

        except Exception as e:
            logger.error(f"{format_exc()}\n清理已刷完课程失败: {e}")
            return None

    async def __decrypt_sync_study_record_request(self) -> None:
        """解密同步学习记录请求数据"""

        try:

            encrypted_text = await answer(
                questionary.text(
                    "请输入: ", validate=lambda x: len(x) > 0 or "请输入内容"
                )
            )

            decrypted_text = sync_text_decrypt(encrypted_text)
            logger.info(
                json.dumps(json.loads(decrypted_text), indent=4, ensure_ascii=False)
            )

        except Exception as e:
            logger.error(f"{format_exc()}\n解密同步学习记录请求数据失败: {e}")


class DataManager:
    def __init__(self) -> None:
        pass

    def parse_textbook_info(
        self, course_config: ModelCourse, textbook_info: TextbookInfoAPIResponse
    ) -> bool:
        """
        解析教材信息

        :param course_config: 课件配置对象
        :type course_config: ModelCourse
        :param textbook_info: 教材信息API响应数据模型
        :type textbook_info: TextbookInfoAPIResponse
        :return: 解析是否成功
        :rtype: bool
        """

        try:
            # 创建引用
            textbook_id = textbook_info.courseid
            course_config_chapters = course_config.textbooks[textbook_id].chapters

            # 遍历该教材的所有章节信息
            for chapter_info in textbook_info.chapters:
                # 创建章节ID和章节名称变量
                chapter_id = chapter_info.nodeid
                chapter_name = chapter_info.nodetitle

                # 初始化配置文件课件章节对象
                course_config_chapters[chapter_id] = CourseWareChapter(
                    chapter_id=chapter_id,
                    chapter_name=chapter_name,
                )

                # 创建引用
                course_config_sections = course_config_chapters[chapter_id].sections

                # 遍历该章节的所有节列表信息
                for section_info in chapter_info.items:
                    # 创建节ID和节名称和节详细信息变量
                    section_id = section_info.itemid
                    section_name = section_info.title

                    # 初始化配置文件课件节对象
                    course_config_sections[section_id] = CourseWareSection(
                        section_id=section_id,
                        section_name=section_name,
                    )

                    # 创建引用
                    course_config_pages = course_config_sections[section_id].pages

                    # 遍历该节下的所有页面列表信息
                    for page_info in section_info.coursepages:
                        # 创建页面ID和页面名称变量
                        page_id = page_info.id
                        page_relation_id = page_info.relationid
                        page_name = page_info.title
                        page_content_type = page_info.contentType

                        # 初始化配置文件课件页面对象
                        course_config_pages[page_id] = CourseWarePage(
                            page_id=page_id,
                            page_relation_id=page_relation_id,
                            page_name=page_name,
                            page_content_type=page_content_type,
                        )

            logger.debug("教材信息解析成功")
            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n解析教材信息失败: {e}")
            return False

    def parse_chapter_info(
        self,
        course_config: ModelCourse,
        textbook_id: int,
        chapter_info: ChapterInfoAPIResponse,
    ) -> bool:
        """
        解析章节信息

        :param course_config: 课件配置对象
        :type course_config: ModelCourse
        :param textbook_id: 教材ID
        :type textbook_id: int
        :param chapter_info: 章节信息API响应数据模型
        :type chapter_info: "ChapterInfoAPIResponse"
        :return: 解析是否成功
        :rtype: bool
        """

        try:
            # 创建引用
            ContentPage = ChapterInfoAPIResponse.ItemDTO.WholePageDTO.ContentPageDTO
            VideoPage = ChapterInfoAPIResponse.ItemDTO.WholePageDTO.VideoPageDTO
            QuestionPage = ChapterInfoAPIResponse.ItemDTO.WholePageDTO.QuestionPageDTO
            DocumentPage = ChapterInfoAPIResponse.ItemDTO.WholePageDTO.DocumentPageDTO
            course_config_textbook = course_config.textbooks[textbook_id]
            chapter_id = chapter_info.chapterid
            course_config_chapter = course_config_textbook.chapters[chapter_id]
            course_config_sections = course_config_chapter.sections

            # 遍历该章节的所有节列表信息
            for section_info in chapter_info.wholepageItemDTOList:
                # 创建引用
                section_id = section_info.itemid
                if section_id not in course_config_sections:
                    continue

                course_config_pages = course_config_sections[section_id].pages

                # 遍历该节下的所有页面列表信息
                for page_info in section_info.wholepageDTOList:
                    # 创建引用
                    page_id = page_info.id
                    page_relation_id = page_info.relationid
                    page_name = page_info.content
                    page_content_type = page_info.contentType
                    course_config_elements = course_config_pages[page_id].elements

                    # 遍历该页面下的所有元素信息
                    for element_info in page_info.coursepageDTOList:
                        # 类型为Doc/Content
                        if page_content_type == 5:
                            # 文档元素
                            if element_info.type == 10 and isinstance(
                                element_info, DocumentPage
                            ):
                                course_config_elements.append(
                                    ElementDocumen(
                                        document_content=element_info.content
                                    )
                                )

                            # 内容元素
                            elif element_info.type == 12 and isinstance(
                                element_info, ContentPage
                            ):
                                course_config_elements.append(
                                    ElementContent(content_content=element_info.content)
                                )

                            # 未知元素
                            else:
                                logger.warning(f"未知的元素类型: {element_info.type}")
                                logger.debug(element_info)

                        # 类型为Video
                        elif page_content_type == 6:
                            # 跳过该页面下非视频元素
                            if not isinstance(element_info, VideoPage):
                                continue

                            # 创建引用
                            video_id = element_info.resourceid
                            video_length = element_info.videoLength

                            # 初始化配置文件课件视频元素对象
                            course_config_elements.append(
                                ElementVideo(
                                    video_id=video_id, video_length=video_length
                                )
                            )

                        # 类型为Question
                        elif page_content_type == 7:
                            # 跳过该页面下非问题元素
                            if not isinstance(element_info, QuestionPage):
                                continue

                            # 初始化问题列表
                            questions: list[ElementQuestion.Question] = []

                            # 遍历问题元素下的所有问题
                            for question_info in element_info.questionDTOList:
                                # 创建引用
                                question_id = question_info.questionid
                                question_score = question_info.score
                                question_content = question_info.title

                                # 初始化配置文件课件问题元素单个问题对象
                                question = ElementQuestion.Question(
                                    question_id=question_id,
                                    question_score=question_score,
                                    question_content=question_content,
                                )
                                questions.append(question)

                            # 初始化配置文件课件问题元素对象
                            course_config_elements.append(
                                ElementQuestion(questions=questions)
                            )

            logger.debug(f"解析章节信息成功")
            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n解析章节信息失败: {e}")
            return False

    def parse_study_record_info(
        self,
        course_config: ModelCourse,
        textbook_id: int,
        study_record_info: StudyRecordAPIResponse,
    ) -> bool:
        """
        解析学习记录信息

        :param course_config: 课件配置对象
        :type course_config: ModelCourse
        :param textbook_id: 教材ID
        :type textbook_id: int
        :param study_record_info: 学习记录API响应数据模型
        :type study_record_info: StudyRecordAPIResponse
        :return: 解析是否成功
        :rtype: bool
        """

        try:
            # 创建引用
            chapter_id = study_record_info.node_id
            section_id = study_record_info.item_id
            course_config_textbook = course_config.textbooks[textbook_id]
            course_config_chapter = course_config_textbook.chapters[chapter_id]
            course_config_section = course_config_chapter.sections[section_id]
            course_config_pages = course_config_section.pages

            # 遍历该节下的所有页面信息
            for page_info in study_record_info.pageStudyRecordDTOList:
                page_relation_id = page_info.pageid
                page_is_complete = page_info.complete

                # 遍历配置文件课件对象的所有页面信息以匹配 relation_id
                for course_page_id, course_page_info in course_config_pages.items():
                    if course_page_info.page_relation_id == page_relation_id:
                        # 设置页面完成状态
                        course_page_info.is_complete = bool(page_is_complete)

            logger.debug(f"解析学习记录信息成功")
            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n解析学习记录信息失败: {e}")
            return False

    def build_sync_study_record_request(
        self,
        study_start_time: int,
        section_info: CourseWareSection,
        user_info: GeneralAPIUserInfoAPIResponse,
        study_time_config: ConfigModel.StudyTime,
    ) -> SyncStudyRecordAPIRequest | None:
        """
        构造同步学习记录请求

        :param study_start_time: 初始化返回的学习开始时间戳(s)
        :type study_start_time: int
        :param section_info: 节信息
        :type section_info: CourseWareSection
        :param user_info: 获取用户信息API响应数据模型
        :type user_info: GeneralAPIUserInfoAPIResponse
        :param study_time_config: 配置文件中的学习时间配置
        :type study_time_config: ConfigModel.StudyTime
        :return: 同步学习记录请求数据模型
        :rtype: SyncStudyRecordAPIRequest | None
        """

        try:
            PageStudyRecordDTO = SyncStudyRecordAPIRequest.PageStudyRecordDTO
            VideoDTO = PageStudyRecordDTO.VideoDTO
            StartEndTime = VideoDTO.StartEndTime
            QuestionDTO = PageStudyRecordDTO.QuestionDTO

            section_id = section_info.section_id
            study_time = 0
            score = 0
            page_study_record_dto_list: list[
                SyncStudyRecordAPIRequest.PageStudyRecordDTO
            ] = []

            pages = section_info.pages

            for page_id, page_info in pages.items():
                page_content_type = page_info.page_content_type
                page_study_record_dto_videos = []
                page_study_record_dto_questions = []

                # 类型为Doc/Content
                if page_content_type == 5:
                    # 分数为100
                    score = 100

                    # 获取元素数量
                    element_num = len(page_info.elements)

                    # 类型为Doc
                    if ElementDocumen in page_info.elements:
                        study_time = (
                            random.randint(
                                study_time_config.document.min,
                                study_time_config.document.max,
                            )
                            * element_num
                        )

                    # 类型为Content
                    else:
                        study_time = (
                            random.randint(
                                study_time_config.content.min,
                                study_time_config.content.max,
                            )
                            * element_num
                        )

                # 类型为Video
                elif page_content_type == 6:
                    # 分数为100
                    score = 100

                    # 遍历所有元素
                    elements = page_info.elements
                    for element in elements:
                        # 非视频元素跳过
                        if not isinstance(element, ElementVideo):
                            continue

                        video_id = element.video_id
                        video_length = element.video_length

                        video_start_time = int(time.time())
                        page_study_record_dto_videos.append(
                            VideoDTO(
                                videoid=video_id,
                                current=video_length - random.uniform(1, 3),
                                recordTime=video_length - random.randint(1, 3),
                                time=video_length,
                                startEndTimeList=[
                                    StartEndTime(
                                        startTime=int(video_start_time),
                                        endTime=video_start_time + video_length,
                                    )
                                ],
                            )
                        )

                # 类型为Question
                elif page_content_type == 7:

                    # 遍历所有元素
                    elements = page_info.elements
                    for element in elements:
                        # 非题目元素跳过
                        if not isinstance(element, ElementQuestion):
                            continue

                        for question in element.questions:
                            question_id = question.question_id
                            answer_list = question.question_answer_list
                            question_score = question.question_score

                            score += int(question_score)

                            page_study_record_dto_questions.append(
                                QuestionDTO(
                                    questionid=question_id,
                                    answerList=answer_list,
                                    score=int(
                                        question_score
                                    ),  # ？？为什么API返回浮点数但是提交的是整数
                                )
                            )

                # 未知类型
                else:
                    logger.warning(f"未知的页面类型: {page_content_type}")
                    continue

                page_study_record_dto_list.append(
                    PageStudyRecordDTO(
                        pageid=page_id,
                        studyTime=study_time,
                        score=score,
                        videos=page_study_record_dto_videos,
                        questions=page_study_record_dto_questions,
                    )
                )

            return SyncStudyRecordAPIRequest(
                itemid=section_id,
                studyStartTime=study_start_time,
                userName=user_info.name,
                pageStudyRecordDTOList=page_study_record_dto_list,
            )

        except Exception as e:
            logger.error(f"{format_exc()}\n构造同步学习记录请求失败: {e}")
            return None
