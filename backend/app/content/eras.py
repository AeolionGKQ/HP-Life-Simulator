from __future__ import annotations

from typing import Any


ERAS: tuple[dict[str, Any], ...] = (
    {
        "id": "dumbledore_era",
        "name": "邓布利多时代",
        "years": "1892–1899",
        "eyebrow": "维多利亚晚期 · 天才与悲剧的序章",
        "title": "在传奇成为传说之前，与年轻的邓布利多并肩。",
        "description": (
            "煤油灯与旧羊皮纸的气息笼罩着霍格沃茨。年轻的阿不思·邓布利多尚未背负那个夏日的悲剧，"
            "格林德沃也还没有走入戈德里克山谷。"
        ),
        "mainline": (
            "与年轻的邓布利多共度七年校园生活，并走向1899年的戈德里克山谷："
            "格林德沃来访、“更伟大的利益”诞生，以及阿利安娜之死。"
        ),
        "atmosphere": "煤油灯、旧羊皮纸、秋天壁炉里的烟、雨后的湿土。",
        "available": False,
    },
    {
        "id": "parent_generation",
        "name": "亲世代",
        "years": "1971–1978",
        "eyebrow": "掠夺者年代 · 战争逼近前的青春",
        "title": "在笑声被战争碾碎之前，走进掠夺者的七年。",
        "description": (
            "詹姆、小天狼星、卢平、彼得、莉莉与斯内普一同踏入城堡。活点地图正在成形，"
            "尖叫棚屋藏着秘密，第一次巫师战争的硝烟已在远方升起。"
        ),
        "mainline": (
            "亲历掠夺者成形、卢平的满月秘密、莉莉与斯内普友谊破裂；"
            "毕业后卷入第一次巫师战争，并走向1981年波特夫妇遇害与小天狼星蒙冤的结局。"
        ),
        "atmosphere": "魁地奇球场的青草、扫帚抛光油、禁林松脂、远处逼近的硝烟。",
        "available": False,
    },
    {
        "id": "second_generation",
        "name": "子世代",
        "years": "1991–1998",
        "eyebrow": "第二次巫师战争前夕 · 七年命运之战",
        "title": "命运的猫头鹰，正在寻找你的窗台。",
        "description": (
            "与哈利、罗恩、赫敏同窗七年。从魔法石与密室，到三强争霸赛、D.A.与霍格沃茨之战，"
            "每一学年都将把你推向历史的正中央。"
        ),
        "mainline": (
            "与黄金三角经历七学年核心事件：保护魔法石、密室蛇怪、追寻小天狼星、三强争霸赛、"
            "组建D.A.、天文塔悲剧，最终参与1998年5月2日的霍格沃茨之战。"
        ),
        "atmosphere": "南瓜汁、扫帚掠过的冷风、禁林夜雾中的潮湿木香。",
        "available": True,
    },
    {
        "id": "modern",
        "name": "现代",
        "years": "2020+",
        "eyebrow": "战后二十余年 · 下一代与时间危机",
        "title": "旧伤被常春藤覆盖，新的秘密仍在石墙间发酵。",
        "description": (
            "麦格担任校长，战后秩序逐渐稳定。阿不思·波特与斯科皮·马尔福走进城堡，"
            "一架旧时间转换器却可能再次撕裂历史。"
        ),
        "mainline": (
            "与阿不思·波特和斯科皮·马尔福同窗，围绕旧时间转换器、拯救塞德里克造成的历史崩塌，"
            "阻止德尔菲利用被改写的时间线让伏地魔归来。"
        ),
        "atmosphere": "新书页油墨、暖炉灰烬、庭院晨霜、石缝里发酵的旧秘密。",
        "available": False,
    },
)

ERA_BY_ID = {era["id"]: era for era in ERAS}


def get_era(era_id: str) -> dict[str, Any]:
    return ERA_BY_ID.get(era_id, ERA_BY_ID["second_generation"])


def list_eras() -> list[dict[str, Any]]:
    return [dict(era) for era in ERAS]

