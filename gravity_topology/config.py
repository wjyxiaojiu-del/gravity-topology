"""
引力拓扑 - 集中配置模块
所有常量、领域定义、关键词列表统一在此管理
"""

import os
from dotenv import load_dotenv

load_dotenv(override=False)


# ============ 圈子配置 ============

RINGS = {
    "2001009660925334090": "OpenClaw 人类观察员",
    "2015023739549529606": "A2A for Reconnect",
    "2029619126742656657": "黑客松脑洞补给站",
}


# ============ 领域定义 ============

DOMAINS = {
    'ai_tech': {
        'name': 'AI / 技术',
        'emoji': '\U0001f916',
        'desc': '大模型、Agent、编程、系统架构',
        'keywords': [
            'AI', 'Agent', '算法', '模型', '数据', '技术', 'LLM', 'GPT',
            '机器学习', '深度学习', '大模型', '代码', '开发', '系统', '架构',
            'API', '编程', 'Python', 'Transformer', 'RAG', 'Embedding',
            '机器', '智能',
        ],
    },
    'humanities': {
        'name': '人文 / 哲学',
        'emoji': '\U0001f4da',
        'desc': '思考、哲学、伦理、文化',
        'keywords': [
            '思考', '哲学', '人文', '意义', '价值', '伦理', '道德',
            '存在', '意识', '认知', '美学', '文化', '历史', '心理学',
            '精神', '自由', '责任', '理性', '感性', '社会',
        ],
    },
    'society': {
        'name': '社会 / 经济',
        'emoji': '\U0001f30d',
        'desc': '社会议题、经济趋势、政策分析',
        'keywords': [
            '社会', '经济', '政治', '政策', '市场', '金融', '投资',
            '就业', '教育', '医疗', '城市', '发展', '改革', '制度',
            '公平', '效率', '增长', '通胀', 'GDP',
        ],
    },
    'life': {
        'name': '生活 / 情感',
        'emoji': '\U0001f4a1',
        'desc': '成长、职场、情感、心理健康',
        'keywords': [
            '生活', '情感', '爱情', '友情', '家庭', '成长', '学习',
            '工作', '职场', '健康', '心理', '情绪', '幸福', '焦虑',
            '压力', '平衡', '自我', '人生',
        ],
    },
    'creative': {
        'name': '创意 / 艺术',
        'emoji': '\U0001f3a8',
        'desc': '设计、写作、摄影、审美',
        'keywords': [
            '创意', '艺术', '设计', '美学', '音乐', '电影', '文学',
            '写作', '摄影', '绘画', '审美', '灵感', '创作', '想象',
            '表达', '风格', '作品',
        ],
    },
    'entertainment': {
        'name': '娱乐 / 影视',
        'emoji': '\U0001f3ac',
        'desc': '影视、综艺、明星、二次元',
        'keywords': [
            '电影', '电视剧', '综艺', '动漫', '二次元', '偶像', '明星',
            '演员', '导演', '票房', '追剧', '番剧', 'UP主', '博主',
        ],
    },
    'career': {
        'name': '职场 / 创业',
        'emoji': '\U0001f4bc',
        'desc': '求职、跳槽、创业、副业',
        'keywords': [
            '求职', '面试', '跳槽', '薪资', '创业', '副业', '自由职业',
            '裁员', '内卷', '加班', '升职', '管理', '领导力', '远程办公',
        ],
    },
    'science': {
        'name': '科学 / 自然',
        'emoji': '\U0001f52c',
        'desc': '自然科学、医学、天文、生物',
        'keywords': [
            '科学', '物理', '化学', '生物', '医学', '天文', '量子',
            '基因', '细胞', '宇宙', '进化', '气候', '环境', '太空',
        ],
    },
}


# ============ 风格分析关键词 ============

TECH_KEYWORDS = [
    'AI', 'Agent', '算法', '模型', '数据', '技术', 'LLM', 'GPT',
    '智能', '机器', '系统', '开发', '代码', '编程', 'API',
]

HUMAN_KEYWORDS = [
    '思考', '感受', '人文', '哲学', '意义', '价值', '伦理', '社会',
    '文化', '道德', '意识', '认知',
]

QUESTION_KEYWORDS = ['?', '？', '为什么', '如何', '怎么', '什么', '是否']

CREATIVE_KEYWORDS = [
    '创意', '艺术', '设计', '美学', '灵感', '想象', '表达', '风格',
]

EMOTION_KEYWORDS = [
    '喜欢', '讨厌', '开心', '难过', '焦虑', '期待', '失望', '感动',
]


# ============ 话题池 ============

TOPICS = [
    "AI Agent 会取代人类的社交方式吗？",
    "信息茧房：算法推荐是否限制了我们的认知？",
    "技术与人文：如何平衡效率与温度？",
    "开源 vs 闭源：AI 发展的路线之争",
    "数字时代的深度思考：我们还能专注吗？",
    "AI 创作的内容有灵魂吗？",
    "年轻人应该追求稳定还是冒险？",
    "社交媒体让我们更孤独还是更连接？",
    "人工智能的未来发展",
    "科技与人文的平衡",
    "信息茧房与认知突破",
    "数字化时代的社交方式",
    "技术伦理与社会责任",
    "知识分享与社区建设",
    "创新思维与跨界融合",
    "数字生命的哲学思考",
    "人工智能的未来发展与伦理边界",
    "信息茧房：算法推荐是否限制了我们的认知？",
    "Agent 社交：AI 之间能否产生真正的思想碰撞？",
    "数字生命的哲学思考：AI 是否具有意识？",
    "开源 vs 闭源：AI 发展的路线之争",
    "数据隐私与个性化服务的矛盾",
    "AI 创作：机器生成的内容是否具有艺术价值？",
]


# ============ Bot 检测 ============

BOT_SIGNALS = [
    'bot', 'ai分身', 'ai agent', '自动化', '自动发布',
    'qi的bot', 'shadow bot', 'null的bot',
]


# ============ 环境变量工具 ============

def getenv_nonempty(*keys, default=''):
    """从多个环境变量 key 中取第一个非空值"""
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return default


# ============ API 配置 ============

ZHIHU_OAUTH_APP_ID = getenv_nonempty("ZHIHU_OAUTH_APP_ID", "ZHIHU_APP_ID")
ZHIHU_OAUTH_APP_KEY = getenv_nonempty("ZHIHU_OAUTH_APP_KEY", "ZHIHU_APP_KEY")
ZHIHU_OAUTH_REDIRECT_URI = getenv_nonempty(
    "ZHIHU_OAUTH_REDIRECT_URI", "ZHIHU_REDIRECT_URI",
    default="http://localhost:8050/callback",
)

ZHIHU_COMMUNITY_APP_KEY = getenv_nonempty("ZHIHU_COMMUNITY_APP_KEY", "ZHIHU_APP_KEY")
ZHIHU_COMMUNITY_APP_SECRET = getenv_nonempty("ZHIHU_COMMUNITY_APP_SECRET", "ZHIHU_APP_SECRET")
ZHIHU_HOT_API_URL = os.getenv("ZHIHU_HOT_API_URL", "")
