import json
import random
import time
from base64 import b64decode, b64encode
from traceback import format_exc
from typing import TYPE_CHECKING
from urllib.parse import unquote

from Crypto.Cipher import DES
from Crypto.Util import Padding
from httpx import Client
from loguru import logger

if TYPE_CHECKING:
    from .config import Config


class Login:
    def __init__(self, config: "Config", username: str):
        self.config = config
        self.user_info = config.users[username]
        self.token = ""
        self.client = Client(verify=not self.config.debug)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
        }
        self.client.headers.update(headers)

    def login(self) -> dict:
        """执行登录并获取 Token 和 用户信息"""
        logger.debug("执行登录并获取 Token 和 用户信息")

        try:
            resp = None
            url = "https://courseapi.ulearning.cn/users/login/v2"
            payload = {
                "loginName": self.user_info["username"],
                "password": self.user_info["password"],
            }

            resp = self.client.post(url=url, data=payload)

            if resp.status_code != 302:
                raise

            USERINFO = resp.cookies.get("USERINFO", "")

            if not USERINFO:
                return {}

            # URL 解码
            user_info = json.loads(unquote(USERINFO))

            # 获取 Token
            token = user_info.get("authorization", None)

            if not token:
                return {}

            # 更新 headers
            headers = {"Authorization": token}
            self.client.headers.update(headers)

            # 更新 config
            self.config.users[self.user_info["username"]]["token"] = token
            self.config.save()

            return user_info

            # other info...

        except Exception as e:
            logger.error(
                f"执行登录并获取 Token 和 用户信息时发生错误: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return {}

    def check_login_status(self) -> bool:
        """检查 Token 是否有效"""
        logger.debug("检查 Token 是否有效")

        try:
            resp = None
            url = f"https://courseapi.ulearning.cn/users/isValidToken/{self.user_info["token"]}"

            resp = self.client.get(url)

            if resp.status_code != 200:
                raise

            # 检查接口返回值
            return resp.text.strip().lower() == "true"

        except Exception as e:
            logger.error(
                f"检查登录状态时发生错误: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return False


class Course:
    def __init__(self, client: Client):
        self.client = client

    def get_courses(self) -> dict:
        """获取课程列表"""
        logger.debug("获取课程列表")

        try:
            resp = None
            # 构造 url 与请求体
            url = "https://courseapi.ulearning.cn/courses/students"
            payload = {
                "keyword": "",
                "publishStatus": 1,
                "type": 1,
                "pn": 1,
                "ps": 999,
                "lang": "zh",
            }

            resp = self.client.get(url=url, params=payload)

            if resp.status_code != 200:
                raise

            # 解析数据
            resp_json = resp.json()
            courses = {}
            course_list = resp_json.get("courseList")
            for course in course_list:
                courses[course["id"]] = {
                    "name": course["name"],
                    "class_id": course["classId"],
                    "class_user_id": course["classUserId"],
                }

            return courses

        except Exception as e:
            logger.error(
                f"获取课程列表出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return {}

    def get_textbooks(self, course_id: int, class_id: int) -> dict:
        """获取教材列表"""
        logger.info(f"获取教材列表 课程 ID - {course_id} 班级 ID - {class_id}")

        try:
            resp = None
            # 构造 url 与请求体
            url = f"https://courseapi.ulearning.cn/textbook/student/{course_id}/list"
            payload = {
                "lang": "zh",  # 抓包的参数, 未知用处
            }

            resp = self.client.get(url, params=payload)
            if resp.status_code != 200:
                raise

            # 解析数据
            resp_data = resp.json()

            textbooks = {}
            for textbook in resp_data:
                textbook_id = textbook["courseId"]
                textbooks[textbook_id] = {
                    "name": textbook["name"],
                    "type": textbook["type"],
                    "status": textbook["status"],
                    "limit": textbook["limit"],
                    "chapters": self.get_chapters(textbook_id, class_id),
                }

            return textbooks

        except Exception as e:
            logger.error(
                f"获取教材列表出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return {}

    def get_chapters(self, textbook_id: int, class_id: int) -> dict:
        """获取章节列表"""
        logger.info(f"获取章节列表 教材 ID - {textbook_id} 班级 ID - {class_id}")

        try:
            resp = None
            # 构造 url 与请求体
            url = f"https://api.ulearning.cn/course/stu/{textbook_id}/directory"
            payload = {"classId": class_id}

            resp = self.client.get(url, params=payload)
            if resp.status_code != 200:
                raise

            # 解析数据
            resp_json = resp.json()
            chapters = resp_json.get("chapters")
            chapter_list = {}
            for chapter in chapters:
                chapter_nodeid = chapter["nodeid"]
                chapter_list[chapter_nodeid] = {
                    "name": chapter["nodetitle"],
                    "items": {},
                }
                chapter_info = chapter_list[chapter_nodeid]

                item_info = self.get_item_info(chapter_nodeid)
                for item in chapter["items"]:
                    item_id = item["itemid"]
                    chapter_info["items"][item_id] = {
                        "name": item["title"],
                        "pages": {},
                    }
                    for page in item["coursepages"]:
                        page_id = page["id"]
                        element_info = (
                            item_info[item_id]["pages"][page_id] if item_info else {}
                        )

                        chapter_info["items"][item_id]["pages"][page_id] = {
                            "relation_id": page["relationid"],
                            "name": page["title"],
                            "content_type": page["contentType"],
                            "is_complete": False,
                            "element_info": element_info,
                        }

            return chapter_list

        except Exception as e:
            logger.error(
                f"获取章节列表出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return {}

    def get_item_info(self, chapter_id: int) -> dict:
        """获取项目列表"""
        logger.info(f"获取项目列表, 章节 ID - {chapter_id}")

        try:
            resp = None
            # 构造 url
            url = f"https://api.ulearning.cn/wholepage/chapter/stu/{chapter_id}"

            resp = self.client.get(url)
            if resp.status_code != 200:
                raise

            # 解析数据
            resp_json = resp.json()
            item_list = resp_json.get("wholepageItemDTOList")
            item_info = {}
            for item in item_list:
                item_id = item["itemid"]
                item_info[item_id] = {"pages": {}}

                for page in item["wholepageDTOList"]:
                    page_id = page["id"]
                    item_info[item_id]["pages"][page_id] = {
                        "name": page["content"],
                        "type": "",
                        "info": {},
                    }
                    page_info = item_info[item_id]["pages"][page_id]

                    for element in page["coursepageDTOList"]:
                        element_id = element["coursepageDTOid"]
                        element_type = element["type"]
                        element_type_map = {
                            6: "question",
                            4: "video",
                            10: "ppt",
                            12: "content",
                        }
                        if element_type not in element_type_map:
                            logger.error(f"未适配的类型 TypeID - {element_type}, 请提供日志以供适配")
                            logger.debug(
                                json.dumps(element, ensure_ascii=False, indent=2)
                            )
                            raise

                        page_info["type"] = element_type_map[element_type]
                        if element_type == 4:
                            video_id = element["resourceid"]
                            page_info["info"][video_id] = {
                                "length": element["videoLength"]
                            }
                        elif element_type == 6:
                            for question in element["questionDTOList"]:
                                question_id = question["questionid"]
                                page_info["info"][question_id] = {
                                    "name": question["title"],
                                    "score": question["score"],
                                    "answer_list": self.get_question_answer_list(
                                        question_id, page_id
                                    ),
                                }
                        else:
                            pass

            return item_info

        except Exception as e:
            logger.error(
                f"获取项目列表出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return {}

    def append_record_info(self, textbook_info: dict) -> dict:
        """获取学习记录信息"""
        logger.info(f"获取学习记录信息, 教材名 - {textbook_info["name"]}")

        try:
            resp = None
            # 构造 url 与请求体
            url = f"https://api.ulearning.cn/studyrecord/item"
            payload = {"courseType": 4}

            # 遍历章节
            chapters: dict = textbook_info.get("chapters", {})
            for chapter_id, chapter_info in chapters.items():

                # 遍历项目
                items: dict = chapter_info.get("items", {})
                for item_id, item_info in items.items():
                    pages: dict = item_info.get("pages")

                    # 获取学习记录
                    item_url = f"{url}/{item_id}"
                    resp = self.client.get(url=item_url, params=payload)
                    if resp.status_code != 200:
                        raise

                    if not resp.text:
                        continue

                    # 解析数据
                    resp_json = resp.json()
                    page_record_info = resp_json.get("pageStudyRecordDTOList")

                    if not page_record_info:
                        continue

                    # 遍历页面
                    for page_record in page_record_info:
                        page_id = page_record["pageid"]

                        # SB relationid
                        for _, page_info in pages.items():
                            if page_info["relation_id"] == page_id:
                                if page_record["complete"]:
                                    page_info["is_complete"] = True

            return textbook_info

        except Exception as e:
            logger.error(
                f"获取学习记录过程出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return textbook_info

    def start_rush_course(self, courses: dict) -> bool:
        """传入课程配置信息, 开始刷课"""
        logger.debug("开始刷课")

        general_api = General(self.client)
        user_info = general_api.get_user_info()
        if not user_info:
            logger.warning("无法获取用户信息, 无法启动刷课")
            return False

        for course_id, course_info in dict(courses).items():

            logger.info(f'[课程][{course_id}] 正在刷 "{course_info["name"]}"')
            textbooks: dict = course_info.get("textbooks", {})
            for textbook_id, textbook_info in dict(textbooks).items():

                logger.info(f'[教材][{textbook_id}] 正在刷 "{textbook_info["name"]}"')
                chapters: dict = textbook_info.get("chapters", {})
                for chapter_id, chapter_info in dict(chapters).items():

                    logger.info(f'[章节][{chapter_id}] 正在刷 "{chapter_info["name"]}"')
                    items: dict = chapter_info.get("items", {})
                    for item_id, item_info in dict(items).items():

                        logger.info(f'[项目][{item_id}] 正在刷 "{item_info["name"]}"')
                        retry = 0
                        while True:
                            study_start_time = self.initialize_course(item_id)
                            if study_start_time == -1:
                                logger.warning(
                                    f'[项目][{item_id}] 跳过 "{item_info["name"]}"'
                                )

                            pages: dict = item_info.get("pages", {})

                            page_record_list = []
                            self.build_rush_info(
                                pages=pages,
                                page_record_list=page_record_list,
                                class_id=course_info["class_id"],
                                textbook_id=textbook_id,
                                chapter_id=chapter_id,
                            )
                            sync_status = self.sync_course(
                                item_id=item_id,
                                study_start_time=study_start_time,
                                username=user_info["name"],
                                score=100,
                                page_record_list=page_record_list,
                            )

                            if sync_status:
                                logger.success("上报成功")
                                break

                            if retry >= 3:
                                logger.error("上报次数超过 3 次, 上报失败")
                                break

                            retry += 1

        return True

    def build_rush_info(
        self,
        pages: dict,
        page_record_list: list,
        class_id: int,
        textbook_id: int,
        chapter_id: int,
    ):
        for page_id, page_info in dict(pages).items():

            element_info: dict = page_info.get("element_info", {})
            element_type = element_info["type"]

            study_time = 0
            score = 0
            study_record = {
                "pageid": page_info["relation_id"],
                "complete": 1,
                "studyTime": 0,
                "score": 0,
                "answerTime": 1,
                "submitTimes": 0,
                "questions": [],
                "videos": [],
                "speaks": [],
            }

            logger.info(f"[页面][{page_id}] 正在构造请求信息, 类型: {element_type}")

            if element_type == "video":
                start_time = int(time.time())
                score = 100
                videos: dict = element_info.get("info", {})
                for video_id, video_info in videos.items():
                    self.watch_video_behavior(
                        class_id=class_id,
                        textbook_id=textbook_id,
                        chapter_id=chapter_id,
                        video_id=video_id,
                    )
                    video_length = video_info["length"]
                    study_time += video_length
                    study_record["videos"].append(
                        {
                            "videoid": video_id,
                            "current": video_length,
                            "status": 1,
                            "recordTime": video_length,
                            "time": video_length + random.uniform(1, 5),
                            "startEndTimeList": [
                                {
                                    "startTime": start_time,
                                    "endTime": start_time + video_length,
                                }
                            ],
                        }
                    )

            elif element_type == "question":
                questions: dict = element_info.get("info", {})

                study_time = random.randint(120, 300)
                study_record["coursepageId"] = page_info["relation_id"]
                study_record["submitTimes"] = 1

                for (
                    question_id,
                    question_info,
                ) in questions.items():
                    question_score = question_info["score"]
                    score += question_score

                    study_record["questions"].append(
                        {
                            "questionid": question_id,
                            "answerList": question_info["answer_list"],
                            "score": question_score,
                        },
                    )

            else:
                score = 100
                study_time = random.randint(120, 300)

            study_record["score"] = score
            study_record["studyTime"] = study_time

            page_record_list.append(study_record)
            sleep_time = random.uniform(0.3, 1.2)
            time.sleep(sleep_time)

    def get_question_answer_list(self, question_id: int, parent_id: int) -> list:
        """获取答案列表"""
        logger.info(f"获取答案列表 问题 ID - {question_id} 页面 ID - {parent_id}")

        try:
            resp = None
            # 构造 url 与请求体
            url = f"https://api.ulearning.cn/questionAnswer/{question_id}"
            payload = {"parentId": parent_id}

            resp = self.client.get(url=url, params=payload)
            if resp.status_code != 200:
                raise

            # 解析数据
            resp_json = resp.json()
            return resp_json["correctAnswerList"]

        except Exception as e:
            logger.error(
                f"获取答案时出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return []

    def initialize_course(self, item_id: int) -> int:
        """初始化课程"""

        logger.debug(f"初始化课程 ID - {item_id}")
        try:
            resp = None
            # 构造 url 与请求体
            url = f"https://api.ulearning.cn/studyrecord/initialize/{item_id}"
            resp = self.client.get(url)
            if resp.status_code != 200:
                raise

            return int(resp.text)

        except Exception as e:
            logger.error(
                f"初始化课程出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return -1

    def watch_video_behavior(
        self, class_id: int, textbook_id: int, chapter_id: int, video_id: int
    ) -> bool:
        """上报视频观看行为"""

        logger.debug("上报视频观看行为")
        try:
            resp = None
            url = "https://courseapi.ulearning.cn/behavior/watchVideo"
            payload = {
                "classId": class_id,
                "courseId": textbook_id,
                "chapterId": chapter_id,
                "videoId": video_id,
            }

            resp = self.client.post(url=url, json=payload)
            if resp.status_code != 200:
                raise

            return True

        except Exception as e:
            logger.error(
                f"上报视频观看行为出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return False

    def sync_course(
        self,
        item_id: int,
        study_start_time: int,
        username: str,
        score: int,
        page_record_list: list,
    ) -> bool:
        """上报学习状态"""
        logger.debug(f"上报学习状态 项目 ID - {item_id}")
        try:
            resp = None
            url = "https://api.ulearning.cn/yws/api/personal/sync"
            params = {"courseType": 4, "platform": "PC"}
            payload = {
                "itemid": item_id,
                "autoSave": 1,
                "withoutOld": None,
                "complete": 1,
                "studyStartTime": study_start_time,
                "userName": username,
                "score": score,
                "pageStudyRecordDTOList": page_record_list,
            }
            payload_text = json.dumps(payload, ensure_ascii=False).replace(" ", "")
            encrypted_text = self.sync_data_encrypt(payload_text)

            resp = self.client.post(url=url, content=encrypted_text, params=params)
            if resp.status_code != 200:
                raise

            if resp.text != "1":
                logger.warning("上报学习状态失败")
                return False

            return True

        except Exception as e:
            logger.error(
                f"上报学习状态过程出错: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return False

    @staticmethod
    def sync_data_encrypt(text: str) -> str:
        """sync接口数据加密"""

        # 初始化密钥与文本
        key = b"12345678"
        data = text.encode("utf-8")

        # 创建 DES 加密对象
        cipher = DES.new(key, DES.MODE_ECB)

        # 填充数据并加密
        padded_data = Padding.pad(data, DES.block_size)
        encrypted_data = cipher.encrypt(padded_data)

        # Base64 编码
        encoded_data = b64encode(encrypted_data)
        encoded_text = encoded_data.decode("utf-8")

        return encoded_text

    @staticmethod
    def sync_data_decrypt(text: str) -> str:
        """sync接口解密"""

        key = b"12345678"
        data = b64decode(text.encode("utf-8"))
        cipher = DES.new(key, DES.MODE_ECB)
        decrypted_data = cipher.decrypt(data)
        unpadded_data = Padding.unpad(decrypted_data, DES.block_size)

        return unpadded_data.decode("utf-8")


class General:
    def __init__(self, client: Client):
        self.client = client

    def get_user_info(self) -> dict:
        """获取用户信息"""
        logger.debug("获取用户信息")

        try:
            resp = None
            url = "https://api.ulearning.cn/user"
            resp = self.client.get(url)
            if resp.status_code != 200:
                raise

            resp_json = resp.json()
            return resp_json

        except Exception as e:
            logger.error(
                f"获取用户信息失败: "
                + (f"HTTP {resp.status_code}" if resp else f"{e}\n{format_exc()}")
            )
            return {}
