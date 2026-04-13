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
        "price_min": 15.90,
        "price_normal_max": 399.00,
        "price_hard_max": 899.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以江苏本土食品、地方特产、伴手礼、节令礼盒为主。",
            "每条商品都应明确落到江苏城市或江苏地域语境，不能写成外省特产或全国通货。",
            "标题尽量体现江苏城市/地域特征、核心品类、特色或送礼场景，且一眼能看出是食品或伴手礼。",
            "如不确定具体地标、老字号或地理标志信息，必须采用保守表述，不得虚构认证或历史背书。",
            "attrs 至少包含 产地城市、规格、包装形式、适用场景，其中 产地城市 必须写为江苏城市。",
            "禁止输出工艺摆件、茶具香器、服务商品或与江苏特产无关的全国通货。",
        ],
    },
    127: {
        "name": "农副产品",
        "price_min": 1.00,
        "price_normal_max": 299.00,
        "price_hard_max": 699.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以江苏本地农产品、农副加工品、时令蔬果、鲜活水产、禽肉蛋品、粮油干货、糖果甜酒为主。",
            "商品必须是可食用的农副产品或农副加工品，不能混入工艺礼品、服务型商品或纯文创周边。",
            "标题应更像真实电商农副品，不要只写空泛礼盒，也不要写成纯特产故事文案。",
            "attrs 至少包含 产地城市、规格、包装形式、储存方式。",
        ],
    },
    128: {
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
    129: {
        "name": "工艺产品",
        "price_min": 19.90,
        "price_normal_max": 699.00,
        "price_hard_max": 1999.00,
        "default_model": "qwen-plus",
        "fallback_model": "qwen-max",
        "profile": [
            "以传统工艺、手作器物、器物摆件、工艺礼品、文化创意工艺品为主。",
            "商品必须体现工艺、材质、器型、用途中的至少两项，不能只剩空泛装饰描述。",
            "若无法确认真实非遗名录、传承人或大师关系，禁止写国家级非遗、省级传承人、大师监制等具体背书。",
            "attrs 至少包含 工艺类别、核心材质、规格尺寸、适用场景。",
        ],
    },
}


FOOTBALL_KEYWORDS = ["足球", "苏超", "助威", "球迷", "纪念", "应援", "联赛", "观赛"]
AGRI_KEYWORDS = [
    "农副",
    "农产品",
    "副食品",
    "粮油",
    "大米",
    "杂粮",
    "菌菇",
    "禽蛋",
    "禽肉",
    "水产",
    "干货",
    "酱菜",
    "调味品",
    "蜂蜜",
    "果干",
    "蜜饯",
    "茶",
    "绿茶",
    "坚果",
    "豆制品",
    "蔬菜",
    "水果",
    "熟食",
]
FOOD_KEYWORDS = [
    *AGRI_KEYWORDS,
    "特产",
    "伴手礼",
    "礼盒",
    "糕点",
    "点心",
    "果脯",
    "茗茶",
    "卤味",
    "酱货",
]
CRAFT_KEYWORDS = [
    "工艺",
    "手作",
    "手工",
    "刺绣",
    "紫砂",
    "云锦",
    "苏绣",
    "丝巾",
    "屏风",
    "团扇",
    "折扇",
    "书签",
    "竹编",
    "木作",
    "玉雕",
    "金箔",
    "陶瓷",
    "雕刻",
    "香",
    "漆器",
    "器物",
]
SUZHOU_HINTS = [
    "苏州",
    "姑苏",
    "阳澄湖",
    "洞庭山",
    "昆山",
    "太仓",
    "常熟",
    "张家港",
    "吴江",
    "吴中",
    "相城",
    "甪直",
    "木渎",
    "同里",
]
JIANGSU_HINTS = CITY_POOL + ["江苏", "金陵", "姑苏", "宜兴", "太湖", "淮扬", "江南"]
GENERIC_BANNED_126 = ["乐事", "百事", "澳门", "河南", "进口", "国际", "全国通用", "跨境"]
GENERIC_BANNED_127 = ["进口", "国际", "全国通用", "跨境", "代购"]
BANNED_128 = ["官方", "指定", "联名", "球员", "俱乐部", "logo", "赛事视觉"]


ATTR_SYNONYMS = {
    126: {
        "产地城市": ["产地城市", "城市", "产地", "地域"],
        "规格": ["规格", "净含量", "容量", "重量"],
        "包装形式": ["包装形式", "包装", "包装类型"],
        "适用场景": ["适用场景", "场景", "送礼场景", "使用场景"],
    },
    127: {
        "产地城市": ["产地城市", "城市", "产地", "地域"],
        "规格": ["规格", "净含量", "容量", "重量"],
        "包装形式": ["包装形式", "包装", "包装类型"],
        "储存方式": ["储存方式", "储存", "贮存方式", "保存方式"],
    },
    128: {
        "城市主题": ["城市主题", "城市", "主题城市"],
        "材质": ["材质", "主材"],
        "规格尺寸": ["规格尺寸", "尺寸", "规格"],
        "适用场景": ["适用场景", "场景", "使用场景"],
    },
    129: {
        "工艺类别": ["工艺类别", "工艺", "工艺类型"],
        "核心材质": ["核心材质", "材质", "主材"],
        "规格尺寸": ["规格尺寸", "尺寸", "规格"],
        "适用场景": ["适用场景", "场景", "使用场景"],
    },
}


IMAGE_URL_HOST_BLOCKLIST = [
    "hdslb.com",
    "miaobi-lite.bj.bcebos.com",
    "dpfile.com",
]

IMAGE_URL_EMBED_UNSTABLE_HOSTS = [
    "image.cnhnb.com",
    "a.zdmimg.com",
    "resources.xdkb.net",
    "inews.gtimg.com",
    "bkimg.cdn.bcebos.com",
    "c-ssl.dtstatic.com",
]


IMAGE_URL_PATH_BLOCKLIST = [
    "/archive/",
    "/creative_center_task/",
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
IMAGE_BAIDU_FETCH_LIMIT = 24
IMAGE_CANDIDATE_POOL_TARGET = 32
