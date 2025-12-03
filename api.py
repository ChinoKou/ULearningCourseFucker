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
    def __init__(self, username: str, config: "Config", client: "HttpClient") -> None:
        self.user_config: UserConfig = config.users[username]
        self.config: Config = config
        self.client: "HttpClient" = client
        self.api: APIUrl = APIUrl.create(self.user_config.site)

    async def login(self) -> LoginAPIUserInfoResponse | None:
        """执行登录并用户信息"""
        logger.debug("执行登录并获取用户信息")

        try:
            url = f"{self.api.course_api}/users/login/v2"
            payload = {
                "loginName": self.user_config.username,
                "password": self.user_config.password,
            }

            resp = await self.client.post(url=url, data=payload)

            if not resp or resp.status_code != 302:
                status_code = resp.status_code if resp else None
                logger.error(f"执行登录并用户信息时网络出错: HTTP {status_code}")
                return None

            USERINFO = resp.cookies.get("USERINFO", "")

            if not USERINFO:
                return None

            # URL 解码
            user_info = json.loads(unquote(USERINFO))

            return LoginAPIUserInfoResponse(**user_info)

        except Exception as e:
            logger.error(f"{format_exc()}\n执行登录并用户信息时发生错误: {e}")
            return None

    async def check_login_status(self) -> bool:
        """检查 Token 是否有效"""
        logger.debug("检查 Token 是否有效")

        try:
            url = f"{self.api.course_api}/users/isValidToken/{self.user_config.token}"

            resp = await self.client.get(url)

            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"检查 Token 是否有效时网络出错: HTTP {status_code}")
                raise

            # 检查接口返回值
            return resp.text.strip().lower() == "true"

        except Exception as e:
            logger.error(f"{format_exc()}\n检查 Token 是否有效时发生错误: {e}")
            return False


class CourseAPI:
    def __init__(self, username: str, config: "Config", client: "HttpClient"):
        self.user_config = config.users[username]
        self.config = config
        self.client = client
        self.api = APIUrl.create(self.user_config.site)

    async def get_courses(self) -> CourseListAPIResponse | None:
        """获取课程列表"""
        logger.debug("获取课程列表")

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
                logger.error(f"获取课程列表时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body: dict = resp.json()
            return CourseListAPIResponse(**resp_body)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取课程列表时出错: {e}")
            return None

    async def get_textbooks(
        self, course_id: int, class_id: int
    ) -> TextbookListAPIResponse | None:
        """获取教材列表"""
        logger.info(f"获取教材列表 课程 ID - {course_id} 班级 ID - {class_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.course_api}/textbook/student/{course_id}/list"
            payload = {
                "lang": "zh",  # 抓包的参数, 未知用处
            }

            resp = await self.client.get(url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"获取教材列表时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            return TextbookListAPIResponse.create(resp=resp_body)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取教材列表时出错: {e}")
            return None

    async def get_textbook_info(
        self, textbook_id: int, class_id: int
    ) -> TextbookInfoAPIResponse | None:
        """获取教材信息"""
        logger.info(f"获取教材信息 教材 ID - {textbook_id} 班级 ID - {class_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/course/stu/{textbook_id}/directory"
            payload = {"classId": class_id}

            resp = await self.client.get(url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"获取教材信息时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            return TextbookInfoAPIResponse(**resp_body)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取教材信息时出错: {e}")
            return None

    async def get_chapter_info(self, chapter_id: int) -> ChapterInfoAPIResponse | None:
        """获取章节信息"""
        logger.info(f"获取章节信息, 章节 ID - {chapter_id}")

        try:
            # 构造 url
            url = f"{self.api.ua_api}/wholepage/chapter/stu/{chapter_id}"

            resp = await self.client.get(url)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"获取章节信息时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            return ChapterInfoAPIResponse(**resp_body)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取章节信息时出错: {e}")
            return None

    async def get_study_record_info(
        self, section_id: int
    ) -> tuple[bool, StudyRecordAPIResponse | None]:
        """获取学习记录信息"""
        logger.info(f"获取学习记录信息, 段ID - {section_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/studyrecord/item/{section_id}"
            payload = {"courseType": 4}

            resp = await self.client.get(url=url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"获取学习记录信息时网络出错: HTTP {status_code}")
                return False, None

            if not resp.text:
                return True, None

            # 解析数据
            resp_body = resp.json()
            return True, StudyRecordAPIResponse(**resp_body)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取学习记录信息时出错: {e}")
            return False, None

    async def get_question_answer_list(
        self, question_id: int, parent_id: int
    ) -> QuestionAnswerAPIResponse | None:
        """获取答案列表"""
        logger.info(f"获取答案列表 问题 ID - {question_id} 页面 ID - {parent_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/questionAnswer/{question_id}"
            payload = {"parentId": parent_id}

            resp = await self.client.get(url=url, params=payload)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"获取答案列表时网络出错: HTTP {status_code}")
                return None

            # 解析数据
            resp_body = resp.json()
            return QuestionAnswerAPIResponse(**resp_body)

        except Exception as e:
            logger.error(f"{format_exc()}\n获取答案列表时出错: {e}")
            return None

    async def initialize_section(self, section_id: int) -> int | None:
        """初始化课件-段"""
        logger.debug(f"初始化课程 段ID - {section_id}")

        try:
            # 构造 url 与请求体
            url = f"{self.api.ua_api}/studyrecord/initialize/{section_id}"

            resp = await self.client.get(url)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"初始化课件-段时网络出错: HTTP {status_code}")
                return None

            return int(resp.text)

        except Exception as e:
            logger.error(f"{format_exc()}\n初始化课程出错: {e}")
            return None

    async def watch_video_behavior(
        self, class_id: int, textbook_id: int, chapter_id: int, video_id: int
    ) -> bool:
        """上报视频观看行为"""
        logger.debug("上报视频观看行为")

        try:
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
                logger.error(f"上报视频观看行为时网络出错: HTTP {status_code}")
                return False

            # 无内容返回

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n上报视频观看行为出错: {e}")
            return False

    async def sync_study_record(self, study_record: SyncStudyRecordAPIRequest) -> bool:
        """上报学习记录"""
        logger.debug(f"上报学习记录 段ID - {study_record.itemid}")

        try:
            url = f"{self.api.ua_api}/yws/api/personal/sync"
            params = {"courseType": 4, "platform": "PC"}
            payload_text = study_record.model_dump_json().replace(" ", "")
            encrypted_text = sync_text_encrypt(payload_text)

            resp = await self.client.post(
                url=url, content=encrypted_text, params=params
            )
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"上报学习记录时网络出错: HTTP {status_code}")
                return False

            if resp.text != "1":
                logger.warning("上报学习记录失败")
                return False

            return True

        except Exception as e:
            logger.error(f"{format_exc()}\n上报学习记录时出错: {e}")
            return False

    # async def sync_course(
    #     self,
    #     item_id: int,
    #     study_start_time: int,
    #     username: str,
    #     score: int,
    #     page_record_list: list,
    # ) -> bool:
    #     """上报学习状态"""
    #     logger.debug(f"上报学习状态 项目 ID - {item_id}")

    #     resp = None
    #     try:
    #         url = f"{self.api.ua_api}/yws/api/personal/sync"
    #         params = {"courseType": 4, "platform": "PC"}
    #         payload = {
    #             "itemid": item_id,
    #             "autoSave": 1,
    #             "withoutOld": None,
    #             "complete": 1,
    #             "studyStartTime": study_start_time,
    #             "userName": username,
    #             "score": score,
    #             "pageStudyRecordDTOList": page_record_list,
    #         }
    #         payload_text = json.dumps(payload, ensure_ascii=False).replace(" ", "")
    #         encrypted_text = sync_text_encrypt(payload_text)

    #         resp = await self.client.post(
    #             url=url, content=encrypted_text, params=params
    #         )
    #         if not resp or resp.status_code != 200:
    #             raise

    #         if resp.text != "1":
    #             logger.warning("上报学习状态失败")
    #             return False

    #         return True

    #     except Exception as e:
    #         logger.error(
    #             f"上报学习状态过程出错: "
    #             + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
    #         )
    #         return False

    # async def start_rush_course(self, courses: dict) -> bool:
    #     """传入课程配置信息, 开始刷课"""
    #     logger.debug("开始刷课")

    #     general_api = GeneralAPI(
    #         username=self.user_config.username,
    #         config=self.config,
    #         client=self.client,
    #     )
    #     user_info = await general_api.get_user_info()
    #     if not user_info:
    #         logger.warning("无法获取用户信息, 无法启动刷课")
    #         return False

    #     for course_id, course_info in dict(courses).items():

    #         logger.info(f'[课程][{course_id}] 正在刷 "{course_info["name"]}"')
    #         textbooks: dict = course_info.get("textbooks", {})
    #         for textbook_id, textbook_info in dict(textbooks).items():

    #             logger.info(f'[教材][{textbook_id}] 正在刷 "{textbook_info["name"]}"')
    #             chapters: dict = textbook_info.get("chapters", {})
    #             for chapter_id, chapter_info in dict(chapters).items():

    #                 logger.info(f'[章节][{chapter_id}] 正在刷 "{chapter_info["name"]}"')
    #                 items: dict = chapter_info.get("items", {})
    #                 for item_id, item_info in dict(items).items():

    #                     logger.info(f'[项目][{item_id}] 正在刷 "{item_info["name"]}"')
    #                     retry = 0
    #                     while True:
    #                         study_start_time = await self.initialize_course(item_id)
    #                         if study_start_time == -1:
    #                             logger.warning(
    #                                 f'[项目][{item_id}] 跳过 "{item_info["name"]}"'
    #                             )

    #                         pages: dict = item_info.get("pages", {})

    #                         page_record_list = []
    #                         await self.build_rush_info(
    #                             pages=pages,
    #                             page_record_list=page_record_list,
    #                             class_id=course_info["class_id"],
    #                             textbook_id=textbook_id,
    #                             chapter_id=chapter_id,
    #                         )
    #                         sync_status = self.sync_course(
    #                             item_id=item_id,
    #                             study_start_time=study_start_time,
    #                             username=user_info["name"],
    #                             score=100,
    #                             page_record_list=page_record_list,
    #                         )

    #                         if sync_status:
    #                             logger.success("上报成功")
    #                             break

    #                         if retry >= 3:
    #                             logger.error("上报次数超过 3 次, 上报失败")
    #                             break

    #                         retry += 1

    #     return True

    # async def build_rush_info(
    #     self,
    #     pages: dict,
    #     page_record_list: list,
    #     class_id: int,
    #     textbook_id: int,
    #     chapter_id: int,
    # ):
    #     for page_id, page_info in dict(pages).items():

    #         element_info: dict = page_info.get("element_info", {})
    #         element_type = element_info["type"]

    #         study_time = 0
    #         score = 0
    #         study_record = {
    #             "pageid": page_info["relation_id"],
    #             "complete": 1,
    #             "studyTime": 0,
    #             "score": 0,
    #             "answerTime": 1,
    #             "submitTimes": 0,
    #             "questions": [],
    #             "videos": [],
    #             "speaks": [],
    #         }

    #         logger.info(f"[页面][{page_id}] 正在构造请求信息, 类型: {element_type}")

    #         if element_type == "video":
    #             start_time = int(time.time())
    #             score = 100
    #             videos: dict = element_info.get("info", {})
    #             for video_id, video_info in videos.items():
    #                 await self.watch_video_behavior(
    #                     class_id=class_id,
    #                     textbook_id=textbook_id,
    #                     chapter_id=chapter_id,
    #                     video_id=video_id,
    #                 )
    #                 video_length = video_info["length"]
    #                 study_time += video_length
    #                 study_record["videos"].append(
    #                     {
    #                         "videoid": video_id,
    #                         "current": video_length,
    #                         "status": 1,
    #                         "recordTime": video_length,
    #                         "time": video_length + random.uniform(1, 5),
    #                         "startEndTimeList": [
    #                             {
    #                                 "startTime": start_time,
    #                                 "endTime": start_time + video_length,
    #                             }
    #                         ],
    #                     }
    #                 )

    #         elif element_type == "question":
    #             questions: dict = element_info.get("info", {})

    #             study_time = random.randint(120, 300)
    #             study_record["coursepageId"] = page_info["relation_id"]
    #             study_record["submitTimes"] = 1

    #             for (
    #                 question_id,
    #                 question_info,
    #             ) in questions.items():
    #                 question_score = question_info["score"]
    #                 score += question_score

    #                 study_record["questions"].append(
    #                     {
    #                         "questionid": question_id,
    #                         "answerList": question_info["answer_list"],
    #                         "score": question_score,
    #                     },
    #                 )

    #         else:
    #             score = 100
    #             config_study_time = self.config.study_time[element_type]
    #             study_time = random.randint(
    #                 config_study_time["min"], config_study_time["max"]
    #             )

    #         study_record["score"] = score
    #         study_record["studyTime"] = study_time

    #         page_record_list.append(study_record)
    #         sleep_time = random.uniform(0.3, 1.2)
    #         time.sleep(sleep_time)


class GeneralAPI:
    def __init__(self, username: str, config: "Config", client: "HttpClient"):
        self.user_config = config.users[username]
        self.config = config
        self.client = client
        self.api = APIUrl.create(self.user_config.site)

    async def get_user_info(self) -> GeneralAPIUserInfoAPIResponse | None:
        """获取用户信息"""
        logger.debug("获取用户信息")

        try:
            url = f"{self.api.ua_api}/user"
            resp = await self.client.get(url)
            if not resp or resp.status_code != 200:
                status_code = resp.status_code if resp else None
                logger.error(f"获取用户信息时网络出错: HTTP {status_code}")
                return None

            resp_body = resp.json()
            return resp_body

        except Exception as e:
            logger.error(f"{format_exc()}\n获取用户信息时出错: {e}")
            return None
