from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any, Iterable

from backend.app.content.eras import get_era
from backend.app.content.modern_cast import modern_cast_index
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
        memories=memories,
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

    return {
        "id": era["id"],
        "name": era["name"],
        "years": era["years"],
        "era_frame": _copy_frame(content["era_frame"]),
        "generation_mainline": era["mainline"],
        "mainline_phase": {
            "id": arc["id"],
            "title": arc["title"],
            "period": arc["period"],
            "summary": arc["summary"],
            "anchor_events": list(arc["anchor_events"]),
            "important_figures": list(arc["important_figures"]),
            "active_pressures": list(arc["active_pressures"]),
            "freedom_note": arc["freedom_note"],
        },
        "timeline_phase": timeline_phase,
        "relevant_nodes": relevant_nodes,
        "freedom_rules": list(content["freedom_rules"]),
        "worldline_pressure": pressure,
        "cast_index": content.get("cast_index", []),
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
