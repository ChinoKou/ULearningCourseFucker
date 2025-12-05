import json
from traceback import format_exc
from typing import TYPE_CHECKING
from urllib.parse import unquote

from loguru import logger

from config import Config
from models import (
    APIUrl,
    ChapterInfoAPIResponse,
    CourseListAPIResponse,
    GeneralAPIUserInfoAPIResponse,
    LoginAPIUserInfoResponse,
    QuestionAnswerAPIResponse,
    StudyRecordAPIResponse,
    SyncStudyRecordAPIRequest,
    TextbookInfoAPIResponse,
    TextbookListAPIResponse,
    UserConfig,
)
from utils import sync_text_encrypt

if TYPE_CHECKING:
    from config import Config
    from services import HttpClient


class LoginAPI:
    """登录 API"""

    def __init__(self, username: str, config: "Config", client: "HttpClient") -> None:
        """
        登录 API初始化

        :param username: 要登录的用户名
        :type username: str
        :param config: 配置对象
        :type config: "Config"
        :param client: 内部Http客户端对象
        :type client: "HttpClient"
        """

        self.user_config: UserConfig = config.users[username]
        self.config: Config = config
        self.client: "HttpClient" = client
        self.api: APIUrl = APIUrl.create(self.user_config.site)

    async def login(self) -> LoginAPIUserInfoResponse | None:
        """
        执行登录并用户信息API

        :return: 登录获取的用户信息API响应模型
        :rtype: LoginAPIUserInfoResponse | None
        """
        logger.debug("[API][O] 执行登录并获取用户信息")

        try:
            # 构造 url 与请求体
            url = f"{self.api.course_api}/users/login/v2"
            payload = {
                "loginName": self.user_config.username,
                "password": self.user_config.password,
            }

            resp = await self.client.post(url=url, data=payload)

            if not resp or resp.status_code != 302:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 执行登录并用户信息时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            USERINFO = resp.cookies.get("USERINFO", "")

            if not USERINFO:
                return None

            # URL 解码
            user_info = json.loads(unquote(USERINFO))

            # 转换为模型
            resp_model = LoginAPIUserInfoResponse(**user_info)

            logger.debug(f"[API][✓] 执行登录并获取用户信息")

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 执行登录并用户信息时发生错误: {e}")
            return None

    async def check_login_status(self) -> bool:
        """
        检查Token是否有效

        :return: Token有效状态
        :rtype: bool
        """
        logger.debug("[API][O] 检查Token是否有效")

        try:
            # 构造 url 与请求体
            url = f"{self.api.course_api}/users/isValidToken/{self.user_config.token}"

            resp = await self.client.get(url)

            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 检查 Token 是否有效时网络出错: HTTP {status_code}")
                raise

            # 检查接口返回值
            parse_info = resp.text.strip().lower() == "true"

            logger.debug(f"[API][✓] 检查Token是否有效")

            return parse_info

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 检查Token是否有效时发生错误: {e}")
            return False


class CourseAPI:
    """课程 API"""

    def __init__(self, username: str, config: "Config", client: "HttpClient") -> None:
        """
        课程 API

        :param username: 活跃的用户名
        :type username: str
        :param config: 配置对象
        :type config: "Config"
        :param client: 内部Http客户端对象
        :type client: "HttpClient"
        """

        self.user_config = config.users[username]
        self.config = config
        self.client = client
        self.api = APIUrl.create(self.user_config.site)

    async def get_courses(self) -> CourseListAPIResponse | None:
        """
        获取课程列表API

        :param self: 说明
        :return: 课程列表API响应数据模型
        :rtype: CourseListAPIResponse | None
        """
        logger.debug("[API][O] 获取课程列表")

        try:
            # 构造 url 与请求体
            url = f"{self.api.course_api}/courses/students"
            payload = {
                "keyword": "",
                "publishStatus": 1,
                "type": 1,
                "pn": 1,  # page_number
                "ps": 999,  # page_size
                "lang": "zh",
            }

            resp = await self.client.get(url=url, params=payload)

            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取课程列表时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body: dict = resp.json()
            resp_model = CourseListAPIResponse(**resp_body)

            logger.debug(f"[API][✓] 获取课程列表")

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取课程列表时出错: {e}")
            return None

    async def get_textbooks(
        self, course_id: int, class_id: int
    ) -> TextbookListAPIResponse | None:
        """
        获取教材列表API

        :param course_id: 课程ID
        :type course_id: int
        :param class_id: 你在该课程的班级ID
        :type class_id: int
        :return: 教材列表API响应数据模型
        :rtype: TextbookListAPIResponse | None
        """
        logger.debug(
            f"[API][O] 获取教材列表 课程 ID - {course_id} 班级 ID - {class_id}"
        )

        try:
            # 构造 url 与请求体
            url = f"{self.api.course_api}/textbook/student/{course_id}/list"
            payload = {
                "lang": "zh",  # 抓包的参数, 未知用处
            }

            resp = await self.client.get(url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取教材列表时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            resp_model = TextbookListAPIResponse.create(resp=resp_body)

            logger.debug(
                f"[API][✓] 获取教材列表 课程 ID - {course_id} 班级 ID - {class_id}"
            )

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取教材列表时出错: {e}")
            return None

    async def get_textbook_info(
        self, textbook_id: int, class_id: int
    ) -> TextbookInfoAPIResponse | None:
        """
        获取教材信息API

        :param textbook_id: 教材ID
        :type textbook_id: int
        :param class_id: 你在该教材对应的课程的班级ID
        :type class_id: int
        :return: 教材信息API响应数据模型
        :rtype: TextbookInfoAPIResponse | None
        """
        logger.debug(
            f"[API][O] 获取教材信息 教材 ID - {textbook_id} 班级 ID - {class_id}"
        )

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/course/stu/{textbook_id}/directory"
            payload = {"classId": class_id}

            resp = await self.client.get(url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取教材信息时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            resp_model = TextbookInfoAPIResponse(**resp_body)

            logger.debug(
                f"[API][✓] 获取教材信息 教材 ID - {textbook_id} 班级 ID - {class_id}"
            )

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取教材信息时出错: {e}")
            return None

    async def get_chapter_info(self, chapter_id: int) -> ChapterInfoAPIResponse | None:
        """
        获取章节信息API

        :param chapter_id: 章ID
        :type chapter_id: int
        :return: 章节信息API响应数据模型
        :rtype: ChapterInfoAPIResponse | None
        """
        logger.debug(f"[API][O] 获取章节信息, 章节 ID - {chapter_id}")

        try:
            # 构造 url
            url = f"{self.api.ua_api}/wholepage/chapter/stu/{chapter_id}"

            resp = await self.client.get(url)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取章节信息时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            resp_model = ChapterInfoAPIResponse(**resp_body)

            logger.debug(f"[API][✓] 获取章节信息, 章节 ID - {chapter_id}")

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取章节信息时出错: {e}")
            return None

    async def get_study_record_info(
        self, section_id: int
    ) -> tuple[bool, StudyRecordAPIResponse | None]:
        """
        获取学习记录信息API

        :param section_id: 节ID
        :type section_id: int
        :return: 学习记录API响应数据模型
        :rtype: tuple[bool, StudyRecordAPIResponse | None]
        """
        logger.debug(f"[API][O] 获取学习记录信息, 节ID - {section_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/studyrecord/item/{section_id}"
            payload = {"courseType": 4}

            resp = await self.client.get(url=url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取学习记录信息时网络出错: HTTP {status_code}")
                return False, None

            if not resp.text:
                return True, None

            # 解析数据
            resp_body = resp.json()
            resp_model = StudyRecordAPIResponse(**resp_body)

            logger.debug(f"[API][✓] 获取学习记录信息, 节ID - {section_id}")

            return True, resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取学习记录信息时出错: {e}")
            return False, None

    async def get_question_answer_list(
        self, question_id: int, parent_id: int
    ) -> QuestionAnswerAPIResponse | None:
        """
        获取答案列表API

        :param question_id: 问题ID
        :type question_id: int
        :param parent_id: 父级页面ID
        :type parent_id: int
        :return: 问题答案API响应数据模型
        :rtype: QuestionAnswerAPIResponse | None
        """
        logger.debug(
            f"[API][O] 获取答案列表 问题 ID - {question_id} 页面 ID - {parent_id}"
        )

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/questionAnswer/{question_id}"
            payload = {"parentId": parent_id}

            resp = await self.client.get(url=url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取答案列表时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            resp_model = QuestionAnswerAPIResponse(**resp_body)

            logger.debug(
                f"[API][✓] 获取答案列表 问题 ID - {question_id} 页面 ID - {parent_id}"
            )

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取答案列表时出错: {e}")
            return None

    async def initialize_section(self, section_id: int) -> int | None:
        """
        初始化课件-节API

        :param section_id: 节ID
        :type section_id: int
        :return: 开始刷该节的时间戳
        :rtype: int | None
        """
        logger.debug(f"[API][O] 初始化课程 节ID - {section_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/studyrecord/initialize/{section_id}"

            resp = await self.client.get(url)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 初始化课件-节时网络出错: HTTP {status_code}")
                return None

            parse_info = int(resp.text)

            logger.debug(f"[API][✓] 初始化课程 节ID - {section_id}")

            return parse_info

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 初始化课程出错: {e}")
            return None

    async def watch_video_behavior(
        self, class_id: int, textbook_id: int, chapter_id: int, video_id: int
    ) -> bool:
        """
        上报视频观看行为API

        :param class_id: 你在该课程的班级的ID
        :type class_id: int
        :param textbook_id: 教材ID
        :type textbook_id: int
        :param chapter_id: 章ID
        :type chapter_id: int
        :param video_id: 视频ID
        :type video_id: int
        :return: 是否上报成功
        :rtype: bool
        """
        logger.debug("[API][O] 上报视频观看行为")

        try:
            # 构造 url 与请求体
            url = f"{self.api.course_api}/behavior/watchVideo"
            payload = {
                "classId": class_id,
                "courseId": textbook_id,
                "chapterId": chapter_id,
                "videoId": video_id,
            }

            resp = await self.client.post(url=url, json=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 上报视频观看行为时网络出错: HTTP {status_code}")
                return False

            # 无内容返回

            logger.debug("[API][✓] 上报视频观看行为")

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 上报视频观看行为出错: {e}")
            return False

    async def sync_study_record(
        self, study_record_info: SyncStudyRecordAPIRequest
    ) -> bool:
        """
        上报学习记录API

        :param study_record_info: 同步学习记录API请求数据模型
        :type study_record_info: SyncStudyRecordAPIRequest
        :return: 是否上报成功
        :rtype: bool
        """
        logger.debug(f"[API][O] 上报学习记录 节ID - {study_record_info.itemid}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/yws/api/personal/sync"
            params = {"courseType": 4, "platform": "PC"}
            payload_text = study_record_info.model_dump_json().replace(" ", "")
            encrypted_text = sync_text_encrypt(payload_text)

            resp = await self.client.post(
                url=url, content=encrypted_text, params=params
            )
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 上报学习记录时网络出错: HTTP {status_code}")
                return False

            if resp.text != "1":
                logger.warning("[API] 上报学习记录失败")
                return False

            logger.debug(f"[API][✓] 上报学习记录 节ID - {study_record_info.itemid}")

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 上报学习记录时出错: {e}")
            return False


class GeneralAPI:
    """通用API"""

    def __init__(self, username: str, config: "Config", client: "HttpClient") -> None:
        """
        通用API初始化

        :param username: 活跃的用户名
        :type username: str
        :param config: 配置对象
        :type config: "Config"
        :param client: 内部Http客户端对象
        :type client: "HttpClient"
        """
        self.user_config = config.users[username]
        self.config = config
        self.client = client
        self.api = APIUrl.create(self.user_config.site)

    async def get_user_info(self) -> GeneralAPIUserInfoAPIResponse | None:
        """
        获取用户信息API

        :return: 获取用户信息API响应数据模型
        :rtype: GeneralAPIUserInfoAPIResponse | None
        """
        logger.debug("[API][O] 获取用户信息")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/user"
            resp = await self.client.get(url)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"[API] 获取用户信息时网络出错: HTTP {status_code}")
                return None

            resp_body = resp.json()
            resp_model = GeneralAPIUserInfoAPIResponse(**resp_body)

            logger.debug("[API][✓] 获取用户信息")

            return resp_model

        except Exception as e:
            logger.error(f"{format_exc()}\n[API] 获取用户信息时出错: {e}")
            return None
