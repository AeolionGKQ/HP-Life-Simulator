from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any, Iterable

from backend.app.content.eras import get_era
from backend.app.content.dumbledore_cast import (
    DUMBLEDORE_AVAILABLE_FIGURES,
    DUMBLEDORE_ERA_BACKGROUND,
    DUMBLEDORE_FORBIDDEN_FIGURES,
    dumbledore_cast_index,
)
from backend.app.content.modern_cast import modern_cast_index
from backend.app.content.parent_cast import (
    PARENT_AVAILABLE_FIGURES,
    PARENT_ERA_BACKGROUND,
    PARENT_FORBIDDEN_FIGURES,
    parent_cast_index,
)
from backend.app.content.school import normalize_grade


FREEDOM_RULES: tuple[str, ...] = (
    "当前世代主线是历史压力和因果背景，不是强制任务列表。",
    "玩家拥有独立人生，不需要替代原著角色，也不必自动参与每一个原著事件。",
    "玩家可以错过、旁观、误解、延后或改变主线节点。",
    "模型不得默认玩家认识所有原著人物、知道未来历史或获得关键情报。",
    "一轮最多主动推进一个主线焦点；当前个人剧情优先于远期历史事件。",
    "改变主线必须保留人物、关系、声望、资源、世界线或后续因果代价。",
)


SECOND_GENERATION_FRAME: dict[str, Any] = {
    "opening_date": "1991-07-01",
    "opening_scene": "猫头鹰即将把霍格沃茨来信带到玩家窗前；与此同时，哈利·波特即将进入魔法世界。",
    "historical_mood": "日常生活仍然存在，但关于黑魔王的恐惧、否认和流言正在重新聚拢。",
    "world_condition": "魔法部坚持维持表面秩序，邓布利多关注霍格沃茨的异常，部分旧势力等待机会重新抬头。",
    "core_atmosphere": (
        "南瓜汁的甜腻",
        "飞天扫帚掠过时带起的冷风",
        "禁林夜雾中的潮湿木香",
        "古堡石墙吸收烛火后的微凉气息",
        "猫头鹰羽毛、羊皮纸和旧木桌的气味",
    ),
    "mainline_summary": "1991年至1998年，玩家与黄金三角共同经历七年校园生活，并逐步卷入第二次巫师战争和霍格沃茨之战。",
}


SECOND_GENERATION_ARCS: tuple[dict[str, Any], ...] = (
    {
        "id": "letter_and_enrollment",
        "period": "1991年夏至秋",
        "start_date": "1991-07-01",
        "end_date": "1991-09-30",
        "title": "来信与入学",
        "summary": "魔法世界第一次向玩家打开。家庭、出身和第一次进入霍格沃茨的体验，开始决定角色看待这个世界的方式。",
        "anchor_events": ("霍格沃茨来信", "对角巷", "九又四分之三站台", "分院与第一次课程"),
        "important_figures": ("哈利·波特", "罗恩·韦斯莱", "赫敏·格兰杰"),
        "active_pressures": ("玩家尚未拥有完整的魔法界身份", "学院、出身和初始关系正在形成", "哈利·波特的到来吸引了额外关注"),
        "freedom_note": "玩家可以关注哈利，也可以建立自己的朋友圈；不需要在第一年就接触主线核心秘密。",
    },
    {
        "id": "castle_old_secrets",
        "period": "1991–1992学年",
        "start_date": "1991-10-01",
        "end_date": "1992-08-31",
        "title": "城堡旧秘密",
        "summary": "霍格沃茨看似恢复平静，但古老防线、禁忌知识和不愿死去的黑暗正在重新活动。",
        "anchor_events": ("魔法石相关的保护与争夺", "禁书区与地下通道", "城堡中的异常魔法"),
        "important_figures": ("哈利·波特", "罗恩·韦斯莱", "赫敏·格兰杰", "阿不思·邓布利多"),
        "active_pressures": ("学校秩序与个人好奇心发生冲突", "线索可能被提前、延后或错误理解", "教授、学生和校外势力对秘密有不同认知"),
        "freedom_note": "玩家可以成为调查者、旁观者、保护者、投机者或误入者；模型不得强行让玩家替代原著角色。",
    },
    {
        "id": "chamber_and_fear",
        "period": "1992–1993学年",
        "start_date": "1992-09-01",
        "end_date": "1993-08-31",
        "title": "密室与恐惧",
        "summary": "古老偏见重新进入校园，学生安全和血统冲突从流言变成公开恐慌。",
        "anchor_events": ("密室传闻", "学生遭遇袭击", "血统偏见扩散", "城堡深处的蛇怪危险"),
        "important_figures": ("哈利·波特", "罗恩·韦斯莱", "赫敏·格兰杰", "金妮·韦斯莱"),
        "active_pressures": ("学院、血统和声望影响 NPC 判断", "玩家可能成为怀疑对象或调查者", "保护他人与追查真相不一定能同时顺利完成"),
        "freedom_note": "玩家可以参与调查或优先保护特定 NPC；模型不得因为主线存在就自动让玩家发现密室或击败蛇怪。",
    },
    {
        "id": "fugitive_and_time",
        "period": "1993–1994学年",
        "start_date": "1993-09-01",
        "end_date": "1994-08-31",
        "title": "逃犯与时间",
        "summary": "摄魂怪、逃犯传闻和被隐藏的真相，让恐惧、偏见与信任彼此纠缠。",
        "anchor_events": ("小天狼星·布莱克越狱", "摄魂怪进入校园周边", "卢平教授的秘密", "时间转换器与被隐藏的真相"),
        "important_figures": ("小天狼星·布莱克", "莱姆斯·卢平", "哈利·波特", "彼得·佩迪鲁"),
        "active_pressures": ("公众传闻可能与真实事实冲突", "NPC 可能根据错误信息产生敌意", "证据、秘密和信任会影响后续关系"),
        "freedom_note": "玩家可以相信官方消息、追查矛盾或先保护身边人；时间相关事件必须保留因果代价，不能无限重置失败。",
    },
    {
        "id": "tournament_and_war_shadow",
        "period": "1994–1996学年",
        "start_date": "1994-09-01",
        "end_date": "1996-08-31",
        "title": "比赛与战争阴影",
        "summary": "盛大活动、公众目光和黑暗回归同时抵达，霍格沃茨不再是完全安全的避风港。",
        "anchor_events": ("三强争霸赛", "塞德里克·迪戈里的死亡", "伏地魔回归", "魔法部否认与舆论控制", "D.A.秘密学习"),
        "important_figures": ("哈利·波特", "塞德里克·迪戈里", "阿不思·邓布利多", "康奈利·福吉"),
        "active_pressures": ("公开活动与秘密组织之间出现选择", "声望、学院立场和 NPC 信任影响行动空间", "学校与魔法部对真相的说法逐渐分裂"),
        "freedom_note": "玩家可以加入、拒绝或以自己的方式参与 D.A.，也可以建立独立的战时关系网络，不必复制哈利的选择。",
    },
    {
        "id": "resistance_and_battle",
        "period": "1996–1998年",
        "start_date": "1996-09-01",
        "end_date": "1998-12-31",
        "title": "分裂、抵抗与霍格沃茨之战",
        "summary": "成年前夜、牺牲和抵抗将学校、家庭、阵营与个人信念推向冲突，最终汇聚到霍格沃茨之战。",
        "anchor_events": ("天文塔悲剧", "霍格沃茨受到控制", "七年级学生面对战争", "1998年5月2日霍格沃茨之战"),
        "important_figures": ("哈利·波特", "阿不思·邓布利多", "西弗勒斯·斯内普", "德拉科·马尔福", "伏地魔"),
        "active_pressures": ("学校、家庭、阵营和个人信念发生冲突", "玩家需要选择留下、撤离、保护、传递情报或改变战场位置", "战争结束后玩家仍拥有自己的后续人生"),
        "freedom_note": "玩家可以承担战斗、救援、通讯、治疗、侦查或保护任务；可以改变局部代价，但不能无代价抹除战争规模与后果。",
    },
)


SECOND_GENERATION_NODES: tuple[dict[str, Any], ...] = (
    {
        "id": "first_letter_and_enrollment",
        "arc_id": "letter_and_enrollment",
        "title": "霍格沃茨来信与入学",
        "start_date": "1991-07-01",
        "end_date": "1991-09-30",
        "importance": "major",
        "pressure_summary": "玩家的家庭和出身将第一次与魔法界发生正面接触。",
        "possible_player_roles": ("收信人", "旁观者", "怀疑者", "初次探索者"),
        "match_terms": ("来信", "霍格沃茨", "对角巷", "魔杖", "分院", "home", "diagon_alley"),
    },
    {
        "id": "philosophers_stone_protections",
        "arc_id": "castle_old_secrets",
        "title": "魔法石的秘密防线",
        "start_date": "1991-10-01",
        "end_date": "1992-06-30",
        "importance": "major",
        "pressure_summary": "禁书区、地下通道和教授们的异常警惕，暗示城堡里有人正在保护或觊觎某种危险事物。",
        "possible_player_roles": ("调查者", "旁观者", "保护者", "误入者"),
        "match_terms": ("魔法石", "禁书区", "图书馆", "地下通道", "防线", "forbidden", "library"),
    },
    {
        "id": "chamber_of_secrets",
        "arc_id": "chamber_and_fear",
        "title": "密室与袭击",
        "start_date": "1992-09-01",
        "end_date": "1993-06-30",
        "importance": "critical",
        "pressure_summary": "密室传闻和学生袭击正在把血统偏见变成全校恐慌。",
        "possible_player_roles": ("调查者", "保护者", "怀疑对象", "旁观者"),
        "match_terms": ("密室", "蛇怪", "袭击", "血统", "石化", "盥洗室", "chamber"),
    },
    {
        "id": "sirius_escape",
        "arc_id": "fugitive_and_time",
        "title": "逃犯与摄魂怪",
        "start_date": "1993-09-01",
        "end_date": "1994-06-30",
        "importance": "major",
        "pressure_summary": "逃犯传闻、摄魂怪和被隐藏的身份让公众判断与真实危险发生错位。",
        "possible_player_roles": ("追查者", "保护者", "传话者", "相信官方的人"),
        "match_terms": ("小天狼星", "布莱克", "摄魂怪", "卢平", "狼人", "尖叫棚屋", "sirius", "dementor"),
    },
    {
        "id": "triwizard_tournament",
        "arc_id": "tournament_and_war_shadow",
        "title": "三强争霸赛",
        "start_date": "1994-09-01",
        "end_date": "1995-06-30",
        "importance": "major",
        "pressure_summary": "国际赛事让学校成为公众目光的中心，庆典之下隐藏着更危险的安排。",
        "possible_player_roles": ("参赛者", "支持者", "调查者", "观众"),
        "match_terms": ("三强争霸赛", "火焰杯", "迷宫", "塞德里克", "德姆斯特朗", "布斯巴顿", "tournament"),
    },
    {
        "id": "dark_lord_return",
        "arc_id": "tournament_and_war_shadow",
        "title": "黑暗回归与否认",
        "start_date": "1995-06-25",
        "end_date": "1996-08-31",
        "importance": "critical",
        "pressure_summary": "黑暗回归的证据逐渐出现，但魔法部和公众舆论试图把它解释成谣言。",
        "possible_player_roles": ("证人", "抵抗者", "怀疑者", "情报传递者"),
        "match_terms": ("伏地魔", "黑魔王", "魔法部", "回归", "否认", "凤凰社", "dark lord"),
    },
    {
        "id": "da_resistance",
        "arc_id": "tournament_and_war_shadow",
        "title": "D.A.与秘密学习",
        "start_date": "1995-09-01",
        "end_date": "1996-06-30",
        "importance": "major",
        "pressure_summary": "当正式教育被控制时，学生开始寻找私下学习防御魔法和互相信任的方法。",
        "possible_player_roles": ("成员", "拒绝者", "情报员", "独立练习者"),
        "match_terms": ("D.A.", "防御术", "乌姆里奇", "有求必应屋", "秘密练习", "room of requirement"),
    },
    {
        "id": "astronomy_tower",
        "arc_id": "resistance_and_battle",
        "title": "天文塔的裂痕",
        "start_date": "1997-06-01",
        "end_date": "1997-07-31",
        "importance": "critical",
        "pressure_summary": "学校内部的忠诚、欺骗和牺牲开始公开撕裂原有秩序。",
        "possible_player_roles": ("目击者", "救援者", "传令者", "被卷入者"),
        "match_terms": ("天文塔", "邓布利多", "德拉科", "斯内普", "夜晚", "astronomy tower"),
    },
    {
        "id": "battle_of_hogwarts",
        "arc_id": "resistance_and_battle",
        "title": "霍格沃茨之战",
        "start_date": "1998-05-02",
        "end_date": "1998-05-02",
        "importance": "critical",
        "pressure_summary": "霍格沃茨成为战争中心，玩家可以留下、撤离或承担战斗、救援、情报和保护任务。",
        "possible_player_roles": ("战斗人员", "救援人员", "情报传递者", "保护者", "撤离组织者", "旁观者"),
        "match_terms": ("霍格沃茨之战", "城堡", "抵抗", "撤离", "战场", "伏地魔", "battle"),
    },
)


MODERN_FRAME: dict[str, Any] = {
    "opening_date": "2020-09-01",
    "opening_scene": "九又四分之三站台的蒸汽掠过人群。战争已经成为历史，但波特、马尔福和格兰杰-韦斯莱的姓氏仍然牵动着每一道目光。",
    "historical_mood": "战后二十余年的稳定表面下，下一代仍承受家族声望、流言、创伤和未解决的历史问题。",
    "world_condition": "霍格沃茨正在正常运转，麦格校长守护学校秩序；旧时间魔法的痕迹则可能把过去重新带回现在。",
    "core_atmosphere": (
        "新书页的油墨",
        "修复后石墙上仍未消失的裂痕",
        "站台蒸汽和秋日晨霜",
        "晚宴上被刻意避开的战争旧事",
        "画像记忆发生错位前短促的钟声",
    ),
    "mainline_summary": "2020 年起，玩家在下一代学生之间建立自己的校园生活，并自行决定是否接触围绕塞德里克、时间转换器和德尔菲展开的时间危机。",
}


MODERN_ARCS: tuple[dict[str, Any], ...] = (
    {
        "id": "modern_school_arrival",
        "period": "2020年9月1日—9月15日",
        "start_date": "2020-09-01",
        "end_date": "2020-09-15",
        "title": "重新进入城堡",
        "summary": "战后校园已经恢复日常，但家族姓氏、同学流言和旧伤仍在新一代之间留下压力。",
        "anchor_events": ("站台与列车", "分院与晚宴", "校园流言", "修复后的旧墙"),
        "important_figures": ("阿不思·西弗勒斯·波特", "斯科皮·马尔福", "罗丝·格兰杰-韦斯莱", "米勒娃·麦格"),
        "active_pressures": ("下一代承受父母声望", "阿不思和斯科皮的友谊受到流言拉扯", "玩家仍可完全建立自己的校园生活"),
        "freedom_note": "现代主线是背景压力，不是玩家必须加入的任务；接近、观察、竞争或离开都应当成立。",
    },
    {
        "id": "modern_two_slytherins",
        "period": "2020年9月16日—10月10日",
        "start_date": "2020-09-16",
        "end_date": "2020-10-10",
        "title": "两个斯莱特林",
        "summary": "阿不思不愿成为父亲的复制品，斯科皮不愿永远为马尔福姓氏辩护；玩家可以成为桥梁、竞争者或旁观者。",
        "anchor_events": ("同学冲突", "学院关系", "家庭来信", "战后校史争议"),
        "important_figures": ("阿不思·西弗勒斯·波特", "斯科皮·马尔福", "罗丝·格兰杰-韦斯莱", "波莉·查普曼"),
        "active_pressures": ("身份压力", "校园舆论", "友谊与竞争"),
        "freedom_note": "关系变化不等于时间改变；普通争吵、帮助和调查不增加时间扰动。",
    },
    {
        "id": "modern_temporal_echoes",
        "period": "2020年10月11日—11月30日",
        "start_date": "2020-10-11",
        "end_date": "2020-11-30",
        "title": "时间的残影",
        "summary": "旧钟自行响起、画像记忆互相矛盾，阿不思和斯科皮开始隐瞒一项可能涉及时间转换器的计划。",
        "anchor_events": ("旧钟错响", "矛盾画像", "被删除的档案", "塞德里克的不同记录"),
        "important_figures": ("阿不思·西弗勒斯·波特", "斯科皮·马尔福", "阿莫斯·迪戈里", "德尔菲"),
        "active_pressures": ("线索是否报告给校方", "玩家是否被邀请进入计划", "调查异常不等于改变历史"),
        "freedom_note": "玩家可以报告、保密、调查、利用或忽略异常；未真正接触时间因果前，不得制造时间灾难。",
    },
    {
        "id": "modern_aftershock",
        "period": "2020年12月以后",
        "start_date": "2020-12-01",
        "end_date": "9999-12-31",
        "title": "时间危机的余波",
        "summary": "时间危机可能已经改变关系、记忆或公共事实，但玩家仍要在新的现实中继续生活并承担选择的后果。",
        "anchor_events": ("时间干涉", "替代记忆", "历史修复", "校园余波"),
        "important_figures": ("阿不思·西弗勒斯·波特", "斯科皮·马尔福", "德尔菲", "塞德里克·迪戈里"),
        "active_pressures": ("时间扰动的后果", "记忆与现实的冲突", "修复或接受改变后的世界"),
        "freedom_note": "高扰动不等于游戏结束；修复、局部保留、替代线延续和远离核心事件都可以继续生成。",
    },
)


MODERN_NODES: tuple[dict[str, Any], ...] = (
    {
        "id": "modern_school_arrival",
        "arc_id": "modern_school_arrival",
        "title": "2020年的开学日",
        "start_date": "2020-09-01",
        "end_date": "2020-09-15",
        "importance": "major",
        "pressure_summary": "站台、列车和晚宴让玩家第一次看到战后下一代如何被家族姓氏定义。",
        "possible_player_roles": ("同窗", "旁观者", "流言反驳者", "独立探索者"),
        "match_terms": ("站台", "列车", "开学", "阿不思", "斯科皮", "罗丝", "霍格沃茨"),
    },
    {
        "id": "modern_slytherin_friendship",
        "arc_id": "modern_two_slytherins",
        "title": "两个斯莱特林的友谊",
        "start_date": "2020-09-01",
        "end_date": "2020-10-10",
        "importance": "major",
        "pressure_summary": "阿不思和斯科皮的友谊跨越两个家族的旧历史，也因此成为流言和家庭压力的目标。",
        "possible_player_roles": ("朋友", "竞争者", "怀疑者", "信息传递者"),
        "match_terms": ("阿不思", "斯科皮", "波特", "马尔福", "友谊", "流言", "斯莱特林"),
    },
    {
        "id": "modern_time_turner_clues",
        "arc_id": "modern_temporal_echoes",
        "title": "时间转换器的残影",
        "start_date": "2020-10-11",
        "end_date": "2021-06-30",
        "importance": "critical",
        "pressure_summary": "旧钟、矛盾档案和被隐藏的行踪暗示有人正在接近危险的时间魔法。",
        "possible_player_roles": ("调查者", "报告者", "保密者", "局外援助者"),
        "match_terms": ("时间", "时间转换器", "旧钟", "画像", "档案", "异常", "残影"),
    },
    {
        "id": "modern_cedric_anchor",
        "arc_id": "modern_aftershock",
        "title": "塞德里克的历史锚点",
        "start_date": "2020-10-11",
        "end_date": "9999-12-31",
        "importance": "critical",
        "pressure_summary": "改变塞德里克的历史可能让一个人的命运与整个时代的稳定发生冲突。",
        "possible_player_roles": ("旁观者", "同行者", "保护者", "阻止者", "利用者"),
        "match_terms": ("塞德里克", "三强争霸赛", "拯救", "历史", "锚点", "过去"),
    },
)


HISTORICAL_FREEDOM_RULES: tuple[str, ...] = (
    "本世代主线引导必须更弱；没有玩家主动靠近时，不要把原著高潮写成当前场景。",
    "一轮最多出现一个时代压力，且优先个人生活、课程、天气和在场人物。",
    "不得因为原著年份到了就传送玩家，也不得让不在场的玩家自动目击关键悲剧。",
    "需要新NPC时，按本时代自行创建，禁止征用后世角色或尚未出场的人物。",
    "原著因果只作为背景引导，玩家的实际行动和已经成立的状态优先。",
)


DUMBLEDORE_FRAME: dict[str, Any] = {
    "opening_date": "1892-07-01",
    "opening_scene": (
        "1892年夏，你踏入戈德里克山谷。煤油灯、泥路和拉上的窗帘构成这个时代的第一口空气。"
        "霍格沃茨的录取通知书已经收到，魔杖、宠物和随身物品都已备齐，只等九月开学。"
        "霍格沃茨还在九月之后，阿不思·邓布利多仍是即将入学的少年，格林德沃也还没有来。"
    ),
    "historical_mood": (
        "维多利亚晚期的魔法界仍被保密法裹住。才华、体面和家庭秘密比战争更近；"
        "人们用隔绝来保护自己，也因此把孩子关在窗帘后面。"
    ),
    "world_condition": (
        "阿芒多·迪佩特掌管霍格沃茨。邓布利多家刚把阿利安娜藏进山谷，珀西瓦尔已死在阿兹卡班。"
        "1899年夏天的悲剧尚未发生，但气压会随着假期回家和毕业年逐渐变重。"
    ),
    "core_atmosphere": (
        "煤油灯的油烟",
        "旧羊皮纸和墨水",
        "秋天壁炉里的烟",
        "雨后的湿土",
        "湿冷石阶上的烛油",
        "山谷里被窗帘挡住的窗口",
    ),
    "era_background": DUMBLEDORE_ERA_BACKGROUND,
    "mainline_summary": (
        "1892年至1899年，玩家可以与年轻的邓布利多同窗七年，也可以完全过自己的学生生活。"
        "戈德里克山谷的家庭秘密、1899年夏格林德沃的到来和阿利安娜的坠落只是可错过的历史气压。"
    ),
}


DUMBLEDORE_AFTERMATH_TIMELINE = """1899年那个夏天之后，阿不思与盖勒特走上完全不同的路。以下内容是成年后时代的历史框架，用作远方压力、报纸标题、人物背景和多年后的回声，不是必须逐条演完的任务清单。

正史层级必须分清：1899年阿利安娜死亡且施法者未知、格林德沃离开英国并崛起、1926年纽约事件、1927年巴黎集会、约1932年选举骗局与血盟破裂、1945年邓布利多击败格林德沃，是普通正史线的硬锚点。玩家可以改变这些事件周围的人物命运、抵抗过程、伤亡、关系和社会代价；如果玩家直接救下阿利安娜、让阿不思追随格林德沃、提前杀死格林德沃或改变1945年胜负，必须明确进入架空历史，并让此后的世界状态产生系统性变化。普通正史线中，玩家可以影响终局的条件与余波，但不应无条件取代邓布利多完成1945年的历史位置。

1899年之后，阿不思留在英国并回到霍格沃茨任教，把才华收进课堂，把那年夏天锁进沉默。资料对他早期教授的科目存在冲突，通常只写"霍格沃茨教授"；确需展开时可以采用先教黑魔法防御术、后转任变形术的兼容解释，但不要虚构未经确认的转职年份。阿不福思逐渐承担自己的成年生活，兄弟关系可以缓慢修复，却始终保留阿利安娜之死留下的伤痕。

约1900年至1925年是正史留白最大的原创区。格林德沃从魔杖制造师格里戈维奇手中夺走老魔杖，在欧洲聚拢追随者并建立纽蒙迦德，城门上刻着"为了更伟大的利益"。他的运动挪用死亡圣器的标志，主张终结《国际巫师保密法》、让巫师不再躲藏并由巫师领导麻瓜。他真正危险的地方是能抓住真实的制度不公、战争创伤和对躲藏的厌倦，再把它们导向统治、酷刑与牺牲。追随者可分为意识形态核心、权力投机者、制度受害者、末日恐惧者、被胁迫者和双面间谍；"圣徒"只是便于创作的中文称呼，不得擅自添加统一黑魔标记、固定军阶、纯血准入制或制式入会仪式。

1914年至1918年的麻瓜第一次世界大战可以作为一代人的共同创伤和保密压力。不得把格林德沃写成直接策划麻瓜战争或操纵纳粹政权，这类内容必须明确标成架空创作。1939年至1945年的麻瓜第二次世界大战与全球巫师战争在时间上并行，也只能作为社会背景与救援压力。

1926年，格林德沃在纽约冒充美国魔法国会高官珀西瓦尔·格雷夫斯，追查并利用默然者克雷登斯，最终被纽特·斯卡曼德等人揭破并短暂拘押。纽约篇可以使用MACUSA的严格保密、魔杖许可、巫师与麻瓜隔离、第二塞勒姆教会和默默然灾难，但不得把纽特、蒂娜、奎妮、雅各布提前放进1890年代的英国校园。

1927年，格林德沃在押送途中脱身，在巴黎拉雪兹神父公墓地下集会公开宣讲。他用未来麻瓜战争的影像放大真实恐惧，并以蓝色魔火筛选愿意穿过火焰的追随者；这既是宣传，也是阵营分化与暴力威胁。莉塔死亡、奎妮与克雷登斯转向、血盟容器被嗅嗅偷走并交到邓布利多一方，可以作为背景事件，不是必须出现的镜头。克雷登斯被告知自己是"奥雷利乌斯·邓布利多"属于电影专属且争议很大的设定，可以不采用。

约1932年，格林德沃在德国获得司法与政治上的放行，进入国际巫师联合会最高领袖选举。他杀死并操纵麒麟尸体伪造认可，骗局最终在不丹被揭穿，维森西娅·桑托斯当选。年份应写作"约1932年"或"1930年代初"。这一段的重点是政治绥靖、官僚渗透、司法失灵、证据与反情报，不要压缩成一场决斗。

同一阶段，格林德沃试图杀死克雷登斯，阿不思与阿不福思出手保护，双方咒语相撞使血盟破裂。血盟只阻止阿不思与格林德沃直接彼此动手，不阻止他们培养代理人、传递情报、保护第三者或破坏对方计划；不得把它扩展成共享思想、远程定位、违约必死或普通解除咒即可拆除，也不得让它决定阿利安娜之死。血盟破裂后阿不思才真正可能与他为敌，但仍受负罪感、政治后果和对权力的不信任约束。

约1933年至1944年，全球巫师战争持续扩大。纽蒙迦德同时是政治圣地、情报中枢和关押反对者的监狱。邓布利多一方不是一支服从命令的军队，而是由纽特、忒修斯、蒂娜、奎妮、雅各布、尤拉莉、邦蒂、尤素福、阿不福思和尼可·勒梅等人组成的信任网络：每个人都可能在某个问题上违背阿不思的预期，质疑他的隐瞒，或拒绝不透明的计划。这段时间的战役、抵抗组织、囚犯和地区政治可以自由创作，但不得当成官方年表宣称。

1945年，阿不思与格林德沃完成那场被后世称为魔法史最伟大的决斗。地点、招式、见证人以及老魔杖具体如何转而效忠阿不思都属于安全留白；硬事实只是阿不思获胜、格林德沃被囚禁在他自己建造的纽蒙迦德。1956年阿不思成为霍格沃茨校长。更晚的年代里另一个追逐老魔杖的黑魔王会杀死格林德沃，那已远在玩家一生之外，只作为远方收束，不要写进剧情。

死亡圣器、老魔杖、血盟、默然者、麒麟和蓝色魔火都必须按已知边界使用：佩戴或研究圣器标志不等于加入格林德沃；老魔杖易主不要求杀死前任，也不会在每次缴械时机械转移；默然者是创伤与压抑的结果，不是可升级的战斗职业；麒麟能感知内心却不是万能测谎仪；蓝色魔火的筛选效果只在巴黎集会那一场成立。年份是硬约束：只有当前日期真正到达对应年份，相应事件才可能成为现实，1900年的人不可能知道1932年的选举或1945年的结局，也不得提前说出这些名字与地点。玩家可以改变这条线上的任何一环，但每次改变都必须留下人物、关系、制度、资源或世界线代价。"""


DUMBLEDORE_ARCS: tuple[dict[str, Any], ...] = (
    {
        "id": "godrics_hollow_summer",
        "period": "1892年夏",
        "start_date": "1892-07-01",
        "end_date": "1892-08-31",
        "title": "踏入山谷",
        "summary": "煤油灯、泥路和一扇总是拉上的窗。邓布利多家保持礼貌距离，阿不思即将去霍格沃茨，兴奋里藏着不想被问起的事。",
        "anchor_events": ("戈德里克山谷", "邓布利多家的距离", "入学前的夏天"),
        "important_figures": ("阿不思·邓布利多", "肯德拉·邓布利多", "阿不福思·邓布利多", "巴希达·巴沙特"),
        "active_pressures": ("山谷里的安静不像表面那么普通", "家庭秘密尚未向玩家打开", "九月入学仍在前方"),
        "freedom_note": "玩家可以把这里当成路过的村子，也可以成为阿不思入学前的玩伴；不要第一回合就揭开阿利安娜的全部秘密。",
    },
    {
        "id": "brilliant_classmate",
        "period": "1892–1893学年",
        "start_date": "1892-09-01",
        "end_date": "1893-08-31",
        "title": "天才同窗",
        "summary": "迪佩特治下的旧式霍格沃茨里，阿不思迅速不再只是仇视麻瓜者的儿子。分院、第一年课程和图书馆成为日常，家庭裂痕只在家书和假期露出。",
        "anchor_events": ("分院", "第一年课程", "阿不思的才华", "假期回山谷"),
        "important_figures": ("阿不思·邓布利多", "埃尔菲亚斯·多吉", "阿芒多·迪佩特"),
        "active_pressures": ("才华把目光吸走", "玩家仍可建立完全独立的朋友圈", "课程与学院生活优先"),
        "freedom_note": "玩家可以与阿不思成为挚友、竞争者或毫无交集的人；格林德沃此时不得出现在校园。",
    },
    {
        "id": "bent_by_family",
        "period": "1893–1896年",
        "start_date": "1893-09-01",
        "end_date": "1896-08-31",
        "title": "被家族压弯的脊背",
        "summary": "荣誉在学校堆积，山谷里的窗户却更紧。阿不福思逐渐长大，阿利安娜的状态不稳定，阿不思不愿归家形成对照。",
        "anchor_events": ("假期回家", "家庭气氛变紧", "阿不福思的怨言"),
        "important_figures": ("阿不思·邓布利多", "阿不福思·邓布利多", "阿利安娜·邓布利多", "肯德拉·邓布利多"),
        "active_pressures": ("是否看进那扇被窗帘挡住的窗", "学校荣誉与家庭责任冲突"),
        "freedom_note": "只有玩家进入山谷、家庭或相关回忆时，才把家庭秘密变成当前焦点。不要提前放出格林德沃。",
    },
    {
        "id": "light_before_graduation",
        "period": "1896–1899学年",
        "start_date": "1896-09-01",
        "end_date": "1899-06-30",
        "title": "毕业前的光",
        "summary": "阿不思已成为学校传奇，开始更公开地谈论巫师应对世界承担的责任。肯德拉更疲惫，毕业与“以后去哪里”变成真问题。",
        "anchor_events": ("N.E.W.T.", "改革理想", "毕业去向"),
        "important_figures": ("阿不思·邓布利多", "阿不福思·邓布利多", "埃尔菲亚斯·多吉"),
        "active_pressures": ("才华要拿去改变世界，还是先看护一个妹妹", "玩家自己的前程同样重要"),
        "freedom_note": "玩家可以把阿不思拉回家庭，一起畅想改革，或只关心自己的考试与前程。",
    },
    {
        "id": "greater_good_summer",
        "period": "1899年夏",
        "start_date": "1899-07-01",
        "end_date": "1899-08-31",
        "title": "更伟大的利益",
        "summary": "肯德拉去世后，被德姆斯特朗开除的格林德沃借住到姑婆巴希达家。两个天才迅速相爱，讨论死亡圣器、用复活石召回死者、打破保密法和由巫师引领麻瓜，并以血立誓永不彼此为敌。阿不福思指出照护责任无法与远行计划共存，冲突随时可能爆发。",
        "anchor_events": ("肯德拉之死", "格林德沃来访", "更伟大的利益", "血盟", "混战"),
        "important_figures": ("阿不思·邓布利多", "盖勒特·格林德沃", "阿不福思·邓布利多", "阿利安娜·邓布利多", "巴希达·巴沙特"),
        "active_pressures": ("两个天才的计划是否值得让一个女孩继续被藏起来", "玩家可以拉住、拆开、旁观或根本不在山谷"),
        "freedom_note": "只有玩家身处山谷、与邓布利多家有联系或主动追寻阿不思去向时，这一阶段才应成为当前焦点；否则只是远方传闻。",
    },
    {
        "id": "greater_good_aftermath",
        "period": "1899年之后",
        "start_date": "1899-09-01",
        "end_date": "9999-12-31",
        "title": "理想碎裂后的余波",
        "summary": (
            "无论阿利安娜是否死去、格林德沃是否逃离，活下来的人都带着伤、秘密和罪名。游戏继续，不结束。"
            "此后数十年，阿不思留在霍格沃茨任教，格林德沃在欧洲聚起圣徒、走向纽蒙迦德，"
            "两人被年少时的血盟锁住，直到1932年血盟破碎、1945年那场决斗才有结局。"
        ),
        "anchor_events": (
            "余波",
            "决裂或改道",
            "毕业后的人生",
            "圣徒与纽蒙迦德",
            "1926年纽约",
            "1927年巴黎集会",
            "1932年选举与血盟破碎",
            "1945年的决斗",
        ),
        "important_figures": (
            "阿不思·邓布利多",
            "阿不福思·邓布利多",
            "盖勒特·格林德沃",
            "格林德沃的圣徒",
        ),
        "active_pressures": (
            "有些咒不是谁施放的，而是谁先伸出了手",
            "改变历史必须留下裂痕",
            "远方的欧洲正在慢慢变黑，英国却迟迟不肯承认",
        ),
        "future_timeline": DUMBLEDORE_AFTERMATH_TIMELINE,
        "freedom_note": "玩家可以离开学校、留在山谷、追随或阻止格林德沃，或过自己的生活。不要把阿不思立刻写成后世那个温和校长，也不要把几十年后的结局提前搬到当前回合。",
    },
)


DUMBLEDORE_NODES: tuple[dict[str, Any], ...] = (
    {
        "id": "godrics_hollow_arrival",
        "arc_id": "godrics_hollow_summer",
        "title": "1892年夏，踏入戈德里克山谷",
        "start_date": "1892-07-01",
        "end_date": "1892-08-31",
        "importance": "major",
        "pressure_summary": "山谷看起来安静，但邓布利多家的礼貌距离和一扇拉上的窗说明这里藏着不愿见人的事。",
        "possible_player_roles": ("路过者", "玩伴", "打听者", "保持距离的人"),
        "match_terms": ("山谷", "戈德里克", "窗帘", "煤油灯", "邓布利多", "godrics_hollow"),
    },
    {
        "id": "dumbledore_first_year",
        "arc_id": "brilliant_classmate",
        "title": "与年轻邓布利多同窗",
        "start_date": "1892-09-01",
        "end_date": "1893-08-31",
        "importance": "major",
        "pressure_summary": "阿不思的才华把所有目光吸走；玩家要决定是否站在他旁边，或过自己的第一年。",
        "possible_player_roles": ("挚友", "竞争者", "普通同学", "毫无交集的人"),
        "match_terms": ("阿不思", "同窗", "分院", "图书馆", "才华", "霍格沃茨"),
    },
    {
        "id": "hidden_sister",
        "arc_id": "bent_by_family",
        "title": "家庭秘密与阿利安娜",
        "start_date": "1893-09-01",
        "end_date": "1899-06-30",
        "importance": "major",
        "pressure_summary": "妹妹被藏在窗帘后面。靠近她需要信任、假期回访或闯入，而不是自动过场。",
        "possible_player_roles": ("家庭一侧的人", "误入者", "保密者", "远离者"),
        "match_terms": ("阿利安娜", "妹妹", "默然者", "窗帘", "山谷", "秘密"),
    },
    {
        "id": "kendra_death",
        "arc_id": "greater_good_summer",
        "title": "1899年母亲之死",
        "start_date": "1899-07-01",
        "end_date": "1899-07-31",
        "importance": "major",
        "pressure_summary": "肯德拉死于照顾阿利安娜时的意外，阿不思被迫回家。不在山谷的玩家只应听到传闻。",
        "possible_player_roles": ("吊唁者", "家庭支持者", "远方听闻者"),
        "match_terms": ("肯德拉", "母亲", "去世", "意外", "回家"),
    },
    {
        "id": "grindelwald_summer",
        "arc_id": "greater_good_summer",
        "title": "两个天才相遇",
        "start_date": "1899-07-01",
        "end_date": "1899-08-31",
        "importance": "major",
        "pressure_summary": "格林德沃借住巴沙特家，与阿不思讨论更伟大的利益并订立血盟。这是可错过、可拆开、可被改变的相遇。",
        "possible_player_roles": ("挚友", "阻拦者", "同谋", "旁观者"),
        "match_terms": ("格林德沃", "金发", "更伟大的利益", "巴沙特", "死亡圣器", "血盟", "复活石"),
    },
    {
        "id": "ariana_fall",
        "arc_id": "greater_good_summer",
        "title": "混战与坠落",
        "start_date": "1899-08-01",
        "end_date": "1899-08-31",
        "importance": "critical",
        "pressure_summary": "格林德沃对阿不福思使用钻心咒后，三人混战可能夺走阿利安娜。致命咒语的施法者必须保持未知：可以给出彼此矛盾的记忆与证词，但不得判定凶手。玩家可以伸手、旁观、错过或改写，但不能无代价。",
        "possible_player_roles": ("拉住坠落女孩的人", "目击者", "劝架者", "不在场的人"),
        "match_terms": ("阿利安娜", "混战", "魔咒", "死亡", "坠落", "决斗", "钻心咒", "葬礼"),
    },
    {
        "id": "greater_good_aftermath",
        "arc_id": "greater_good_aftermath",
        "title": "理想碎裂后的余波",
        "start_date": "1899-09-01",
        "end_date": "9999-12-31",
        "importance": "major",
        "pressure_summary": "格林德沃可能逃离，兄弟可能决裂，活下来的人仍带着伤。高世界线偏移也必须留下裂痕。",
        "possible_player_roles": ("留下的人", "追随者", "阻止者", "过自己生活的人"),
        "match_terms": ("余波", "逃离", "决裂", "霍格沃茨", "格林德沃"),
    },
)


PARENT_FRAME: dict[str, Any] = {
    "opening_date": "1971-09-01",
    "opening_scene": (
        "1971年9月1日，九又四分之三站台的蒸汽里漏进麻瓜收音机的摇滚乐。"
        "詹姆、小天狼星、卢平、彼得、莉莉与斯内普将在这趟列车上第一次把敌意和友谊摆上桌。"
    ),
    "historical_mood": (
        "战争尚未碾碎笑声。霍格沃茨走廊里仍是魁地奇、恶作剧和初恋，"
        "校外却开始有人失踪，有人低声避开一个不该直呼的名字。"
    ),
    "world_condition": (
        "邓布利多已是校长，麦格是变形术教授，斯拉格霍恩执掌魔药课。"
        "打人柳新种下，尖叫棚屋尚未成为完整鬼屋，活点地图还是空白羊皮纸。"
        "第一次巫师战争的硝烟在远处升起，但一年级的日常仍是课堂和宿舍。"
    ),
    "core_atmosphere": (
        "魁地奇球场的青草",
        "飞天扫帚的抛光油",
        "禁林的松脂",
        "宿舍里的收音机杂音",
        "满月前走廊里突然空掉的位置",
        "远处隐隐逼近的硝烟",
    ),
    "era_background": PARENT_ERA_BACKGROUND,
    "mainline_summary": (
        "1971年至1978年是校园阶段，玩家与掠夺者一代同窗；1978年毕业后自动进入成年过渡与战争时代，"
        "并可继续推进到1981年及其后的开放式余波。恶作剧、满月、那句泥巴种和战争都是可错过的气压；"
        "玩家可以并肩、劝阻、告发、参战、远离，或把七年过成普通学生生活。"
    ),
    "school_period": {
        "start_date": "1971-09-01",
        "end_date": "1978-06-30",
        "description": "角色作为霍格沃茨学生度过七年，课程、考试、学院生活和学生关系在此阶段生效。",
    },
    "adult_period": {
        "start_date": "1978-07-01",
        "end_date": "9999-12-31",
        "description": "毕业后进入成年过渡、第一次巫师战争与1981年后的开放式人生，不再默认是学生。",
    },
}


PARENT_ADULT_TIMELINE = """亲世代成年与战争时代从1978年7月1日开始。1971年至1978年6月30日是七年校园阶段；
从1978年夏起，玩家和同期核心角色应按成年巫师、求职者、家属、独立行动者或组织外围人物处理，不能继续默认住在学生宿舍、参加普通课程或以学生身份行动。

1978年至1981年，第一次巫师战争逐渐从远方失踪与低声传闻进入魔法界公共生活。凤凰社和食死徒都是秘密组织，
玩家是否加入、调查、对抗、协助或远离，必须由实际行动、关系和证据决定。成年不自动等于凤凰社成员，也不自动等于食死徒。
普通学生和没有组织联系的成年巫师不应直接知道预言全文、秘密据点、行动名单或组织内部计划。

1981年10月31日是高压历史节点，不是游戏终点。波特夫妇的命运、小天狼星是否蒙冤、彼得是否伪造死亡以及战争后的社会状态，
都应承接玩家已经成立的行动与世界线变化。1981年之后允许继续推进；不得因为原著时间线结束而停止叙事、强制恢复原结局或召回子世代主线。
"""


PARENT_ARCS: tuple[dict[str, Any], ...] = (
    {
        "id": "platform_1971",
        "period": "1971年9月",
        "start_date": "1971-09-01",
        "end_date": "1971-09-30",
        "title": "站台与分院",
        "summary": "蒸汽、猫头鹰和流行乐。列车上詹姆与小天狼星已经开始发光，斯内普与莉莉坐在另一处。分院帽将把四名未来的掠夺者送进格兰芬多，把斯内普送进斯莱特林。",
        "anchor_events": ("九又四分之三站台", "列车冲突", "分院"),
        "important_figures": ("詹姆·波特", "小天狼星·布莱克", "莉莉·伊万斯", "西弗勒斯·斯内普", "莱姆斯·卢平", "彼得·佩迪鲁"),
        "active_pressures": ("你要坐进哪一节车厢", "学院将立刻切开旧友谊与新敌意"),
        "freedom_note": "玩家可以加入任何一群人，也可以谁都不加入。不要把哈利写成这趟列车上的学生。",
    },
    {
        "id": "marauders_forming",
        "period": "1971–1973年",
        "start_date": "1971-10-01",
        "end_date": "1973-08-31",
        "title": "笑声开始成形",
        "summary": "四人组逐渐粘在一起，斯内普与莉莉仍跨学院来往。卢平在满月前后消失，打人柳对低年级是禁止靠近的新危险。",
        "anchor_events": ("宿舍友谊", "跨学院往来", "满月缺席", "打人柳"),
        "important_figures": ("詹姆·波特", "小天狼星·布莱克", "莱姆斯·卢平", "彼得·佩迪鲁", "莉莉·伊万斯", "西弗勒斯·斯内普"),
        "active_pressures": ("恶作剧是友谊还是把人关在门外的方式", "课程与校园生活优先"),
        "freedom_note": "玩家可以成为第五人、旁观者或完全独立的学生。狼人身份不得开局公开。",
    },
    {
        "id": "moon_and_secret",
        "period": "1973–1975年",
        "start_date": "1973-09-01",
        "end_date": "1975-08-31",
        "title": "月亮与秘密",
        "summary": "有人可能发现卢平是狼人。詹姆、小天狼星和彼得开始危险的阿尼马格斯之路，活点地图还是未完成的玩笑，尖叫棚屋的叫声开始变成村庄传说。",
        "anchor_events": ("满月", "打人柳", "尖叫棚屋", "阿尼马格斯"),
        "important_figures": ("莱姆斯·卢平", "詹姆·波特", "小天狼星·布莱克", "彼得·佩迪鲁"),
        "active_pressures": ("发现朋友每月消失一次之后，会告发、帮忙还是利用", "活点地图不是必得物品"),
        "freedom_note": "玩家可以伸出援手、向教师告发或什么都不做。不要把每一次满月都写成强制副本。",
    },
    {
        "id": "mudblood_year",
        "period": "1975–1976学年",
        "start_date": "1975-09-01",
        "end_date": "1976-08-31",
        "title": "那句泥巴种",
        "summary": "O.W.L.年，詹姆的霸凌公开化。莉莉护住斯内普，却被那句咒骂推开。裂痕可以发生、被阻止、被火上浇油，或只成为不在场者后来听到的传闻。",
        "anchor_events": ("公开羞辱", "泥巴种", "友谊破裂", "O.W.L."),
        "important_figures": ("西弗勒斯·斯内普", "莉莉·伊万斯", "詹姆·波特", "小天狼星·布莱克"),
        "active_pressures": ("一句咒骂能否被收回", "玩家可以站在中间、只保护一人或当天不在场"),
        "freedom_note": "不在场时，这只应成为后来的校园传闻，而不是强制过场。",
    },
    {
        "id": "paths_diverge",
        "period": "1976–1978年",
        "start_date": "1976-09-01",
        "end_date": "1978-06-30",
        "title": "毕业前的分流",
        "summary": "莉莉与詹姆可能靠近，斯内普更深地走向斯莱特林中的黑暗圈子，校外失踪消息变多。N.E.W.T.与前途把人推向不同的成年人。",
        "anchor_events": ("N.E.W.T.", "感情变化", "黑暗圈子", "毕业"),
        "important_figures": ("莉莉·伊万斯", "詹姆·波特", "西弗勒斯·斯内普", "小天狼星·布莱克"),
        "active_pressures": ("你们会变成什么样的成年人", "战争仍是校外新闻，除非玩家主动靠近"),
        "freedom_note": "玩家不必提前加入凤凰社或食死徒。普通校园生活仍然合法。",
    },
    {
        "id": "first_war",
        "period": "1978–1981年",
        "start_date": "1978-07-01",
        "end_date": "1981-10-30",
        "title": "硝烟不再远处",
        "summary": "毕业后，掠夺者与莉莉可能走向凤凰社，斯内普可能走向另一条路。预言只应作为远处回声，不要让普通学生开局就知道全文。",
        "anchor_events": ("凤凰社", "食死徒", "失踪与袭击", "隐居"),
        "important_figures": ("詹姆·波特", "莉莉·伊万斯", "小天狼星·布莱克", "西弗勒斯·斯内普", "阿不思·邓布利多"),
        "active_pressures": ("要不要发出警告", "要不要参战", "要不要远离"),
        "freedom_note": "只有毕业后仍留在公共生活、或主动接近相关人物的玩家，才应把战争变成当前焦点。",
    },
    {
        "id": "halloween_1981",
        "period": "1981年10月31日及之后",
        "start_date": "1981-10-31",
        "end_date": "9999-12-31",
        "title": "命运之夜与余波",
        "summary": "高锥村可能发生悲剧，小天狼星可能蒙冤，彼得可能伪造死亡。改变这一夜是最高世界线偏移，必须改写此后的魔法界，但不能把子世代人物提前召唤出来。",
        "anchor_events": ("万圣节", "波特夫妇", "小天狼星", "余波"),
        "important_figures": ("詹姆·波特", "莉莉·伊万斯", "小天狼星·布莱克", "彼得·佩迪鲁", "西弗勒斯·斯内普"),
        "active_pressures": ("你要不要在命运之夜前发出最后一声警告", "游戏不因这一夜结束"),
        "freedom_note": "玩家可以警告、对抗、站在另一侧，或只在报纸上读到讣告。不在场就不要写成目击。",
    },
)


PARENT_NODES: tuple[dict[str, Any], ...] = (
    {
        "id": "platform_1971",
        "arc_id": "platform_1971",
        "title": "1971年的站台与列车",
        "start_date": "1971-09-01",
        "end_date": "1971-09-30",
        "importance": "major",
        "pressure_summary": "你要坐进哪一节车厢，将决定先看见掠夺者的光还是斯内普与莉莉的旧友谊。",
        "possible_player_roles": ("同车人", "旁观者", "劝架者", "独行者"),
        "match_terms": ("站台", "列车", "分院", "詹姆", "莉莉", "斯内普", "platform_nine_three_quarters"),
    },
    {
        "id": "marauders_forming",
        "arc_id": "marauders_forming",
        "title": "掠夺者成形",
        "start_date": "1971-10-01",
        "end_date": "1973-08-31",
        "importance": "major",
        "pressure_summary": "四人组的笑声开始填满走廊。玩家可以加入、厌恶或无视。",
        "possible_player_roles": ("第五人", "竞争者", "告状者", "局外人"),
        "match_terms": ("掠夺者", "恶作剧", "詹姆", "小天狼星", "宿舍"),
    },
    {
        "id": "moon_and_willow",
        "arc_id": "moon_and_secret",
        "title": "满月、打人柳与尖叫棚屋",
        "start_date": "1973-09-01",
        "end_date": "1975-08-31",
        "importance": "major",
        "pressure_summary": "卢平每月消失。打人柳和尖叫棚屋是学校为他准备的秘密，不是一年级观光点。",
        "possible_player_roles": ("援手", "告发者", "误入者", "保密者"),
        "match_terms": ("满月", "狼人", "打人柳", "尖叫棚屋", "卢平"),
    },
    {
        "id": "animagus_and_map",
        "arc_id": "moon_and_secret",
        "title": "阿尼马格斯与活点地图",
        "start_date": "1974-09-01",
        "end_date": "1976-06-30",
        "importance": "major",
        "pressure_summary": "空白羊皮纸正在被画成活点地图。这是可被发现、没收、复制或错过的秘密，不是新系统。",
        "possible_player_roles": ("共犯", "发现者", "告发者", "毫不知情的人"),
        "match_terms": ("阿尼马格斯", "活点地图", "牡鹿", "黑狗", "老鼠", "羊皮纸"),
    },
    {
        "id": "snape_worst_memory",
        "arc_id": "mudblood_year",
        "title": "公开羞辱与那句泥巴种",
        "start_date": "1975-09-01",
        "end_date": "1976-08-31",
        "importance": "critical",
        "pressure_summary": "詹姆当众羞辱斯内普，莉莉护住他后被骂泥巴种。不在场的玩家不应被传送到现场。",
        "possible_player_roles": ("劝架者", "火上浇油的人", "只保护一人的人", "不在场的人"),
        "match_terms": ("泥巴种", "羞辱", "倒吊", "斯内普", "莉莉", "最糟"),
    },
    {
        "id": "paths_diverge",
        "arc_id": "paths_diverge",
        "title": "毕业分流",
        "start_date": "1976-09-01",
        "end_date": "1978-06-30",
        "importance": "major",
        "pressure_summary": "感情、黑暗圈子和前途把同窗推向不同的成年人。",
        "possible_player_roles": ("朋友", "中间人", "旁观者"),
        "match_terms": ("毕业", "N.E.W.T.", "凤凰社", "食死徒", "前途"),
    },
    {
        "id": "first_war",
        "arc_id": "first_war",
        "title": "第一次巫师战争",
        "start_date": "1978-07-01",
        "end_date": "1981-10-30",
        "importance": "major",
        "pressure_summary": "校外袭击变多。战争是可加入、可远离的社会背景，不是必须参战的副本。",
        "possible_player_roles": ("凤凰社成员", "警告者", "远离者", "另一侧的人"),
        "match_terms": ("战争", "凤凰社", "食死徒", "伏地魔", "失踪"),
    },
    {
        "id": "halloween_1981",
        "arc_id": "halloween_1981",
        "title": "1981年万圣节",
        "start_date": "1981-10-31",
        "end_date": "1981-10-31",
        "importance": "critical",
        "pressure_summary": "命运之夜可以被警告、被改变或被错过。改变它必须改写世界，但不能提前召唤子世代人物。",
        "possible_player_roles": ("警告者", "保护者", "对抗者", "只读讣告的人"),
        "match_terms": ("万圣节", "高锥村", "波特夫妇", "1981", "婴儿"),
    },
)


def get_generation_content(era_id: str) -> dict[str, Any]:
    """返回不会随玩家状态变化的时代内容，供动态上下文计算使用。"""
    era = get_era(era_id)
    if era["id"] == "second_generation":
        return {
            "era_frame": _copy_frame(SECOND_GENERATION_FRAME),
            "mainline_arcs": [_copy_mapping(arc) for arc in SECOND_GENERATION_ARCS],
            "mainline_nodes": [_copy_mapping(node) for node in SECOND_GENERATION_NODES],
            "freedom_rules": list(FREEDOM_RULES),
        }
    if era["id"] == "modern":
        return {
            "era_frame": _copy_frame(MODERN_FRAME),
            "mainline_arcs": [_copy_mapping(arc) for arc in MODERN_ARCS],
            "mainline_nodes": [_copy_mapping(node) for node in MODERN_NODES],
            "cast_index": modern_cast_index(),
            "freedom_rules": list(FREEDOM_RULES)
            + [
                "现代线使用时间扰动表达时间因果压力；普通校园生活、对话、课程和关系变化不自动改变时间。",
                "原著因果只作为背景引导，玩家的实际行动和已经成立的状态优先。",
            ],
        }
    if era["id"] == "dumbledore_era":
        return {
            "era_frame": _copy_frame(DUMBLEDORE_FRAME),
            "mainline_arcs": [_copy_mapping(arc) for arc in DUMBLEDORE_ARCS],
            "mainline_nodes": [_copy_mapping(node) for node in DUMBLEDORE_NODES],
            "cast_index": dumbledore_cast_index(),
            "forbidden_figures": list(DUMBLEDORE_FORBIDDEN_FIGURES),
            "available_figures": [
                _copy_mapping(item) for item in DUMBLEDORE_AVAILABLE_FIGURES
            ],
            "era_background": DUMBLEDORE_ERA_BACKGROUND,
            "freedom_rules": list(FREEDOM_RULES) + list(HISTORICAL_FREEDOM_RULES),
        }
    if era["id"] == "parent_generation":
        return {
            "era_frame": _copy_frame(PARENT_FRAME),
            "mainline_arcs": [_copy_mapping(arc) for arc in PARENT_ARCS],
            "mainline_nodes": [_copy_mapping(node) for node in PARENT_NODES],
            "cast_index": parent_cast_index(),
            "forbidden_figures": list(PARENT_FORBIDDEN_FIGURES),
            "available_figures": [
                _copy_mapping(item) for item in PARENT_AVAILABLE_FIGURES
            ],
            "adult_timeline": PARENT_ADULT_TIMELINE,
            "era_background": PARENT_ERA_BACKGROUND,
            "freedom_rules": list(FREEDOM_RULES) + list(HISTORICAL_FREEDOM_RULES),
        }
    return {
        "era_frame": {
            "opening_date": None,
            "opening_scene": era.get("description", ""),
            "historical_mood": era.get("description", ""),
            "world_condition": era.get("mainline", ""),
            "core_atmosphere": _split_atmosphere(era.get("atmosphere", "")),
            "mainline_summary": era.get("mainline", ""),
        },
        "mainline_arcs": [
            {
                "id": era["id"],
                "period": era.get("years", ""),
                "start_date": "0001-01-01",
                "end_date": "9999-12-31",
                "title": era.get("name", ""),
                "summary": era.get("mainline", ""),
                "anchor_events": [],
                "important_figures": [],
                "active_pressures": [],
                "freedom_note": "当前世代尚未开放完整分阶段数据；仍需把长期主线视为背景而不是强制任务。",
            }
        ],
        "mainline_nodes": [],
        "freedom_rules": list(FREEDOM_RULES),
    }


def build_generation_context(
    *,
    era_id: str,
    player_state: dict[str, Any],
    action: dict[str, Any] | None = None,
    memories: Iterable[Any] = (),
) -> dict[str, Any]:
    """根据权威玩家状态生成本轮需要注入的时代与主线上下文。"""
    content = get_generation_content(era_id)
    era = get_era(era_id)
    state = player_state if isinstance(player_state, dict) else {}
    memory_items = list(memories)
    school = state.get("school", {})
    school = school if isinstance(school, dict) else {}
    current_context = state.get("current_context", {})
    current_context = current_context if isinstance(current_context, dict) else {}
    raw_current_date = current_context.get("current_date") or str(
        current_context.get("datetime") or ""
    )[:10]
    current_date = _parse_date(
        raw_current_date,
        _parse_date(str(content["era_frame"].get("opening_date") or ""), date.today()),
    )
    grade = normalize_grade(school)
    worldline = state.get("worldline", {})
    worldline = worldline if isinstance(worldline, dict) else {}

    arc = _select_arc(content["mainline_arcs"], current_date)
    timeline_phase = _build_timeline_phase(
        current_date=current_date,
        grade=grade,
        school=school,
        arc=arc,
    )
    statuses = {
        str(node["id"]): _node_status(node, current_date, worldline.get("affected_nodes", []))
        for node in content["mainline_nodes"]
    }
    relevant_nodes = _select_relevant_nodes(
        content["mainline_nodes"],
        statuses,
        action=action or {},
        location_id=current_context.get("location_id"),
        memories=memory_items,
    )
    pressure = _build_worldline_pressure(
        nodes=content["mainline_nodes"],
        statuses=statuses,
        worldline=worldline,
        relevant_nodes=relevant_nodes,
    )
    if era["id"] == "modern":
        timeline_phase = _build_modern_timeline_phase(
            current_date=current_date,
            school=school,
            arc=arc,
            modern_arc=state.get("modern_arc"),
        )
        pressure = _build_modern_temporal_pressure(
            worldline=worldline,
            relevant_nodes=relevant_nodes,
        )
    cast_index = content.get("cast_index", [])
    if era["id"] == "parent_generation":
        cast_index = parent_cast_index(
            current_date,
            revealed_facts=memory_items,
        )

    mainline_phase = {
        "id": arc["id"],
        "title": arc["title"],
        "period": arc["period"],
        "summary": arc["summary"],
        "anchor_events": list(arc["anchor_events"]),
        "important_figures": list(arc["important_figures"]),
        "active_pressures": list(arc["active_pressures"]),
        "freedom_note": arc["freedom_note"],
    }
    if arc.get("future_timeline"):
        mainline_phase["future_timeline"] = arc["future_timeline"]

    return {
        "id": era["id"],
        "name": era["name"],
        "years": era["years"],
        "era_frame": _copy_frame(content["era_frame"]),
        "generation_mainline": era["mainline"],
        "mainline_phase": mainline_phase,
        "timeline_phase": timeline_phase,
        "relevant_nodes": relevant_nodes,
        "freedom_rules": list(content["freedom_rules"]),
        "worldline_pressure": pressure,
        "cast_index": cast_index,
        "forbidden_figures": list(content.get("forbidden_figures", [])),
        "available_figures": [
            _copy_mapping(item) for item in content.get("available_figures", [])
        ],
        "adult_timeline": content.get("adult_timeline"),
        "era_background": content.get("era_background"),
        "modern_arc": state.get("modern_arc", {}) if era["id"] == "modern" else None,
    }


def _build_modern_timeline_phase(
    *,
    current_date: date,
    school: dict[str, Any],
    arc: dict[str, Any],
    modern_arc: Any,
) -> dict[str, Any]:
    arc_state = modern_arc if isinstance(modern_arc, dict) else {}
    phase_id = str(arc_state.get("phase_id") or arc["id"])
    return {
        "calendar_date": current_date.isoformat(),
        "calendar_year": current_date.year,
        "school_year": school.get("school_year"),
        "term": school.get("term"),
        "grade": normalize_grade(school),
        "phase_id": phase_id,
        "phase_title": arc["title"],
        "phase_summary": arc["summary"],
        "active_pressures": list(arc["active_pressures"][:3]),
    }


def _build_modern_temporal_pressure(
    *,
    worldline: dict[str, Any],
    relevant_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        disturbance = float(worldline.get("temporal_disturbance", 0))
    except (TypeError, ValueError):
        disturbance = 0.0
    try:
        stability = float(worldline.get("temporal_stability", 100))
    except (TypeError, ValueError):
        stability = 100.0
    if disturbance < 10:
        band = "stable"
        guidance = "时间结构暂时稳定；普通校园生活不应被解释成时间异常。"
    elif disturbance < 25:
        band = "local_echo"
        guidance = "局部回声开始出现；可以写入轻微记忆冲突，但不能擅自制造大规模替代现实。"
    elif disturbance < 45:
        band = "historical_fissure"
        guidance = "历史出现裂缝；必须承接已经成立的异常及其人物代价。"
    elif disturbance < 65:
        band = "time_shadow"
        guidance = "时间重影正在侵入现实；只让相关角色和地点受到可解释的影响。"
    elif disturbance < 85:
        band = "reality_split"
        guidance = "现实已经分叉；原始历史不再自动成立，但玩家行动仍优先。"
    elif disturbance < 100:
        band = "collapse_eve"
        guidance = "时间结构接近崩塌；每次行动都应保留明确的后果和选择空间。"
    else:
        band = "temporal_disaster"
        guidance = "时间灾难已经发生；游戏继续在修复、替代现实或余波中生成。"
    triggered = worldline.get("triggered_thresholds", [])
    return {
        "mode": "temporal_disturbance",
        "temporal_disturbance": disturbance,
        "temporal_stability": stability,
        "band": band,
        "last_source": worldline.get("last_source"),
        "current_timeline_id": worldline.get("current_timeline_id", "original_2020"),
        "memory_status": worldline.get("memory_status", "original"),
        "triggered_thresholds": list(triggered) if isinstance(triggered, list) else [],
        "pending_consequence": (
            worldline.get("pending_consequence")
            if isinstance(worldline.get("pending_consequence"), dict)
            else None
        ),
        "changed_nodes": [
            node for node in relevant_nodes if node.get("status") == "altered"
        ],
        "approaching_nodes": [
            node for node in relevant_nodes if node.get("status") == "approaching"
        ],
        "narrative_guidance": guidance,
        "temporal_rule": "普通校园行动、对话、调查和关系变化不增加时间扰动；只有真实触碰时间因果才允许增加。",
    }


def _build_timeline_phase(
    *,
    current_date: date,
    grade: str,
    school: dict[str, Any],
    arc: dict[str, Any],
) -> dict[str, Any]:
    if grade == "left_school":
        phase_id = f"{arc['id']}_after_departure"
        title = f"{arc['title']}·离校后的余波"
        summary = "玩家已经不是在校学生，时代主线仍可作为社会背景，但不得恢复普通学生身份。"
        pressures = ("离校身份限制", "玩家仍可能以成年或非学生身份接触时代事件")
    elif grade == "not_enrolled":
        phase_id = (
            "pre_enrollment_summer"
            if current_date.month in {6, 7, 8}
            else "pre_enrollment"
        )
        title = "来信尚未抵达"
        summary = "魔法世界正在靠近，但玩家尚未完成入学，家庭认知和第一封来信仍是剧情重点。"
        pressures = ("尚未完成入学", "出身决定玩家对魔法界的初始认知")
    else:
        month = current_date.month
        if grade == "year_1":
            phase_id = "first_year_autumn" if month >= 9 or month <= 1 else "first_year_spring"
            title = "城堡的第一道门"
            summary = "新生开始熟悉学院、课程和城堡规则，禁忌区域与陌生人物逐渐进入视野。"
            pressures = ("新生身份限制", "学院关系形成", "城堡异常尚未解释")
        elif grade == "year_3":
            phase_id = "third_year_elective_selection" if school.get("course_selection") else "third_year"
            title = "选择更多道路"
            summary = "课程选择和更复杂的人际关系让玩家开始形成自己的学习方向与校园位置。"
            pressures = ("选修课选择", "更复杂的校园关系", "个人方向逐渐清晰")
        elif grade == "year_5":
            phase_id = "fifth_year_owl"
            title = "O.W.L.前夜"
            summary = "考试、未来道路和战争阴影同时增加，学习选择开始影响成年后的机会。"
            pressures = ("O.W.L.压力", "未来道路选择", "声望与学院立场")
        elif grade == "year_6":
            phase_id = "sixth_year_newt_selection"
            title = "更深的魔法"
            summary = "高年级课程、个人立场和逐渐公开的危险，让学生生活开始接近成年世界。"
            pressures = ("高年级课程门槛", "成年前的责任", "战争消息逐渐逼近")
        elif grade == "year_7":
            phase_id = "seventh_year_newt"
            title = "毕业前的最后一年"
            summary = "N.E.W.T.、个人未来和时代危机彼此交叠，玩家必须决定自己要成为什么样的人。"
            pressures = ("N.E.W.T.压力", "毕业与未来", "个人信念和时代阵营冲突")
        else:
            phase_id = f"{grade}_school_year"
            title = arc["title"]
            summary = arc["summary"]
            pressures = tuple(arc["active_pressures"][:3])

    return {
        "calendar_date": current_date.isoformat(),
        "calendar_year": current_date.year,
        "school_year": school.get("school_year"),
        "term": school.get("term"),
        "grade": grade,
        "phase_id": phase_id,
        "phase_title": title,
        "phase_summary": summary,
        "active_pressures": list(pressures[:3]),
    }


def _build_worldline_pressure(
    *,
    nodes: Iterable[dict[str, Any]],
    statuses: dict[str, str],
    worldline: dict[str, Any],
    relevant_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    node_by_id = {str(node["id"]): node for node in nodes}
    affected = worldline.get("affected_nodes", [])
    affected = affected if isinstance(affected, list) else []
    changed_nodes: list[dict[str, Any]] = []
    known_ids: set[str] = set()
    for raw_node in affected[:8]:
        raw_text = str(raw_node)
        node = node_by_id.get(raw_text) or next(
            (
                candidate
                for candidate in node_by_id.values()
                if raw_text == candidate.get("title")
            ),
            None,
        )
        if node:
            node_id = str(node["id"])
            known_ids.add(node_id)
            changed_nodes.append(_node_for_prompt(node, "altered", "上一轮回合已标记该节点受到世界线影响。"))
        else:
            changed_nodes.append(
                {
                    "id": raw_text,
                    "status": "altered",
                    "title": raw_text,
                    "pressure_summary": "上一轮回合标记了一个受到世界线影响的节点。",
                    "freedom_note": "模型需要结合近期剧情解释其后果，不得凭空抹除既有因果。",
                }
            )

    approaching = [
        _node_for_prompt(node, statuses[str(node["id"])], "节点正在接近当前时间，但不是玩家必须完成的任务。")
        for node in node_by_id.values()
        if statuses[str(node["id"])] == "approaching"
        and str(node["id"]) not in known_ids
    ]
    approaching.sort(key=lambda item: item.get("start_date", ""))
    relevant_ids = {str(node.get("id")) for node in relevant_nodes}
    approaching = [node for node in approaching if node["id"] in relevant_ids or not relevant_ids][:3]

    last_delta = worldline.get("delta", worldline.get("last_delta", 0.0))
    try:
        offset_rate = float(worldline.get("offset_rate", 0.0))
    except (TypeError, ValueError):
        offset_rate = 0.0
    try:
        last_delta = float(last_delta)
    except (TypeError, ValueError):
        last_delta = 0.0
    if offset_rate <= 20:
        offset_band = "low"
        narrative_guidance = "原著主线大致沿原方向发展；可以让事件在远处发生，但不要强迫玩家参与。"
    elif offset_rate <= 60:
        offset_band = "medium"
        narrative_guidance = "部分节点的顺序、人物关系或代价已经改变；必须承接这些变化再推进。"
    else:
        offset_band = "high"
        narrative_guidance = "世界线已显著偏移；仍需保留当前时代人物、历史压力及变化来源，不能凭空改写成无关故事。"

    return {
        "offset_rate": offset_rate,
        "offset_band": offset_band,
        "last_delta": last_delta,
        "reason": str(worldline.get("reason") or ""),
        "changed_nodes": changed_nodes,
        "approaching_nodes": approaching,
        "narrative_guidance": narrative_guidance,
        "worldline_rule": "玩家可以改变事件顺序、参与方式和结局，但每次变化都需要保留因果代价和人物反应。",
    }


def _select_relevant_nodes(
    nodes: Iterable[dict[str, Any]],
    statuses: dict[str, str],
    *,
    action: dict[str, Any],
    location_id: Any,
    memories: Iterable[Any],
) -> list[dict[str, Any]]:
    searchable = _searchable_context(action, location_id, memories)
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for node in nodes:
        node_id = str(node["id"])
        status = statuses[node_id]
        if status not in {"active", "approaching", "altered"}:
            continue
        terms = [str(term).lower() for term in node.get("match_terms", ())]
        matched = any(term and term in searchable for term in terms)
        if not matched and status != "active":
            continue
        relevance = 10 if matched else 3
        if status == "active":
            relevance += 2
        candidates.append((relevance, str(node.get("start_date", "")), _node_for_prompt(
            node,
            status,
            "该节点与当前行动、地点或近期记忆存在关联；仍不得强行替玩家完成节点。",
        )))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [node for _, _, node in candidates[:2]]


def _node_status(node: dict[str, Any], current_date: date, affected_nodes: Any) -> str:
    affected = affected_nodes if isinstance(affected_nodes, list) else []
    node_id = str(node["id"])
    title = str(node.get("title", ""))
    if node_id in {str(item) for item in affected} or title in {str(item) for item in affected}:
        return "altered"
    start = _parse_date(str(node.get("start_date", "")), current_date)
    end = _parse_date(str(node.get("end_date", "")), start)
    if current_date > end:
        return "resolved"
    if start <= current_date <= end:
        return "active"
    if current_date >= start - timedelta(days=180):
        return "approaching"
    return "unavailable"


def _node_for_prompt(node: dict[str, Any], status: str, relevance: str) -> dict[str, Any]:
    return {
        "id": node["id"],
        "title": node["title"],
        "status": status,
        "period": f"{node['start_date']}–{node['end_date']}",
        "importance": node["importance"],
        "pressure_summary": node["pressure_summary"],
        "possible_player_roles": list(node["possible_player_roles"]),
        "relevance": relevance,
        "freedom_note": "anchor_events 是时代背景，不是玩家必须完成的任务；除非时间、地点和因果条件满足，否则不得强行触发。",
    }


def _searchable_context(
    action: dict[str, Any],
    location_id: Any,
    memories: Iterable[Any],
) -> str:
    pieces: list[str] = [str(location_id or "")]
    pieces.extend(
        str(value)
        for value in action.values()
        if isinstance(value, (str, int, float))
    )
    for memory in memories:
        if isinstance(memory, dict):
            pieces.extend(
                str(memory.get(key, ""))
                for key in ("title", "summary", "location_id", "keywords", "actors")
            )
        else:
            pieces.extend(
                str(getattr(memory, key, ""))
                for key in ("title", "summary", "location_id", "keywords", "actors")
            )
    return json.dumps(pieces, ensure_ascii=False).lower()


def _copy_frame(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, (tuple, list)) else value
        for key, value in frame.items()
    }


def _copy_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, (tuple, list)) else value
        for key, value in mapping.items()
    }


def _select_arc(arcs: list[dict[str, Any]], current_date: date) -> dict[str, Any]:
    if (
        arcs
        and arcs[-1].get("id") == "resistance_and_battle"
        and current_date > date(1998, 5, 2)
    ):
        return {
            "id": "postwar_aftermath",
            "period": "1998年5月以后",
            "start_date": "1998-05-03",
            "end_date": "9999-12-31",
            "title": "战后的余波",
            "summary": "战争已经结束，但幸存者、家庭、学校和魔法社会仍在处理失去、重建与被改写的人生。",
            "anchor_events": ("霍格沃茨重建", "战后审判与清算", "幸存者的个人选择"),
            "important_figures": ("哈利·波特", "罗恩·韦斯莱", "赫敏·格兰杰"),
            "active_pressures": ("战争创伤与关系修复", "学校和社会秩序重建", "玩家自己的后续人生"),
            "freedom_note": "主线战争已经结束，不得把已结束的战斗重新写成正在发生；玩家可以建立独立的战后生活。",
        }
    for arc in reversed(arcs):
        if current_date >= _parse_date(arc["start_date"], current_date):
            return arc
    return arcs[0]


def _parse_date(value: Any, fallback: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return fallback


def _split_atmosphere(value: str) -> list[str]:
    return [item.strip(" 。、") for item in value.split("、") if item.strip(" 。、")]
