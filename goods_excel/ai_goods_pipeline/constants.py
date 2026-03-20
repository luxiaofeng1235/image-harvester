from __future__ import annotations


CITY_POOL = [
    "南京",
    "无锡",
    "徐州",
    "常州",
    "苏州",
    "南通",
    "连云港",
    "淮安",
    "盐城",
    "扬州",
    "镇江",
    "泰州",
    "宿迁",
]


CATEGORY_PROFILES: dict[int, dict[str, object]] = {
    126: {
        "name": "江苏特产",
        "price_min": 19.90,
        "price_normal_max": 399.00,
        "price_hard_max": 899.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以江苏本土食品、地方特产、农副加工品、伴手礼、节令礼盒为主。",
            "商品应带有江苏城市或地域特征，不能伪装成全国通货。",
            "标题尽量体现城市/地域、核心品类、特色或送礼场景。",
            "如不确定具体地标、老字号或地理标志信息，必须采用保守表述，不得虚构认证或历史背书。",
            "attrs 至少包含 产地城市、规格、包装形式、适用场景。",
        ],
    },
    127: {
        "name": "非遗",
        "price_min": 59.00,
        "price_normal_max": 699.00,
        "price_hard_max": 1999.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以传统工艺、非遗技艺、地方手作、文化礼品为主。",
            "商品必须体现工艺、材质、技法、文化出处中的至少两项。",
            "若无法确认真实名录或传承关系，禁止写国家级非遗、省级传承人、大师监制等具体背书。",
            "attrs 至少包含 工艺类别、核心材质、适用场景，建议补充产地或流派。",
        ],
    },
    128: {
        "name": "AI科技",
        "price_min": 299.00,
        "price_normal_max": 1000000.00,
        "price_hard_max": 1000000.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以服务型、方案型、交付型商品为主，例如 AI 网站、知识库、数字孪生、VR 展馆、培训咨询。",
            "商品必须是可售卖的服务套餐，写清交付内容、服务周期、适用对象。",
            "禁止编造客户案例、合作机构、交付成效、备案资质或上线数据，拿不准时只写可交付范围。",
            "attrs 至少包含 交付内容、服务周期、适用对象、部署方式。",
        ],
    },
    129: {
        "name": "苏超纪念品",
        "price_min": 5.90,
        "price_normal_max": 99.00,
        "price_hard_max": 299.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以江苏足球联赛氛围、城市助威文化、球迷伴手礼、低客单文创纪念品为主。",
            "商品需同时具备城市元素与足球/助威/纪念语义。",
            "禁止虚构官方授权、俱乐部联名、球员合作或赛事指定关系。",
            "attrs 至少包含 城市主题、材质、规格尺寸、适用场景。",
        ],
    },
}


FOOTBALL_KEYWORDS = ["足球", "苏超", "助威", "球迷", "纪念", "应援", "联赛", "观赛"]
CRAFT_KEYWORDS = [
    "非遗",
    "紫砂",
    "云锦",
    "苏绣",
    "竹编",
    "木作",
    "玉雕",
    "金箔",
    "香",
    "漆器",
    "手作",
]
SERVICE_KEYWORDS = [
    "AI",
    "网站",
    "知识库",
    "系统",
    "平台",
    "数字孪生",
    "可视化",
    "VR",
    "APP",
    "培训",
    "备案",
    "服务",
    "部署",
]
JIANGSU_HINTS = CITY_POOL + ["江苏", "金陵", "姑苏", "宜兴", "太湖", "淮扬", "江南"]
GENERIC_BANNED_126 = ["乐事", "百事", "澳门", "河南", "进口", "国际", "全国通用"]
BANNED_129 = ["官方", "指定", "联名", "球员", "俱乐部", "logo", "赛事视觉"]


ATTR_SYNONYMS = {
    126: {
        "产地城市": ["产地城市", "城市", "产地", "地域"],
        "规格": ["规格", "净含量", "容量", "重量"],
        "包装形式": ["包装形式", "包装", "包装类型"],
        "适用场景": ["适用场景", "场景", "送礼场景", "使用场景"],
    },
    127: {
        "工艺类别": ["工艺类别", "工艺", "工艺类型"],
        "核心材质": ["核心材质", "材质", "主材"],
        "适用场景": ["适用场景", "场景", "使用场景"],
    },
    128: {
        "交付内容": ["交付内容", "交付物", "功能模块"],
        "服务周期": ["服务周期", "周期", "实施周期"],
        "适用对象": ["适用对象", "客户对象", "适用客户"],
        "部署方式": ["部署方式", "部署", "交付方式"],
    },
    129: {
        "城市主题": ["城市主题", "城市", "主题城市"],
        "材质": ["材质", "主材"],
        "规格尺寸": ["规格尺寸", "尺寸", "规格"],
        "适用场景": ["适用场景", "场景", "使用场景"],
    },
}


IMAGE_URL_HOST_BLOCKLIST = [
    "hdslb.com",
]


IMAGE_URL_PATH_BLOCKLIST = [
    "/archive/",
    "/feed/",
    "/dump/",
    "/provider_image/",
    "/preview",
]


IMAGE_BING_META_BLOCKLIST = [
    "解放军",
    "军事",
    "演习",
    "战机",
    "坦克",
    "部队",
    "海军",
    "空军",
    "陆军",
    "火箭军",
    "军舰",
    "武器",
]


IMAGE_MAIN_COUNT = 1
IMAGE_DETAIL_COUNT = 3
IMAGE_REQUIRED_TOTAL = IMAGE_MAIN_COUNT + IMAGE_DETAIL_COUNT
IMAGE_QUERY_LIMIT = 4
IMAGE_TITLE_QUERY_MAX_LEN = 64
IMAGE_FALLBACK_QUERY_MAX_LEN = 32
IMAGE_BING_FETCH_LIMIT = 12
IMAGE_CANDIDATE_POOL_TARGET = 20
