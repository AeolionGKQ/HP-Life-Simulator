from __future__ import annotations

from typing import Any


MODERN_CAST: tuple[dict[str, Any], ...] = (
    {
        "npc_id": "albus_potter",
        "name": "阿不思·西弗勒斯·波特",
        "role": "斯莱特林四年级学生，哈利与金妮的次子",
        "personality": "敏感、骄傲、有谋略，渴望以自己的身份被理解。",
        "goals": ["摆脱父亲声望的定义", "保护与斯科皮的友谊"],
        "fears": ["成为父亲的复制品", "让重要的人失望"],
    },
    {
        "npc_id": "scorpius_malfoy",
        "name": "斯科皮·马尔福",
        "role": "斯莱特林四年级学生，德拉科与阿斯托利亚的独子",
        "personality": "聪明、好学、善于共情，但缺乏安全感。",
        "goals": ["珍惜阿不思", "摆脱伏地魔之子流言", "证明自己不同于家族偏见"],
        "fears": ["失去唯一真正理解自己的朋友", "永远被马尔福姓氏定义"],
    },
    {
        "npc_id": "rose_granger_weasley",
        "name": "罗丝·格兰杰-韦斯莱",
        "role": "格兰芬多四年级学生，罗恩与赫敏的女儿",
        "personality": "聪明、自信、好胜，行动直接。",
        "goals": ["证明自己的能力", "维护自己的判断和朋友圈"],
        "fears": ["被当作父母的简单复制", "在重要问题上失去控制"],
    },
    {
        "npc_id": "polly_chapman",
        "name": "波莉·查普曼",
        "role": "四年级学生，熟悉校园流言和信息传播",
        "personality": "机敏、尖锐、观察敏锐，不愿被忽视。",
        "goals": ["掌握校园消息", "寻找自己的影响力"],
        "fears": ["成为被议论的对象", "错过真正重要的秘密"],
    },
    {
        "npc_id": "karl_jenkins",
        "name": "卡尔·詹金斯",
        "role": "同期学生，参与传播针对阿不思和斯科皮的恶意评价",
        "personality": "从众、好胜，害怕成为被议论的人。",
        "goals": ["维持群体中的位置", "避免承认自己的偏见"],
        "fears": ["被集体排斥", "暴露自己的软弱"],
    },
    {
        "npc_id": "craig_bowker_junior",
        "name": "克雷格·鲍克二世",
        "role": "斯莱特林学生，守规矩的普通好学生",
        "personality": "守规矩、谨慎、认真，容易被忽略。",
        "goals": ["安全完成学业", "得到同学和教授认可"],
        "fears": ["被卷入无法理解的危险", "成为牺牲品"],
    },
    {
        "npc_id": "delphini",
        "name": "德尔菲",
        "role": "与阿莫斯·迪戈里有关的年轻女性；真实信息受揭露等级控制",
        "personality": "善于观察、有吸引力、擅长利用情感，意志强烈。",
        "goals": ["public: 帮助阿莫斯处理塞德里克之死", "hidden: 由受控上下文提供"],
        "fears": ["失去改变历史的机会", "目标被提前识破"],
    },
    {
        "npc_id": "harry_potter",
        "name": "哈利·波特",
        "role": "阿不思的父亲，魔法法律执行系统核心人物",
        "personality": "保护欲强、行动果断，不擅长处理与阿不思的距离。",
        "goals": ["保护家庭", "阻止危险魔法伤害他人"],
        "fears": ["无法保护自己的孩子", "战争以新的形式重演"],
    },
    {
        "npc_id": "draco_malfoy",
        "name": "德拉科·马尔福",
        "role": "斯科皮的父亲，马尔福家主",
        "personality": "谨慎、骄傲、保护斯科皮，背负家族历史。",
        "goals": ["保护斯科皮", "避免旧错误重演"],
        "fears": ["斯科皮受到家族历史伤害", "失去对局面的控制"],
    },
    {
        "npc_id": "hermione_granger",
        "name": "赫敏·格兰杰",
        "role": "罗丝的母亲，魔法部核心决策者",
        "personality": "理性、重视证据、责任感强，熟悉制度。",
        "goals": ["维持公共安全", "防止危险魔法失控"],
        "fears": ["制度再次低估危险", "无法保护罗丝"],
    },
    {
        "npc_id": "minerva_mcgonagall",
        "name": "米勒娃·麦格",
        "role": "霍格沃茨校长，战后学校秩序的守门人",
        "personality": "严格、公正、敏锐，保护学生。",
        "goals": ["维持学校秩序", "防止危险魔法扩散"],
        "fears": ["学生再次成为战争的牺牲品", "城堡旧伤被重新唤醒"],
    },
    {
        "npc_id": "amos_diggory",
        "name": "阿莫斯·迪戈里",
        "role": "塞德里克的父亲，长期承受丧子之痛",
        "personality": "长期悲痛、执着，容易被希望打动。",
        "goals": ["再次见到或拯救塞德里克"],
        "fears": ["希望再次被夺走", "塞德里克被世界遗忘"],
    },
    {
        "npc_id": "cedric_diggory",
        "name": "塞德里克·迪戈里",
        "role": "历史锚点，只在记忆、档案或时间节点中出现",
        "personality": "正直、谦逊、重视公平，拥有自己的判断。",
        "goals": ["完成自己的选择", "不被他人简单定义"],
        "fears": ["被当成别人改写历史的工具"],
    },
)


def modern_cast_index() -> list[dict[str, Any]]:
    return [
        {
            "npc_id": item["npc_id"],
            "name": item["name"],
            "role": item["role"],
            "stable_traits": item["personality"].rstrip("。").split("、"),
            "core_motives": list(item["goals"]),
        }
        for item in MODERN_CAST
    ]
