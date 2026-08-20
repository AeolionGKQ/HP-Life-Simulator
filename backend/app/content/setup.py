from backend.app.content.eras import ERAS
from backend.app.schemas.game import SetupOption, SetupStep


def option(
    option_id: str,
    label: str,
    description: str = "",
    *,
    value: str | None = None,
    category: str = "",
    appendable: bool = False,
    available: bool = True,
) -> SetupOption:
    return SetupOption(
        id=option_id,
        label=label,
        description=description,
        value=value or label,
        category=category,
        appendable=appendable,
        available=available,
    )


SETUP_STEPS = [
    SetupStep(
        step=1,
        title="时代",
        description="选择故事所在的魔法史时期。当前仅开放剧情内容已经完善的子世代；其余三个世代仍共用相同系统，但需要完成剧情后才可选择。",
        options=[
            option(
                era["id"],
                f"{era['name']}（{era['years']}）",
                f"{era['description']} 主线：{era['mainline']}",
                value=era["id"],
                available=era["available"],
            )
            for era in ERAS
        ],
    ),
    SetupStep(
        step=2,
        title="姓名",
        description="在命运尚未落笔之前，先为这位年轻巫师写下一个名字。它会回荡在羊皮纸、城堡走廊与未来相遇之人的低语中。",
        options=[],
        selection_mode="text",
    ),
    SetupStep(
        step=3,
        title="性别",
        description="分院帽尚未落下，命运仍在等待你的自我定义。选择一个预设，或在墨水中写下你希望世界如何称呼这位角色。",
        options=[
            option("female", "女"),
            option("male", "男"),
        ],
    ),
    SetupStep(
        step=4,
        title="生日",
        description="每个巫师出生的那一天，都像一颗落入时间长河的星辰。请以 YYYY-MM-DD 格式写下这颗星辰亮起的日期，它将成为年龄、记忆与命运流转的起点。",
        options=[],
        selection_mode="text",
    ),
    SetupStep(
        step=5,
        title="外貌与体格",
        description="可点击多个外貌和体格描述词，它们会以逗号分隔追加到输入框；也可以继续自行修改。",
        selection_mode="append",
        options=[
            option("black_hair", "乌黑短发", "利落而容易打理。", category="发型", appendable=True),
            option("curly_hair", "蓬松卷发", "常常不太服从梳子。", category="发型", appendable=True),
            option("auburn_hair", "赤褐长发", "在烛光下泛着暖色。", category="发型", appendable=True),
            option("blond_hair", "淡金色头发", "颜色浅而醒目。", category="发型", appendable=True),
            option("green_eyes", "碧绿色眼睛", "目光清亮，颜色少见。", category="眼睛", appendable=True),
            option("grey_eyes", "浅灰色眼睛", "显得冷静而敏锐。", category="眼睛", appendable=True),
            option("brown_eyes", "深褐色眼睛", "温和而沉稳。", category="眼睛", appendable=True),
            option("freckles", "鼻梁有雀斑", "带着少年人的亲切感。", category="特征", appendable=True),
            option("pale", "肤色苍白", "像长期待在图书馆或阴雨天气里。", category="特征", appendable=True),
            option("scar", "眉尾有一道浅疤", "像是一次童年意外留下的痕迹。", category="特征", appendable=True),
            option("slender", "身形纤细", "动作轻快，但力量并不突出。", category="体格", appendable=True),
            option("sturdy", "体格结实", "耐力不错，适合长时间活动。", category="体格", appendable=True),
            option("tall", "身材高挑", "在人群里很容易被看见。", category="体格", appendable=True),
            option("small", "个子娇小", "灵活，擅长穿过狭窄空间。", category="体格", appendable=True),
            option("athletic", "动作矫健", "平衡感和运动能力出色。", category="体格", appendable=True),
        ],
    ),
    SetupStep(
        step=6,
        title="出身",
        description="血统会影响童年环境和部分巫师的初始态度，但不会决定你的能力与选择。",
        options=[
            option(
                "pure_blood",
                "纯血家族",
                "父母双方都是巫师。你从小熟悉会动的照片、猫头鹰邮递和魔法社会礼仪，也可能背负古老家族的声誉与偏见。",
            ),
            option(
                "half_blood",
                "混血家庭",
                "家庭同时连接魔法界与麻瓜世界。你对两边都不完全陌生，也常常要在两套生活方式之间寻找自己的位置。",
            ),
            option(
                "muggle_born",
                "麻瓜出身",
                "父母都是麻瓜。魔法曾以无法解释的意外出现在童年里，而霍格沃茨来信将第一次为这些怪事给出答案。",
            ),
        ],
    ),
    SetupStep(
        step=7,
        title="童年经历",
        description="选择塑造过你的经历，也可以补充自己的故事。建议选择三项。",
        selection_mode="append",
        options=[
            option("accidental_magic", "受欺负时意外让玻璃全部碎裂", "第一次强烈的失控魔法。", appendable=True),
            option("roof_escape", "惊慌时突然出现在屋顶上", "一次连自己都无法解释的逃脱。", appendable=True),
            option("talking_portrait", "曾和家中画像偷偷交谈", "纯血或混血家庭常见的童年秘密。", appendable=True),
            option("garden_bloom", "情绪高涨时让花园反季节盛开", "魔力以温和方式显现。", appendable=True),
            option("family_broom", "偷骑家里的旧扫帚并摔进树篱", "危险但难忘的第一次飞行。", appendable=True),
            option("knockturn_lost", "在翻倒巷附近短暂走失", "见过不该由孩子接触的黑暗角落。", appendable=True),
            option("owl_rescue", "照料过一只受伤的猫头鹰", "学会与魔法动物建立耐心的信任。", appendable=True),
            option("muggle_school", "在麻瓜学校隐藏反常能力", "习惯在被注视时压抑魔法。", appendable=True),
            option("family_duel", "目睹家族成员因观念不同发生决斗", "很早便理解咒语也能伤害亲近的人。", appendable=True),
            option("storybook", "沉迷《诗翁彼豆故事集》", "对古老巫师传说和寓言充满兴趣。", appendable=True),
            option("ghost_encounter", "在旧宅里遇见过一位幽灵", "从此对死亡和灵魂有了不同看法。", appendable=True),
            option("heirloom", "被托付保管一件不知用途的家族遗物", "一件可能在未来唤醒秘密的旧物。", appendable=True),
        ],
    ),
    SetupStep(
        step=8,
        title="性格",
        description="选择最贴近你的核心性格，之后的经历仍会让角色逐渐改变。",
        selection_mode="append",
        options=[
            option("brave", "勇敢直接", "面对危险时倾向先行动，再承担后果。"),
            option("thoughtful", "冷静谨慎", "习惯观察、求证，不轻易暴露真实想法。"),
            option("kind", "温和体贴", "能感受到他人的不安，愿意提供帮助。"),
            option("ambitious", "野心坚定", "清楚自己想要什么，并愿意为目标长期努力。"),
            option("curious", "好奇求知", "无法容忍未解之谜，常被秘密吸引。"),
            option("rebellious", "叛逆不羁", "对不合理的权威和规则保持本能怀疑。"),
            option("loyal", "重情忠诚", "一旦认可某人，就很难在危机中抛下对方。"),
            option("witty", "机敏幽默", "善用玩笑化解压力，也可能用讽刺保护自己。"),
            option("reserved", "内敛寡言", "不易亲近，但会记住每一次真诚。"),
            option("competitive", "好胜进取", "渴望在课堂、魁地奇或决斗中证明自己。"),
            option("principled", "原则坚定", "有清晰底线，即使吃亏也不愿轻易跨越。"),
            option("adaptable", "圆滑善变", "擅长理解局势，在不同人群中调整自己的表现。"),
        ],
    ),
    SetupStep(
        step=9,
        title="信仰与价值观",
        description="选择角色在故事开始时认同的观念。价值观可能在经历中受到挑战或改变。",
        selection_mode="append",
        options=[
            option("equality", "血统平等", "魔法能力与人格不应由出身评判。", appendable=True),
            option("pure_supremacy", "纯血至上", "相信古老巫师血统应拥有更高地位；这一观念会引发明显的社会冲突。", appendable=True),
            option("merit", "能力至上", "出身不重要，真正重要的是知识、力量与成就。", appendable=True),
            option("tradition", "尊重巫师传统", "古老礼仪和制度值得维护，但未必拒绝一切改变。", appendable=True),
            option("reform", "魔法社会改革", "认为魔法部和学校都需要变得更公平透明。", appendable=True),
            option("secrecy", "保密法不可动摇", "巫师世界只有保持隐秘才能免于灾难。", appendable=True),
            option("muggle_bridge", "巫师与麻瓜应增进理解", "隔绝会滋生恐惧，交流才能减少冲突。", appendable=True),
            option("knowledge", "知识不应被禁止", "危险知识应被谨慎研究，而不是简单封存。", appendable=True),
            option("anti_dark", "黑魔法绝不可触碰", "某些力量从一开始就会腐蚀施法者。", appendable=True),
            option("means", "力量本身无善恶", "真正需要判断的是目的、代价和使用者。", appendable=True),
            option("loyalty_first", "家人与同伴优先", "制度和名誉都不能凌驾于重要的人之上。", appendable=True),
            option("fate", "相信预言与命运", "星象和预言揭示了无法轻易逃脱的道路。", appendable=True),
        ],
    ),
    SetupStep(
        step=10,
        title="魔杖",
        description="选择一种木材和一种杖芯，也可补充长度与柔韧性。奥利凡德强调：是魔杖选择巫师。",
        selection_mode="append",
        options=[
            option("holly", "冬青木", "罕见而具有保护性，常选择需要克服冲动、踏上危险精神旅程的人。", category="木材", appendable=True),
            option("yew", "紫杉木", "稀有而强大，与生死、决斗和非凡使命有深刻联系。", category="木材", appendable=True),
            option("oak", "英国橡木", "忠诚可靠，偏爱勇敢、忠实且直觉敏锐的主人。", category="木材", appendable=True),
            option("ash", "白蜡木", "极重忠诚，通常只认定一位主人，适合意志坚定者。", category="木材", appendable=True),
            option("willow", "柳木", "具有疗愈倾向，常选择怀有不必要不安全感、但潜力出众的人。", category="木材", appendable=True),
            option("hazel", "榛木", "敏感，会映照主人的情绪，也常与洞察力和疗愈能力相合。", category="木材", appendable=True),
            option("vine", "葡萄藤木", "常选择追求更高目标、拥有独特眼界且富有深度的人。", category="木材", appendable=True),
            option("hawthorn", "山楂木", "矛盾而复杂，既适合疗愈也适合诅咒，偏爱内心冲突者。", category="木材", appendable=True),
            option("cherry", "樱桃木", "罕见且力量奇异，绝非仅仅华美，尤其需要自制力。", category="木材", appendable=True),
            option("chestnut", "栗木", "性格多面，常亲近神奇动物驯养者、草药学好手和天生飞行者。", category="木材", appendable=True),
            option("cypress", "柏木", "与勇气、自我牺牲和无畏面对死亡的品质相合。", category="木材", appendable=True),
            option("redwood", "红杉木", "偏爱能绝处逢生、抓住时机并从灾难中取得优势的人。", category="木材", appendable=True),
            option("unicorn", "独角兽毛", "魔法稳定、忠诚且不易转向黑魔法，但通常并非最强力。", category="杖芯", appendable=True),
            option("dragon", "龙心弦", "力量强、学习快，容易产生华丽魔法，但性情更不稳定。", category="杖芯", appendable=True),
            option("phoenix", "凤凰羽毛", "魔法范围最广、最有自主性，也最挑剔且最难驯服。", category="杖芯", appendable=True),
            option("length_short", "十英寸", "相对短小，适合精确紧凑的施法风格。", category="规格", appendable=True),
            option("length_medium", "十一又四分之一英寸", "常见而均衡的长度。", category="规格", appendable=True),
            option("length_long", "十二又四分之三英寸", "较长，通常配合更宽展的施法动作。", category="规格", appendable=True),
            option("flexible", "柔韧", "更容易适应变化和新的施法方式。", category="规格", appendable=True),
            option("unyielding", "坚硬", "意志鲜明，需要与主人建立稳定一致的配合。", category="规格", appendable=True),
        ],
    ),
    SetupStep(
        step=11,
        title="魔法天赋",
        description="选择一种罕见或鲜明的先天天赋。天赋代表潜力，而不是无需学习就能掌握力量。",
        selection_mode="append",
        options=[
            option("abundant_magic", "魔力充盈", "魔力储量天生高于同龄人，长时间施法更有优势，但精细控制仍需训练。"),
            option("creature_affinity", "神奇生物亲和", "更容易获得神奇生物的信任，并敏锐察觉它们的情绪。"),
            option("dark_aptitude", "黑魔法专精", "对诅咒与黑魔法结构有异常敏锐的理解力，也更容易面对诱惑与猜忌。"),
            option("spell_instinct", "咒语直觉", "能快速把握咒语的节奏与发音，学习新魔咒时事半功倍。"),
            option("transfiguration_mind", "变形思维", "擅长理解形态、结构和物质之间的关系。"),
            option("potion_sense", "魔药感知", "能从气味、颜色和火候中捕捉配方偏差。"),
            option("mental_fortress", "精神壁垒", "意志坚韧，对恐惧、迷惑和精神侵扰有较强抵抗力。"),
            option("emotional_resonance", "情绪共鸣", "容易感知他人强烈情绪，有利于理解人心，也可能被情绪淹没。"),
            option("flight_talent", "飞行天赋", "骑上扫帚后能本能地保持平衡、判断风向和路线。"),
            option("ancient_runes", "古代魔文亲和", "对古老文字、符号与魔法结构有天然敏感度。"),
            option("prophetic_dreams", "预兆梦", "偶尔会在梦中捕捉未来的碎片，但象征往往含混且可能误导。"),
            option("wandless_spark", "无杖魔法火花", "在强烈情绪下更容易触发无杖魔法，但远未达到稳定施法。"),
        ],
    ),
    SetupStep(
        step=12,
        title="宠物",
        description="普通学生最常携带猫头鹰、猫或蟾蜍；其他神奇动物可能需要额外照料、许可或承担麻烦。",
        options=[
            option("owl", "猫头鹰", "可靠的信使，能在长途旅程中找到收件人。"),
            option("cat", "猫", "敏锐而独立，有些猫似乎能察觉不可信的人。"),
            option("toad", "蟾蜍", "传统、安静、容易照料，但也容易在城堡里走丢。"),
            option("rat", "宠物鼠", "体型小，容易携带；它究竟有多聪明取决于个体。"),
            option("kneazle", "猫狸子", "聪明、独立，能识破可疑之人；纯种猫狸子可能受饲养管理限制。"),
            option("kneazle_hybrid", "猫狸子混血猫", "兼具家猫的亲近与猫狸子的判断力，更适合学生生活。"),
            option("puffskein", "蒲绒绒", "温顺的球状小生物，喜欢被拥抱，会用长舌头寻找食物。"),
            option("bowtruckle", "护树罗锅", "害羞的树木守护者，偏爱木虱和仙子蛋，需要稳定的木质栖息环境。"),
            option("niffler", "嗅嗅", "亲昵但痴迷闪亮物品，可能把宿舍和同学口袋翻得一团糟。"),
            option("raven", "渡鸦", "聪明而善于模仿声音，但不是霍格沃茨标准宠物。"),
            option("none", "暂时没有", "先适应学校生活，未来仍可能在剧情中遇见伙伴。"),
        ],
    ),
    SetupStep(
        step=13,
        title="初始好友",
        description="可选择多位原著人物，也可以输入自定义姓名。选择的人物会以朋友身份进入关系列表并获得初始好感。",
        selection_mode="append",
        options=[
            option("harry_potter", "哈利·波特", "安静但勇敢，对真诚的友谊十分珍惜。", value="哈利·波特", appendable=True),
            option("ron_weasley", "罗恩·韦斯莱", "幽默热情，熟悉巫师世界，也很在意自己是否被重视。", value="罗恩·韦斯莱", appendable=True),
            option("hermione_granger", "赫敏·格兰杰", "认真聪明，对知识和规则充满热情。", value="赫敏·格兰杰", appendable=True),
            option("draco_malfoy", "德拉科·马尔福", "骄傲敏锐，重视家族和身份，友谊也常伴随立场。", value="德拉科·马尔福", appendable=True),
            option("neville_longbottom", "纳威·隆巴顿", "善良而羞怯，需要有人发现他尚未展现的勇气。", value="纳威·隆巴顿", appendable=True),
            option("ginny_weasley", "金妮·韦斯莱", "年纪稍小，机敏坚定，熟悉热闹的大家庭生活。", value="金妮·韦斯莱", appendable=True),
            option("luna_lovegood", "卢娜·洛夫古德", "要到后续学年才入学；想象力独特，不太在意旁人的评价。", value="卢娜·洛夫古德", appendable=True),
            option("fred_weasley", "弗雷德·韦斯莱", "热衷恶作剧和冒险，对有趣的人格外友好。", value="弗雷德·韦斯莱", appendable=True),
            option("george_weasley", "乔治·韦斯莱", "善于观察同伴，常和弗雷德一起把规则变成玩笑。", value="乔治·韦斯莱", appendable=True),
            option("cedric_diggory", "塞德里克·迪戈里", "高年级学生，正直、谦逊并具有公平竞争精神。", value="塞德里克·迪戈里", appendable=True),
        ],
    ),
    SetupStep(
        step=14,
        title="剧情起点",
        description="选择故事真正开始的时刻。越晚的起点会略过此前流程，但不会抹去角色背景。",
        options=[
            option("before_first_letter", "收到霍格沃茨来信之前", "从魔法尚未得到解释的普通早晨开始。"),
            option("diagon_alley", "第一次踏入对角巷", "从采购魔杖、长袍、课本和坩埚开始。"),
            option("platform_nine_three_quarters", "九又四分之三站台", "从蒸汽、猫头鹰叫声和即将启程的列车开始。"),
            option("sorting_ceremony", "分院时", "直接从礼堂的烛光、四张长桌和分院帽落到头顶的那一刻开始。"),
        ],
    ),
    SetupStep(
        step=15,
        title="学院",
        description=(
            "礼堂上空，千万支烛火在夜色中静静漂浮；四张长桌旁，等待已久的目光纷纷投向你。"
            "那顶古老的分院帽低声翻阅你的勇气、忠诚、智慧与抱负，准备为未来七年的归处唱出答案。"
            "此刻，请从霍格沃茨四大学院中选择一个，让它的名字落在你的命运卷宗上。"
        ),
        options=[
            option("gryffindor", "格兰芬多", "重视勇气、胆识与在困难面前坚持的决心。", value="gryffindor"),
            option("hufflepuff", "赫奇帕奇", "重视忠诚、勤劳、公平与对同伴的真诚。", value="hufflepuff"),
            option("ravenclaw", "拉文克劳", "重视智慧、求知欲、创造力与独立思考。", value="ravenclaw"),
            option("slytherin", "斯莱特林", "重视目标、机敏、资源整合与实现抱负的决心。", value="slytherin"),
        ],
    ),
    SetupStep(
        step=16,
        title="选择你的守护神",
        description=(
            "在银白色的雾光真正回应咒语以前，先辨认可能守护你灵魂的形态。"
            "犬、猫与马是巫师中较常见的守护神，其他动物也会映照独特的记忆、性格与羁绊。"
            "选择一个预设，或写下只属于你的守护神。此时它仍是潜在形态；"
            "角色未学会【呼神护卫】时无法将它召唤出来。"
        ),
        options=[
            option("dolphin", "海豚", "灵动而亲近同伴，像一道穿过黑暗水面的银光。"),
            option("cat", "猫", "敏锐、独立而富有好奇心，会无声守在最需要它的地方。"),
            option("dog", "犬", "忠诚、热情且勇于保护同伴，是魔法界常见的守护形态。"),
            option("horse", "马", "自由而坚韧，带着沉稳的力量穿越恐惧与长夜。"),
            option("stag", "雄鹿", "高贵、勇敢而坚定，昂首挡在危险与所爱之人之间。"),
            option("doe", "牝鹿", "温柔、警觉而执着，以安静的光芒指引迷途者。"),
            option("otter", "水獭", "聪慧、活泼而富有韧性，总能在湍流中找到方向。"),
            option("hare", "野兔", "机敏、迅捷而富有直觉，会在危机逼近前跃入月光。"),
            option("fox", "狐狸", "善于观察、适应与寻找隐秘道路，很少被表象欺骗。"),
            option("wolf", "狼", "坚韧而重视羁绊，既能独自行走，也会守护认定的同伴。"),
        ],
    ),
    SetupStep(
        step=17,
        title="补充你自己",
        description=(
            "命运卷宗已经写满姓名、出身与天赋，却仍为你留着最后一块空白。"
            "在这里写下任何还想让魔法世界记住的设定：习惯、恐惧、愿望、秘密、"
            "口头禅，或一段无人知晓的往事。也可以什么都不写，让未来的经历亲自留下答案。"
        ),
        options=[],
        selection_mode="text",
    ),
    SetupStep(
        step=18,
        title="最终确认",
        description="烛火掠过命运卷宗的最后一页。请检查完整角色设定；确认后将生成初始状态与好友关系，并从选定起点开启故事。",
        options=[option("confirm", "确认并开始", "角色创建完成后仍可在剧情中成长和改变。")],
        selection_mode="confirm",
    ),
]


def get_setup_step(step: int) -> SetupStep:
    return SETUP_STEPS[step - 1]
