from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from api import LoginAPI


class ElementVideo(BaseModel):
    """视频元素 数据模型"""

    video_id: int
    video_length: int


class ElementQuestion(BaseModel):
    """问题元素 数据模型"""

    class Question(BaseModel):
        """单个问题数据模型"""

        question_id: int
        question_score: int
        question_content: str
        question_answer_list: list = Field(default_factory=list)

    questions: list[Question] = Field(default_factory=list)


class ElementDocumen(BaseModel):
    """文档元素 数据模型"""

    document_content: str


class ElementContent(BaseModel):
    """文本元素 数据模型"""

    content_content: str


class CourseWarePage(BaseModel):
    """课件第三层-页面 数据模型"""

    page_id: int
    page_relation_id: int
    page_name: str
    page_content_type: int  # 上报体构造方式有关
    """
    5: "Doc/Content",
    6: "Video",
    7: "Question",
    """
    is_complete: bool = False
    elements: list[ElementContent | ElementDocumen | ElementVideo | ElementQuestion] = (
        Field(default_factory=list)
    )


class CourseWareSection(BaseModel):
    """课件第二层-节 数据模型"""

    section_id: int
    section_name: str
    pages: dict[int, CourseWarePage] = Field(default_factory=dict)

    def prune(self) -> None:
        """清理已刷完的页面"""
        for page_id, page in dict(self.pages).items():
            if page.is_complete:
                self.pages.pop(page_id)


class CourseWareChapter(BaseModel):
    """课件第一层-章 数据模型"""

    chapter_id: int
    chapter_name: str
    sections: dict[int, CourseWareSection] = Field(default_factory=dict)

    def prune(self, remove_complete: bool = False) -> None:
        """清理已刷完的节和空节"""
        for section_id, section in dict(self.sections).items():
            if remove_complete:
                section.prune()
            if not section.pages:
                self.sections.pop(section_id)


class ModelTextbook(BaseModel):
    """课程教材数据模型"""

    textbook_id: int
    textbook_name: str
    status: int
    limit: int
    chapters: dict[int, CourseWareChapter] = Field(default_factory=dict)

    def prune(self, remove_complete: bool = False) -> None:
        """清理已刷完的章"""
        for chapter_id, chapter in dict(self.chapters).items():
            chapter.prune(remove_complete)
            if not chapter.sections:
                self.chapters.pop(chapter_id)


class ModelCourse(BaseModel):
    """课程数据模型"""

    course_id: int
    course_name: str
    class_id: int
    class_user_id: int
    textbooks: dict[int, ModelTextbook] = Field(default_factory=dict)

    def prune(self, remove_complete: bool = False) -> None:
        """清理已刷完的教材和空教材"""
        for textbook_id, textbook in dict(self.textbooks).items():
            textbook.prune(remove_complete)
            if not textbook.chapters:
                self.textbooks.pop(textbook_id)


class SyncStudyRecordAPIRequest(BaseModel):
    """
    同步学习记录API请求数据模型
    url = https://api.ulearning.cn/yws/api/personal/sync
    params = {"courseType": 4, "platform": "PC"}
    """

    class PageStudyRecordDTO(BaseModel):
        """页面学习记录数据模型"""

        class VideoDTO(BaseModel):
            """视频元素数据模型"""

            class StartEndTime(BaseModel):
                """开始结束时间数据模型"""

                startTime: int
                """开始看视频时间戳(s)"""
                endTime: int
                """结束看视频时间戳(s)"""

            videoid: int
            """视频ID = video_id"""
            current: float
            """当前播放视频的进度"""
            status: int = 1
            """完成状态 0: 未完成 1: 已完成"""
            recordTime: int
            """已记录的播放了视频的时长"""
            time: float
            """视频长度 = video_length"""
            startEndTimeList: list[StartEndTime]

        class QuestionDTO(BaseModel):
            """问题元素数据模型"""

            questionid: int
            """问题ID = question_id"""
            answerList: list[str]
            """答案列表"""
            score: int
            """分数"""

        pageid: int
        """页面RelationID = page_relation_id"""
        complete: int = 1  # 1
        """完成状态 0: 未完成 1: 已完成"""
        studyTime: int
        """学习时长(s)"""
        score: int
        """分数"""
        answerTime: int = 1  # 1
        """回答次数"""
        submitTimes: int = 0  # 0
        """提交次数"""
        coursepageId: int | None
        """页面ID = page_id"""
        questions: list[QuestionDTO] = Field(default_factory=list)
        videos: list[VideoDTO] = Field(default_factory=list)
        speaks: list = Field(default_factory=list)

    itemid: int
    """节ID = section_id"""
    autoSave: int = 1  # 1
    withoutOld: None = None  # None
    complete: int = 1  # 1
    """完成状态 0: 未完成 1: 已完成"""
    studyStartTime: int
    """初始化返回的时间戳(s)"""
    userName: str
    """姓名 CourseAPIUserInfoAPIResponse 的 name 属性"""
    score: int = 100
    """分数"""
    pageStudyRecordDTOList: list[PageStudyRecordDTO]


class QuestionAnswerAPIResponse(BaseModel):
    """
    问题答案API响应数据模型
    url = https://api.ulearning.cn/questionAnswer/{question_id}
    params = {"parentId": page_id} 页面ID
    """

    questionid: int
    """问题ID = question_id"""
    correctreply: str
    correctAnswerList: list[str]
    """正确答案列表 与 answer_list 性质相同"""


class StudyRecordAPIResponse(BaseModel):
    """
    学习记录API响应数据模型
    url = https://api.ulearning.cn/studyrecord/item/{section_id}
    """

    class PageStudyRecordDTO(BaseModel):
        """页面学习记录数据模型"""

        class VideoDTO(BaseModel):
            """视频元素数据模型"""

            class StartEndTime(BaseModel):
                """开始结束时间数据模型"""

                startTime: int
                """开始看视频时间戳(s)"""
                endTime: int
                """结束看视频时间戳(s)"""

            videoid: int
            """视频ID = video_id"""
            current: float
            """当前播放视频的进度"""
            status: int
            recordTime: int
            """已记录的播放了视频的时长"""
            time: float
            """视频长度 = video_length"""
            startEndTimeList: list[StartEndTime | None]

        class QuestionDTO(BaseModel):
            """问题元素数据模型"""

            questionid: int
            """问题ID = question_id"""
            answerList: list[str]
            """答案列表 = answer_list"""
            score: int
            """分数"""

        pageid: int
        """页面RelationID = page_relation_id"""
        complete: int
        """完成状态 0: 未完成 1: 已完成"""
        submitTimes: int
        studyTime: int
        """学习时长"""
        answerTime: int
        """回答次数"""
        videos: list[VideoDTO] | None = None
        questions: list[QuestionDTO] | None = None
        coursepageId: int | None = None
        """与题目(questions)一起出现 为元素ID"""

    completion_status: int
    """完成状态 0: 未完成 1: 已完成"""
    learner_id: int
    """用户ID = user_id"""
    learner_name: str
    """姓名"""
    relationid: int
    """未知ID"""
    customized: int
    activity_title: str
    """节名 section_name"""
    item_id: int
    """节ID = section_id"""
    node_id: int
    """章节ID = chapter_id = nodeid"""
    score: int
    """分数, 为题目时和题目自带的分数有关"""
    studyTime: int
    """学习时长, pageStudyRecordDTOList下所有页面学习时长之和"""
    pageStudyRecordDTOList: list[PageStudyRecordDTO]


class ChapterInfoAPIResponse(BaseModel):
    """
    章节信息API响应数据模型
    url = https://api.ulearning.cn/wholepage/chapter/stu/{chapter_id}
    哪个神人写的api(
    """

    class ItemDTO(BaseModel):
        """节数据模型"""

        class WholePageDTO(BaseModel):
            """页面数据模型"""

            class BasePageDTO(BaseModel):
                """元素基数据模型"""

                coursepageDTOid: int
                """元素ID = element_id"""
                type: int
                """
                元素类型
                6: "Question",
                4: "Video",
                10: "Document",
                12: "Content",
                """
                parentid: int
                """页面ID = page_id"""
                orderIndex: int
                resourceid: int
                """资源ID / 视频ID"""
                skipVideoTitle: int
                note: str

            class ContentPageDTO(BasePageDTO):
                """内容元素数据模型"""

                content: str
                """内容"""

                resourceDTOList: list

            class VideoPageDTO(BasePageDTO):
                """视频元素数据模型"""

                videoLength: int
                """视频长度 = video_length"""
                resourceid: int
                """视频ID = video_id"""

                resourceFullurl: str
                resourceContentSize: int
                videoQuestionDTOList: list
                knowledgeResourceDTOS: list

            class QuestionPageDTO(BasePageDTO):
                """问题元素数据模型"""

                class QuestionDTO(BaseModel):
                    """题目数据模型"""

                    class choiceitemModel(BaseModel):
                        choiceitemid: int
                        questionid: int
                        title: str

                    questionid: int
                    """问题ID = question_id"""
                    score: float
                    """分数 = question_score"""
                    title: str
                    """问题名 = question_content"""

                    type: int
                    """
                    问题类型
                    1: "单选题",
                    2: "多选题",
                    4: "判断题",
                    """
                    iscontent: int
                    hardlevel: int
                    parentid: int
                    createtime: str
                    updatetime: str
                    remark: str
                    userid: int
                    orgid: int
                    isShare: int
                    blankOrder: int
                    choiceitemModels: list[choiceitemModel] | None = None
                    tagList: list
                    relatedTextbookChapterDTOList: list

                content: str
                questionDTOList: list[QuestionDTO]

            class DocumentPageDTO(BasePageDTO):
                """文档数据模型"""

                content: str
                """内容"""

                resourceFullurl: str
                resourceContentSize: int
                docTitle: str
                docSize: int
                knowledgeResourceDTOS: list

            id: int
            """页面ID = page_id"""
            relationid: int
            """页面RelationID = page_relation_id"""
            content: str
            """页面名 = page_name = title"""
            contentType: int
            """页面类型 = content_type"""

            contentnodeid: int
            """节ID = section_id"""
            type: int
            orderindex: int
            lastmodifydate: str
            share: int
            status: int
            qrcode: int

            coursepageDTOList: list[
                ContentPageDTO | DocumentPageDTO | VideoPageDTO | QuestionPageDTO
            ]
            """元素列表"""

        itemid: int
        """节ID = section_id = itemid"""
        wholepageDTOList: list[WholePageDTO]
        """页面列表"""

    chapterid: int
    """章节ID = chapter_id = nodeid"""
    wholepageItemDTOList: list[ItemDTO]
    """节列表"""


class TextbookInfoAPIResponse(BaseModel):
    """
    教材信息API响应数据模型
    url = https://api.ulearning.cn/course/stu/{textbook_id}/directory"
    params = {"classId": class_id}
    """

    class Chapter(BaseModel):
        class Item(BaseModel):
            class CoursePage(BaseModel):
                id: int
                """页面ID = page_id"""
                relationid: int
                """页面RelationID = page_relation_id"""
                title: str
                """页面名 = page_name"""
                orderindex: int
                contentType: int
                """页面类型 = content_type"""

            itemid: int
            """节ID = section_id"""
            title: str
            """节名 = section_name"""
            orderindex: int

            hide: int = Field(default=0)
            """0: 显示，1: 隐藏"""
            ishidepreview: str = Field(default="2")  # 疑似与 hide 互斥出现
            id: int = Field(default=0)  # 当父chapter中出现id时这个也会跟着出现
            """未知ID"""

            coursepages: list[CoursePage]

        nodeid: int
        """章节ID = chapter_id = node_id"""
        nodetitle: str
        """章节名 = chapter_name"""
        orderindex: int

        hide: int = Field(default=0)
        """0: 显示，1: 隐藏"""
        preview: int = Field(default=0)  # 疑似与 hide 互斥出现
        id: int = Field(default=0)
        """未知ID"""

        items: list[Item]
        """节列表"""

    courseid: int
    """教材ID = textbook_id"""
    coursename: str
    """教材名 = textbook_name"""
    chapters: list[Chapter]
    """章列表"""


class TextbookListAPIResponse(BaseModel):
    """
    教材列表API响应数据模型
    url = https://courseapi.ulearning.cn/textbook/student/{course_id}/list
    """

    class TextbookInfo(BaseModel):
        courseId: int
        """教材ID = textbook_id"""
        name: str
        """教材名 = textbook_name"""

        type: int
        status: int
        limit: int
        author: str | None = None
        copyright: str | None = None
        description: str | None = None
        """描述"""
        cover: str | None = None
        """封面"""
        needapprove: str
        lastModifyDate: int
        """最后修改时间戳"""
        openCourse: int
        md5: str

    textbooks: list[TextbookInfo]

    @classmethod
    def create(cls, resp: list) -> "TextbookListAPIResponse":
        return cls(textbooks=resp)


class CourseListAPIResponse(BaseModel):
    """
    课程列表API响应数据模型
    url = https://courseapi.ulearning.cn/courses/students
    payload = {
        "keyword": "",
        "publishStatus": 1,
        "type": 1,
        "pn": 1,  # page_number
        "ps": 999,  # page_size
        "lang": "zh",
    }
    """

    class _Course(BaseModel):
        id: int
        """课程ID = course_id"""
        name: str
        """课程名 = course_name"""
        classId: int
        """班级ID = class_id"""
        classUserId: int
        """班级用户ID = class_user_id"""

        cover: str
        """课程封面"""
        courseCode: str
        """课程编号"""
        type: int
        className: str
        """班级名"""
        status: int
        """状态"""
        teacherName: str
        """教师名"""
        learnProgress: int
        totalDuration: int
        publishStatus: int
        creatorOrgId: int
        """创建者机构ID"""
        creatorOrgName: str
        """创建者机构名"""

    pn: int
    """页码 = page_number"""
    ps: int
    """页大小 = page_size"""
    total: int
    """总数"""
    courseList: list[_Course]


class LoginAPIUserInfoResponse(BaseModel):
    """
    登录获取的用户信息API响应模型
    url = https://courseapi.ulearning.cn/users/login/v2
    payload = {
        "loginName": self.user_config.username,
        "password": self.user_config.password,
    }
    """

    orgName: str
    """机构名"""
    headimage: str | None = None
    """头像"""
    roleId: int
    """角色ID"""
    sex: str | None = None
    """性别"""
    orgHome: str
    """机构主页"""
    userId: int
    """用户ID"""
    orgId: int
    """机构ID"""
    authorization: str
    """鉴权令牌"""
    studentId: str
    """学号"""
    loginName: str
    """登录用户名"""
    name: str
    """姓名"""
    uversion: int
    """优学院版本"""


class CourseAPIUserInfoAPIResponse(BaseModel):
    """
    获取用户信息API响应数据模型
    url = https://api.ulearning.cn/user
    """

    userid: int
    """用户ID"""
    name: str
    """姓名"""
    headimage: str | None = None
    """头像"""
    orgid: int
    """机构ID"""
    logo: str
    """机构Logo"""
    roleid: int
    """角色ID"""
    antiCheat: int
    antiDrag: int
    openCourseResource: int
    enableSubtitle: int
    enableSkipVideoTitle: int


class APIUrl(BaseModel):
    """API地址数据模型"""

    base_api: str
    course_api: str
    ua_api: str

    @classmethod
    def create(cls, site: str) -> "APIUrl":
        """创建实例"""
        url_map = {
            "ulearning": {
                "base_api": "https://ulearning.cn",
                "course_api": "https://courseapi.ulearning.cn",
                "ua_api": "https://api.ulearning.cn",
            },
            "dgut": {
                "base_api": "https://lms.dgut.edu.cn",
                "course_api": "https://lms.dgut.edu.cn/courseapi",
                "ua_api": "https://ua.dgut.edu.cn/uaapi",
            },
        }
        return cls(**url_map[site])


class UserConfig(BaseModel):
    """用户配置信息数据模型"""

    site: str = Field(title="站点")
    """站点"""
    username: str = Field(title="用户名")
    """用户名"""
    password: str = Field(title="密码")
    """密码"""
    token: str = "a"  # 占位
    """鉴权令牌"""
    cookies: dict = Field(default_factory=dict)
    """Cookies"""
    courses: dict[int, ModelCourse] = Field(default_factory=dict)
    """课程信息"""


class ConfigModel(BaseModel):
    """配置信息数据模型"""

    class StudyTime(BaseModel):
        """学习时间数据模型"""

        class MinMaxTime(BaseModel):
            """时间范围"""

            min: int = 180
            """最小上报时间(s)"""
            max: int = 360
            """最大上报时间(s)"""

        question: MinMaxTime = Field(default_factory=MinMaxTime)
        """问题类型的上报时间范围"""
        document: MinMaxTime = Field(default_factory=MinMaxTime)
        """文档类型的上报时间范围"""
        content: MinMaxTime = Field(default_factory=MinMaxTime)
        """内容类型的上报时间范围"""

    debug: bool = False
    """调试模式"""
    active_user: str = ""
    """当前活跃用户"""
    users: dict[str, UserConfig] = Field(default_factory=dict)
    """用户信息"""
    study_time: StudyTime = Field(default_factory=StudyTime)
    """学习时间配置"""
    sleep_time: float = 1
    """休眠时间(s)"""


@dataclass
class UserAPI:
    """用户API"""

    user_config: UserConfig
    login_api: "LoginAPI"
