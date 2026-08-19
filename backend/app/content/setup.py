from backend.app.schemas.game import SetupOption, SetupStep


SETUP_STEPS = [
    SetupStep(
        step=1,
        title="时代",
        description="你的故事发生在哈利·波特就读霍格沃茨的年代。",
        options=[
            SetupOption(
                id="second_generation",
                label="子世代：1991–1998",
                description="从哈利入学前后开始，经历七年的霍格沃茨生活。",
            )
        ],
    ),
    SetupStep(
        step=2,
        title="身份",
        description="告诉我们关于你的基本身份。",
        options=[
            SetupOption(id="custom_identity", label="自定义姓名、性别和生日")
        ],
    ),
    SetupStep(
        step=3,
        title="外貌与体格",
        description="描述你希望在镜子中看到的自己。",
        options=[
            SetupOption(id="custom_appearance", label="自定义外貌与体格")
        ],
    ),
    SetupStep(
        step=4,
        title="家族与血统",
        description="你从怎样的家庭来到魔法世界？",
        options=[
            SetupOption(id="pure_blood", label="纯血家族"),
            SetupOption(id="half_blood", label="混血家庭"),
            SetupOption(id="muggle_born", label="麻瓜出身"),
        ],
    ),
    SetupStep(
        step=5,
        title="童年经历",
        description="选择或描述三项塑造过你的童年经历。",
        options=[
            SetupOption(id="custom_childhood", label="自定义三项童年经历")
        ],
    ),
    SetupStep(
        step=6,
        title="性格倾向",
        description="选择最接近你的性格倾向。",
        options=[
            SetupOption(id="brave", label="勇敢直接"),
            SetupOption(id="thoughtful", label="冷静谨慎"),
            SetupOption(id="kind", label="温和体贴"),
            SetupOption(id="ambitious", label="野心坚定"),
        ],
    ),
    SetupStep(
        step=7,
        title="信仰与价值观",
        description="什么原则会在困难时支撑你？",
        options=[SetupOption(id="custom_values", label="自定义信仰与价值观")],
    ),
    SetupStep(
        step=8,
        title="魔杖",
        description="选择或描述你的魔杖。",
        options=[SetupOption(id="custom_wand", label="自定义木材、杖芯和长度")],
    ),
    SetupStep(
        step=9,
        title="初始天赋",
        description="选择一个最初的专精方向。",
        options=[
            SetupOption(id="charms", label="魔咒"),
            SetupOption(id="transfiguration", label="变形术"),
            SetupOption(id="defense", label="黑魔法防御"),
            SetupOption(id="potions", label="魔药"),
            SetupOption(id="herbology", label="草药学"),
        ],
    ),
    SetupStep(
        step=10,
        title="宠物",
        description="是否有一位动物伙伴与你同行？",
        options=[
            SetupOption(id="owl", label="猫头鹰"),
            SetupOption(id="cat", label="猫"),
            SetupOption(id="toad", label="蟾蜍"),
            SetupOption(id="none", label="暂时没有"),
        ],
    ),
    SetupStep(
        step=11,
        title="初始好友",
        description="选择你希望在故事开始时已经认识的人。",
        options=[
            SetupOption(id="custom_friend", label="自定义初始好友"),
            SetupOption(id="none", label="没有预设好友"),
        ],
    ),
    SetupStep(
        step=12,
        title="剧情起点",
        description="从哪一刻开始进入你的故事？",
        options=[
            SetupOption(id="before_first_letter", label="收到霍格沃茨来信之前"),
            SetupOption(id="diagon_alley", label="前往对角巷购买校用品"),
            SetupOption(id="platform_nine_three_quarters", label="九又四分之三站台"),
        ],
    ),
    SetupStep(
        step=13,
        title="最终确认",
        description="确认角色设定，开始你的霍格沃兹人生。",
        options=[SetupOption(id="confirm", label="确认并开始")],
    ),
]


def get_setup_step(step: int) -> SetupStep:
    return SETUP_STEPS[step - 1]

