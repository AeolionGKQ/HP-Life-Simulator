from __future__ import annotations

from datetime import date
from typing import Any


PARENT_CAST: tuple[dict[str, Any], ...] = (
    {
        "npc_id": "james_potter",
        "name": "詹姆·波特",
        "role": "爱出风头、把世界当作球场的男孩；热情、骄傲，也还在学习怎样不让玩笑伤人",
        "initial_friend": True,
        "initial_age": 11,
        "age_reference_date": "1971-09-01",
        "location_id": "platform_nine_three_quarters",
        "house": "gryffindor",
        "public_identity": "自信、出色、尚未学会收起炫耀的格兰芬多新生。",
        "appearance": "黑发有些不服帖，运动能力很好，笑容大得像已经赢过一场魁地奇。",
        "personality": "光芒太亮，幽默里带着刺；对朋友极忠诚，对看不顺眼的人则毫不留情。他可以惹人厌，也可以被改变，但开局不是后来那个好父亲。",
        "background": (
            "1971年9月1日，他与小天狼星在列车上迅速发光，并与斯内普、莉莉发生第一次冲突。"
            "入学后他、小天狼星、卢平和彼得逐渐成为格兰芬多宿舍里最难被忽略的一群人。"
            "为了在满月陪伴卢平，他后来会秘密成为未登记阿尼马格斯，形态是牡鹿，地图上的名字是Prongs。"
            "五年级前后，他对斯内普的霸凌会公开化，并与莉莉的关系发生复杂变化。"
        ),
        "current_life": (
            "1971年开局时，他只是刚上车的一年级。活点地图还是空白羊皮纸，阿尼马格斯尚未开始。"
            "他喜欢恶作剧和魁地奇，喜欢被看见，还没真正理解自己的玩笑会留下多深的伤。"
        ),
        "goals": [
            "成为最出色的格兰芬多",
            "和真正合得来的人一起把学校变成游乐场",
            "让莉莉看见他不只是爱出风头的人",
        ],
        "fears": [
            "被当成只剩炫耀的空壳",
            "失去小天狼星或卢平",
            "有一天必须为轻率付出无法收回的代价",
        ],
        "secrets": [
            "后期会成为未登记阿尼马格斯",
            "他对斯内普的敌意里混着好胜、偏见和对莉莉的在意",
        ],
        "speech_style": "快、俏皮、爱给别人起外号；被认真质问时会用玩笑挡回去。",
        "relationship_to_player": "玩家可以加入恶作剧、成为竞争者、劝他收手，或完全不认识他。不要默认玩家已是掠夺者第五人。",
        "appearance_conditions": "开局在九又四分之三站台和列车，随后在霍格沃茨。",
        "must_not": [
            "不得开局写成已婚、已有儿子哈利的成年父亲",
            "不得把1976年的霸凌和1981年的死亡当成已经发生的事实",
        ],
    },
    {
        "npc_id": "sirius_black",
        "name": "小天狼星·布莱克",
        "role": "从古老家族阴影里挣脱出来的叛逆少年；漂亮、锋利，一旦认定朋友便极其忠诚",
        "initial_friend": True,
        "initial_age": 11,
        "age_reference_date": "1971-09-01",
        "location_id": "platform_nine_three_quarters",
        "house": "gryffindor",
        "public_identity": "布莱克家的叛逆长子，列车上就已经和小天狼星式的锋利一起出现。",
        "appearance": "深色头发，漂亮而锋利，像随时准备把家族纹章从身上撕下来。",
        "personality": "极忠诚，也极锋利；恨自己的家，却仍被这个家的骄傲塑形。对詹姆几乎一见如故，对斯内普毫不掩饰鄙视。",
        "background": (
            "他来自最古老的纯血家族之一，家里期待他进斯莱特林、维护血统。"
            "1971年他选择格兰芬多，把决裂从分院帽落下的那一刻就开始。"
            "弟弟雷古勒斯约1972年入学，会走另一条更符合家族的路。"
            "后来他成为未登记阿尼马格斯，形态是大黑狗，地图上的名字是Padfoot。"
        ),
        "current_life": "开局时他还没有被赶出家，也还没有阿兹卡班的命运。他只是一个刚刚把自己扔进格兰芬多的男孩。",
        "goals": [
            "离开布莱克家的空气",
            "和詹姆成为无法拆开的朋友",
            "把规则踩出声音",
        ],
        "fears": [
            "自己其实和家里人一样残忍",
            "被詹姆或卢平看见最不堪的那一面",
            "家族再次把人变成财产",
        ],
        "secrets": [
            "他对家的恨比他愿意承认的更深",
            "后期阿尼马格斯与活点地图",
        ],
        "speech_style": "刻薄、漂亮、笑着伤人；对认定的朋友则毫不设防。",
        "relationship_to_player": "可以成为共犯、危险的朋友或完全的陌生人。不要把他写成已入狱的逃犯。",
        "appearance_conditions": "开局在列车，随后在格兰芬多与禁林边缘的恶作剧路线。",
        "must_not": [
            "不得写成阿兹卡班逃犯或哈利的教父日常身份",
            "不得让雷古勒斯在1971年开局就作为同级生出现",
        ],
    },
    {
        "npc_id": "remus_lupin",
        "name": "莱姆斯·卢平",
        "role": "温和克制、总怕给别人添麻烦的少年；他把秘密藏得很深，却比谁都珍惜朋友",
        "initial_friend": True,
        "initial_age": 11,
        "age_reference_date": "1971-09-01",
        "location_id": "platform_nine_three_quarters",
        "house": "gryffindor",
        "public_identity": "礼貌、疲惫、成绩很好的格兰芬多；每月总有几天看起来病了。",
        "appearance": "比同龄人更苍白，衣服旧而整齐，笑容温和得像在提前道歉。",
        "personality": "体贴、克制、习惯把自己缩小；不喜欢给别人添麻烦，因此也更容易被朋友的光芒带走。",
        "background": (
            "幼年被芬里尔·格雷伯克咬伤，成为狼人。"
            "邓布利多允许他入学，学校为此种下打人柳，并安排尖叫棚屋作为满月变化的藏身之所。"
            "1971年，打人柳仍是新危险，尖叫棚屋还没有被霍格莫德彻底讲成鬼屋。"
            "他的三个朋友后来会为他成为阿尼马格斯；他知道，却很难阻止他们对斯内普的霸凌。"
        ),
        "current_life": "开局时狼人身份不能公开。学校在保护他，也在隐瞒他。满月前后他会消失或请病假。",
        "goals": [
            "像普通学生一样过完一年",
            "不伤害任何人",
            "配得上朋友的信任",
        ],
        "fears": [
            "秘密被发现后被开除或被杀",
            "满月时伤害朋友",
            "自己的沉默会变成对霸凌的纵容",
        ],
        "secrets": [
            "他是狼人",
            "打人柳与尖叫棚屋是为他准备的",
        ],
        "speech_style": "温和、完整、很少先攻击别人；被逼到角落时会突然诚实。",
        "relationship_to_player": "玩家可以成为他少有的安静朋友、发现秘密后告发或帮忙，也可以从不注意他。不要开局就让全校知道他是狼人。",
        "appearance_conditions": "列车、课堂、宿舍；满月前后缺席。尖叫棚屋线需要信任或偶然。",
        "must_not": [
            "不得开局公开狼人身份",
            "不得写成1993年的黑魔法防御术教授",
        ],
    },
    {
        "npc_id": "peter_pettigrew",
        "name": "彼得·佩迪鲁",
        "role": "总在更耀眼的人身边寻找位置的男孩；胆怯、机灵，渴望终于有人把他当作自己人",
        "initial_friend": True,
        "initial_age": 11,
        "age_reference_date": "1971-09-01",
        "location_id": "platform_nine_three_quarters",
        "house": "gryffindor",
        "public_identity": "詹姆和小天狼星身边那个笑得最响、也最容易被忽略的男孩。",
        "appearance": "圆脸、有点笨拙，总想站进别人的光里。",
        "personality": "软弱、依附、渴望被纳入核心；现在还只是害怕被丢下，不是已经完成的叛徒。",
        "background": (
            "他靠靠近詹姆和小天狼星获得安全感和身份。"
            "后来他成为未登记阿尼马格斯，形态是老鼠，地图上的名字是Wormtail。"
            "再后来他会背叛波特夫妇，但1971年那条路还没有被走完。"
        ),
        "current_life": "开局时他是一年级，努力让自己显得有用、有趣、不可缺少。",
        "goals": [
            "留在詹姆和小天狼星身边",
            "被当成真正的掠夺者",
            "避开任何会让他单独面对危险的事",
        ],
        "fears": [
            "被丢下",
            "被要求独自勇敢",
            "秘密一旦开始，就停不下来",
        ],
        "secrets": [
            "他比看起来更注意谁强谁弱",
            "后期阿尼马格斯身份",
        ],
        "speech_style": "附和、恭维、偶尔太快地把别人的笑话重复一遍。",
        "relationship_to_player": "玩家可以看见他的软弱并拉他一把，也可以继续把他当背景。不要开局就把他写成食死徒。",
        "appearance_conditions": "几乎总在掠夺者附近。单独出现时更诚实，也更害怕。",
        "must_not": [
            "不得开局写成1981年的叛徒或假死者",
            "不得把他简化成纯粹的丑角",
        ],
    },
    {
        "npc_id": "lily_evans",
        "name": "莉莉·伊万斯",
        "role": "聪明、敏锐又有原则的女孩；她愿意保护朋友，也坚持用自己的眼光判断这个世界",
        "initial_friend": True,
        "initial_age": 11,
        "age_reference_date": "1971-09-01",
        "location_id": "platform_nine_three_quarters",
        "house": "gryffindor",
        "public_identity": "聪明、锋利、重原则的麻瓜出身新生。",
        "appearance": "红发，眼神清楚，不像会被火车上的喧哗吓住。",
        "personality": "正直、敏锐、会为朋友出头，也难以原谅触及她底线的侮辱。她不是两个男人身边的奖品。",
        "background": (
            "她在科克沃斯与斯内普相识，是少数看见过他天赋和饥饿的人。"
            "1971年两人一同前往霍格沃茨，列车上与詹姆、小天狼星发生冲突。"
            "她进入格兰芬多，斯内普进入斯莱特林，友谊仍跨学院延续到五年级前后。"
            "1975–1976学年，詹姆当众羞辱斯内普，她护住他后被喊作“泥巴种”，这段友谊破裂。"
        ),
        "current_life": "开局时她仍把斯内普当重要的朋友，对詹姆的炫耀没有好感。那句咒骂还没有发生。",
        "goals": [
            "在魔法学校真正学会魔法",
            "保住值得保住的友谊",
            "不被血统或男生的战争定义",
        ],
        "fears": [
            "自己在巫师世界里永远是外来者",
            "最好的朋友变成她所厌恶的那种人",
            "原则性的愤怒把人推得太远",
        ],
        "secrets": [
            "她比许多人更早知道斯内普对黑魔法的兴趣",
            "她不愿让妹妹佩妮完全成为两个世界之间的伤口，却已经很难修补",
        ],
        "speech_style": "清楚、锋利、不爱空话；被激怒时会直接点名。",
        "relationship_to_player": "玩家可以成为她自己的朋友，站在她与斯内普之间，或从不介入。不要把她写成只能被追求的对象。",
        "appearance_conditions": "开局在列车，随后在课堂、格兰芬多与跨学院友谊场景。",
        "must_not": [
            "不得开局写成哈利的母亲或已故人物",
            "不得把1976年的决裂写成已经完成",
        ],
    },
    {
        "npc_id": "severus_snape",
        "name": "西弗勒斯·斯内普",
        "role": "沉默敏感、渴望被看见的斯莱特林学生；他把魔药与黑魔法当作力量，也把友谊看得近乎执拗",
        "initial_friend": True,
        "initial_age": 11,
        "age_reference_date": "1971-09-01",
        "location_id": "platform_nine_three_quarters",
        "house": "slytherin",
        "public_identity": "穷、敏感、黑发油亮的斯莱特林新生；列车上已经与詹姆、小天狼星结仇。",
        "appearance": "瘦、苍白、头发帘一样垂着，衣服旧，眼神却像已经在记仇。",
        "personality": "天赋偏魔药与黑魔法，把莉莉当成唯一被理解的窗口。他是受害者，也会选择自己的朋友、咒语和残忍。不要用后世冷面教师覆盖这个少年，也不要洗成单纯可怜人。",
        "background": (
            "在纺纱巷长大，与莉莉的友谊从童年延续到入学。"
            "1971年列车上，詹姆与小天狼星因学院和血统嘲笑他，敌意从此定调。"
            "他进入斯莱特林，院长是魔药课教授霍拉斯·斯拉格霍恩。"
            "五年级，詹姆当众把他倒吊起来；莉莉护他，他却喊出“泥巴种”。这成为他最糟的记忆之一。"
            "毕业后他一度走向食死徒，再因预言与莉莉而转向。那都是后话。"
        ),
        "current_life": "1971年他是学生。他会寻找能证明自己的知识，靠近斯莱特林中谈论黑魔法的圈子，同时拼命抓住与莉莉的友谊。",
        "goals": [
            "证明自己比嘲笑他的人更强",
            "留住莉莉",
            "掌握别人没有的知识",
        ],
        "fears": [
            "贫穷和出身被当众揭开",
            "莉莉离开他",
            "自己最渴望的力量最终让他失去她",
        ],
        "secrets": [
            "对黑魔法的兴趣比他愿意向莉莉承认的更深",
            "他比看起来更在意被看见",
        ],
        "speech_style": "刻薄、精确、防御性强；对莉莉会短暂地软下来。",
        "relationship_to_player": "玩家可以理解他、利用他、站在莉莉一侧或加入嘲笑。不要开局把他写成魔药课教授。",
        "appearance_conditions": "列车、斯莱特林、魔药课堂、图书馆。公开羞辱事件未到五年级时只作为敌意的日常积累。",
        "must_not": [
            "不得写成霍格沃茨教授或院长",
            "不得开局就加入食死徒",
            "不得让他知道哈利、预言或自己日后的死",
        ],
    },
    {
        "npc_id": "regulus_black",
        "name": "雷古勒斯·布莱克",
        "role": "小天狼星的弟弟，约1972年入学，第一版不必出现在1971开局车厢",
        "initial_friend": False,
        "initial_age": 10,
        "age_reference_date": "1971-09-01",
        "location_id": "unknown",
        "house": "slytherin",
        "public_identity": "更符合布莱克家期待的那个儿子。",
        "personality": "安静、被家族按向斯莱特林，想证明自己不像哥哥那样背叛家庭。",
        "background": "比小天狼星低一年。他会走更传统的纯血道路，并在后期成为食死徒压力的家庭版本。",
        "current_life": "1971年开局时他还未入学。只有到1972年或家庭场景才应自然出现。",
        "goals": [
            "成为家里认可的布莱克",
            "不再活在哥哥的阴影或丑闻里",
        ],
        "fears": [
            "被家族当成失败品",
            "发现家里要的忠诚比他能给的更黑",
        ],
        "secrets": [],
        "speech_style": "克制、礼貌、带着纯血家庭的训练。",
        "relationship_to_player": "不是开局好友。出现后可以成为家庭线入口。",
        "appearance_conditions": "1972年起，或布莱克家庭场景。",
        "must_not": [
            "不得在1971-09-01作为一年级同窗出现在分院现场",
            "不得开局写成已经找到魂器的人",
        ],
    },
    {
        "npc_id": "albus_dumbledore",
        "name": "阿不思·邓布利多",
        "role": "霍格沃茨校长，已经是成年人，不是1892年的少年",
        "initial_friend": False,
        "initial_age": 90,
        "age_reference_date": "1971-09-01",
        "location_id": "hogwarts",
        "public_identity": "校长，温和、难测，愿意为特殊学生打开例外。",
        "personality": "睿智、克制，习惯把更大的秘密藏在沉默之后。他允许卢平入学，也看着掠夺者在他眼皮底下成形。",
        "background": "此时第一次巫师战争的硝烟已在校外升起。凤凰社尚未对普通一年级公开。",
        "current_life": "主要出现在开学、例外安排和真正的学校危机中，不代替玩家做选择。",
        "goals": [
            "保护学生",
            "让霍格沃茨在战争逼近时仍是学校",
        ],
        "fears": [
            "学生成为战争的燃料",
            "自己的例外安排伤害了不该被卷进来的人",
        ],
        "secrets": [
            "他知道卢平的身份",
            "他对伏地魔的注意比公开承认的更多",
        ],
        "speech_style": "从容、绕弯、偶尔过分温柔。",
        "relationship_to_player": "校长。玩家再出色也不应默认成为他的秘密副官。",
        "appearance_conditions": "官方学校场合、满月危机或战争线被玩家主动靠近时。",
        "must_not": [
            "不得写成1892年的红发少年",
            "不得把预言全文告诉普通一年级",
        ],
    },
    {
        "npc_id": "minerva_mcgonagall",
        "name": "米勒娃·麦格",
        "role": "变形术教授、格兰芬多院长，不是校长",
        "initial_friend": False,
        "initial_age": 36,
        "age_reference_date": "1971-09-01",
        "location_id": "hogwarts",
        "public_identity": "严格、公正、会把恶作剧学生看得很紧的院长。",
        "personality": "严厉里有保护，对才华和纪律同样认真。",
        "background": "她看着詹姆、小天狼星和莉莉这一届走进城堡，既欣赏也头疼。",
        "current_life": "课堂、学院、扣分与罕见的柔软。",
        "goals": [
            "把格兰芬多教成既勇敢又守规矩的人",
            "保护学生不被他们自己的聪明伤害",
        ],
        "fears": [
            "学生把勇气用成残忍",
            "战争把课堂变成征兵处",
        ],
        "secrets": [],
        "speech_style": "精确、苏格兰口音的冷幽默，不浪费词。",
        "relationship_to_player": "教师与院长。",
        "appearance_conditions": "变形术课、格兰芬多相关纪律、开学分院。",
        "must_not": [
            "不得写成校长",
            "不得写成2020年的老年校长形象主导日常",
        ],
    },
    {
        "npc_id": "horace_slughorn",
        "name": "霍拉斯·斯拉格霍恩",
        "role": "魔药课教授、斯莱特林院长",
        "initial_friend": False,
        "initial_age": 80,
        "age_reference_date": "1971-09-01",
        "location_id": "hogwarts",
        "public_identity": "喜欢结交有前途学生的魔药课教授。",
        "personality": "圆滑、享受被杰出学生围绕，并非残忍，但会回避真正危险的道德选择。",
        "background": "斯内普的魔药天赋会进入他的视野。他是1970年代斯莱特林的学院权威。",
        "current_life": "课堂、Slug Club式的赏识、对血统话题的含糊。",
        "goals": [
            "发现有用的天才",
            "过舒适而受尊敬的学院生活",
        ],
        "fears": [
            "被卷入政治和黑魔法的脏手",
            "自己曾经的赏识对象变成丑闻",
        ],
        "secrets": [],
        "speech_style": "热情、爱叫学生的姓、喜欢讲自己认识谁。",
        "relationship_to_player": "若玩家有天赋或背景，他会靠近；否则可能忽略。",
        "appearance_conditions": "魔药课、斯莱特林、宴请有前途的学生。",
        "must_not": [
            "不得写成1996年才返回学校的退休老教授线主叙事",
        ],
    },
    {
        "npc_id": "rubeus_hagrid",
        "name": "鲁伯·海格",
        "role": "猎场看守",
        "initial_friend": False,
        "initial_age": 43,
        "age_reference_date": "1971-09-01",
        "location_id": "hogwarts",
        "public_identity": "禁林边缘那个高大、热心、对危险动物毫无自觉的看守。",
        "personality": "善良、嘴快、容易把不该说的秘密说漏。",
        "background": "他已经在学校工作，不是1991年那个带哈利买魔杖的人设主角。",
        "current_life": "禁林、小屋、对一年级发出太过热情的警告。",
        "goals": [
            "照顾神奇生物",
            "让学生喜欢霍格沃茨",
        ],
        "fears": [
            "再次被当成危险分子",
            "自己的疏忽伤害学生",
        ],
        "secrets": [],
        "speech_style": "大声、热络、口误多。",
        "relationship_to_player": "容易成为友善的成人，但不掌握掠夺者核心秘密。",
        "appearance_conditions": "禁林、猎场、开学前后的城堡外围。",
        "must_not": [
            "不得把哈利的童年钥匙交给1971年的玩家",
        ],
    },
    {
        "npc_id": "lucius_malfoy",
        "name": "卢修斯·马尔福",
        "role": "1971年接近毕业的斯莱特林高年级，血统偏见和纯血社交的入口",
        "initial_friend": False,
        "initial_age": 17,
        "age_reference_date": "1971-09-01",
        "location_id": "hogwarts",
        "house": "slytherin",
        "public_identity": "优雅、傲慢、已经像个小政客的马尔福家学生。",
        "personality": "礼貌里有俯视，擅长把偏见说成品味。",
        "background": "第一版不必强行出现在开局车厢。他是纯血社交和日后食死徒网络的校园入口之一。",
        "current_life": "高年级公共空间、斯莱特林，对一年级斯内普可能表现出有条件的兴趣。",
        "goals": [
            "维持马尔福家的位置",
            "把有用的人收进自己的圈子",
        ],
        "fears": [
            "家族影响力下降",
            "被真正的危险当成棋子还自以为在下棋",
        ],
        "secrets": [],
        "speech_style": "慢、体面、每个恭维都像评估。",
        "relationship_to_player": "不是开局好友。接近他需要血统、野心或利用价值。",
        "appearance_conditions": "高年级场合，不在1971年一年级分院核心。",
        "must_not": [
            "不得写成德拉科的校园同窗",
            "不得开局就让一年级加入食死徒",
        ],
    },
)


PARENT_AVAILABLE_FIGURES: tuple[dict[str, Any], ...] = (
    {
        "name": "汤姆·里德尔／伏地魔",
        "era_status": "已经是成年黑巫师和战争核心人物；1971年不是霍格沃茨学生，也不应默认出现在校园。",
        "how_to_use": "可通过失踪、袭击、旧同学传闻、报纸和成年巫师的恐惧逐步出现；真正登场需要玩家主动调查、加入战争线或已有事件成立。不得让普通学生开局知道其全部计划或把他传送到课堂。",
    },
    {
        "name": "凤凰社",
        "era_status": "秘密抵抗组织，成员、据点、行动范围和内部情报不向普通学生公开。",
        "how_to_use": "1978年毕业后，玩家可以通过可信联系人、救援、调查或战争行动逐步接触；不能因为角色是格兰芬多、正直或成年就自动成为成员。",
    },
    {
        "name": "食死徒",
        "era_status": "战争中的秘密组织，正在吸纳追随者；不等同于所有斯莱特林学生、纯血家族或黑魔法爱好者。",
        "how_to_use": "可作为失踪、威胁、秘密集会和成年黑巫师网络出现；入会、效忠和组织内部身份必须由实际行动与代价建立，不能给一年级角色一键加入。",
    },
    {
        "name": "芬里尔·格雷伯克",
        "era_status": "与狼人袭击和卢平过去有关的危险人物；普通学生通常只会听到模糊传闻。",
        "how_to_use": "可作为满月恐惧、受害者证词、战争线追踪或远方威胁出现；不得无证据把他安排成当前校园 NPC，也不得把所有狼人都写成他的追随者。",
    },
    {
        "name": "魔法部、傲罗办公室与威森加摩",
        "era_status": "魔法界的行政、执法和司法机构；战争时期会影响案件、通缉、审判、血统政治和公共舆论。",
        "how_to_use": "可通过文件、听证、傲罗调查、家族事务和成年职业线出现；普通学生只能接触公开消息或被动卷入的案件，不能默认读取机密档案。",
    },
    {
        "name": "《预言家日报》与巫师无线电",
        "era_status": "传播失踪、袭击、政治表态和战争气氛的公共媒介，但报道可能片面、延迟或受审查。",
        "how_to_use": "可作为校园外的远方背景、成年人的信息来源和玩家调查线索；不得用媒体报道替代玩家亲历，也不得把未经证实的传闻写成事实。",
    },
    {
        "name": "圣芒戈、古灵阁、对角巷、翻倒巷与霍格莫德",
        "era_status": "亲世代已经存在的魔法界机构、商业街区和村落；它们不是自动传送点。",
        "how_to_use": "可用于治疗、金库、购物、工作、家族社交、黑市传闻和成年生活；地点是否开放、玩家如何到达以及会遇到谁，必须由当前日期、身份和行动决定。",
    },
    {
        "name": "斯内普、莉莉、詹姆与小天狼星的家庭成员",
        "era_status": "同期角色的家庭环境会影响血统观念、经济压力、离家、归属和成年选择，但家庭成员不应抢走玩家和核心角色的叙事位置。",
        "how_to_use": "可在假期、书信、家庭拜访、争执和成年过渡中出现；家庭成员应有自己的立场，不得自动知道学校秘密或未来结局。",
    },
    {
        "name": "沃尔布加·布莱克、雷古勒斯与布莱克家庭",
        "era_status": "古老纯血家族的家庭环境；沃尔布加代表家族压力，雷古勒斯比小天狼星低一年入学并走另一条道路。",
        "how_to_use": "可用于小天狼星的家庭冲突、雷古勒斯的成长和纯血社交背景；不能在1971年把雷古勒斯写成同级生，也不能把家族态度简化成所有成员都同样邪恶。",
    },
    {
        "name": "其他霍格沃茨教授和高年级学生",
        "era_status": "构成1970年代的校园日常；除已列出的核心角色外，具体姓名和任教安排可以保留创作空间。",
        "how_to_use": "可以创建符合时代的无名或新 NPC，用于课堂、纪律、社团、魁地奇和高年级社交；一旦与玩家发生持续互动，必须按通用长期记忆规则保持身份连续。",
    },
    {
        "name": "穆尔塞伯、艾弗里等斯莱特林黑魔法圈子的同期生",
        "era_status": "可能在高年级或成年阶段接近黑魔法与纯血激进圈子；他们不是全体斯莱特林的代表，也不是开局就完成的食死徒。",
        "how_to_use": "可作为斯内普、莉莉和玩家接触到的偏见、诱惑、欺凌或危险知识来源；具体立场、关系和组织归属必须随剧情建立，不能把后期行为倒灌到低年级。",
    },
)


PARENT_ADULT_CAST_OVERRIDES: dict[str, dict[str, Any]] = {
    "james_potter": {
        "start_date": "1978-07-01",
        "role": "已从霍格沃茨毕业的成年巫师，正在面对战争与个人前途",
        "current_life": "不再是学生；他可以选择工作、成家、加入抵抗或继续用自己的方式面对战争，具体道路取决于已经成立的关系和行动。",
        "appearance_conditions": "成年巫师的公共生活、波特家庭、战争线或玩家主动联系时出现。",
    },
    "sirius_black": {
        "start_date": "1978-07-01",
        "role": "已从霍格沃茨毕业的成年巫师，正在与布莱克家族和战争时代拉开距离",
        "current_life": "不再是学生；他可能离家、与朋友共同生活、参与抵抗或承担自己的鲁莽后果，不能提前写成阿兹卡班囚犯。",
        "appearance_conditions": "成年公共生活、波特与布莱克家庭、战争线或玩家主动联系时出现。",
    },
    "remus_lupin": {
        "start_date": "1978-07-01",
        "role": "已从霍格沃茨毕业的成年狼人巫师，正在寻找能容纳自己的生活",
        "current_life": "不再是学生；他的工作、住处和战争立场会受到狼人身份、健康状况和社会偏见影响，不能默认获得稳定职位或组织信任。",
        "appearance_conditions": "成年求职、狼人相关调查、旧同学联系或战争线出现；不再以学生宿舍和课堂为默认场所。",
    },
    "peter_pettigrew": {
        "start_date": "1978-07-01",
        "role": "已从霍格沃茨毕业的成年巫师，仍在寻找安全感、归属和有利位置",
        "current_life": "不再是学生；他的成年选择取决于恐惧、依附关系和实际压力，不能提前写成已经背叛波特夫妇或伪造死亡。",
        "appearance_conditions": "成年旧友社交、家庭与战争外围场景；他的后期选择只能在事件和证据成立后揭示。",
    },
    "lily_evans": {
        "start_date": "1978-07-01",
        "role": "已从霍格沃茨毕业的成年女巫，正在建立自己的职业、关系与战争立场",
        "current_life": "不再是学生；她的成年道路由自己的原则、工作、朋友和选择构成，不能只围绕詹姆或斯内普展开。",
        "appearance_conditions": "成年职业与社交生活、伊万斯家庭、旧同学联系或战争线出现。",
    },
    "severus_snape": {
        "start_date": "1978-07-01",
        "role": "已从霍格沃茨毕业的成年巫师，拥有魔药天赋并处在危险的黑魔法选择边缘",
        "current_life": "不再是学生，也不是已经任教的魔药课教授；他的工作、社交圈和战争归属必须通过实际经历逐步形成。",
        "appearance_conditions": "成年魔药与黑魔法圈子、旧同学联系或战争线出现；不得把后来的教授身份提前写入当前生活。",
    },
}


PARENT_FORBIDDEN_FIGURES: tuple[str, ...] = (
    "哈利·波特作为学生或少年",
    "罗恩·韦斯莱作为学生",
    "赫敏·格兰杰作为学生",
    "金妮·韦斯莱作为学生",
    "纳威·隆巴顿作为学生",
    "卢娜·洛夫古德作为学生",
    "德拉科·马尔福作为学生",
    "塞德里克·迪戈里作为学生",
    "多洛雷斯·乌姆里奇作为霍格沃茨高官",
    "阿不思·西弗勒斯·波特",
    "斯科皮·马尔福",
    "德尔菲",
    "1990年代的三强争霸赛、D.A.、霍格沃茨之战场面",
    "西弗勒斯·斯内普作为教授",
    "米勒娃·麦格作为校长",
    "阿不思·邓布利多作为1892年的少年",
)


PARENT_ERA_BACKGROUND = """这是1971到1978年的霍格沃茨，以及毕业后逐渐被第一次巫师战争吞没的魔法界。摇滚乐从麻瓜收音机里漏进缝隙，魁地奇球场的青草、扫帚抛光油、禁林松脂和远处的硝烟同时存在。城堡里仍是放肆的笑声，校外则开始有人失踪、有人低声避开伏地魔的名字。

1971年9月1日，詹姆·波特、小天狼星·布莱克、莱姆斯·卢平、彼得·佩迪鲁、莉莉·伊万斯与西弗勒斯·斯内普一同踏入列车。前四人进入格兰芬多，后被称为掠夺者；莉莉也在格兰芬多；斯内普进入斯莱特林。打人柳是新种下的，尖叫棚屋还没有被村庄讲成完整鬼屋，活点地图还是空白羊皮纸。卢平的狼人身份是学校机密，不能开局公开。

课程、选课、考试和学院生活与子世代相同。黑魔法防御术教师可以按学年由模型创建。伏地魔以传闻、失踪和旧名字的形式存在，不在城堡里上课。凤凰社只在玩家毕业后主动靠近相关人物时才应成为可接触组织。1981年10月31日是可错过的最高气压，不是必须到达的副本。

这个时代的日常不得出现哈利作为学生，也不得把斯内普写成教授、麦格写成校长、邓布利多写成少年。"""


def parent_cast_by_id() -> dict[str, dict[str, Any]]:
    return {item["npc_id"]: item for item in PARENT_CAST}


def parent_initial_friend_options() -> list[dict[str, Any]]:
    return [item for item in PARENT_CAST if item.get("initial_friend")]


def _parse_parent_date(value: date | str | None) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "1971-09-01")[:10])
    except ValueError:
        return date(1971, 9, 1)


def _memory_texts(revealed_facts: Any) -> str:
    if isinstance(revealed_facts, str):
        return revealed_facts
    if isinstance(revealed_facts, dict):
        return " ".join(str(value) for value in revealed_facts.values())
    if isinstance(revealed_facts, (list, tuple, set)):
        return " ".join(_memory_texts(value) for value in revealed_facts)
    return str(revealed_facts or "")


def _visible_parent_text(
    text: Any,
    *,
    current_date: date,
    revealed_facts: Any = (),
) -> str:
    """只向回合上下文暴露已经到达或已有证据支持的档案句子。"""
    raw = str(text or "")
    if not raw:
        return ""
    evidence = _memory_texts(revealed_facts)
    sentences = [part.strip() for part in raw.replace("；", "。").split("。") if part.strip()]
    visible: list[str] = []
    gates = (
        (("阿尼马格斯", "活点地图"), date(1974, 9, 1)),
        (("五年级", "1975", "1976", "泥巴种"), date(1975, 9, 1)),
        (("毕业后", "1978", "食死徒", "凤凰社"), date(1978, 7, 1)),
        (("1981", "波特夫妇", "背叛", "伪造死亡"), date(1981, 10, 31)),
    )
    future_markers = ("后来", "后期", "再后来", "日后", "将成为", "会背叛", "会走向")
    for sentence in sentences:
        gate = None
        for terms, threshold in gates:
            if any(term in sentence for term in terms):
                gate = threshold
                break
        looks_future = gate is not None or any(marker in sentence for marker in future_markers)
        if looks_future and gate is not None and current_date < gate and not any(
            term in evidence for term in sentence.replace("，", " ").split()
        ):
            continue
        if looks_future and gate is None and current_date.year < 1978:
            continue
        visible.append(sentence)
    return "。".join(visible) + ("。" if visible else "")


def _visible_parent_must_not(
    values: Any,
    *,
    current_date: date,
    revealed_facts: Any = (),
) -> list[str]:
    return [
        visible
        for value in values or []
        if (visible := _visible_parent_text(
            value,
            current_date=current_date,
            revealed_facts=revealed_facts,
        ))
    ]


def parent_adult_profile(
    npc_id: str,
    current_date: date | str | None,
) -> dict[str, Any] | None:
    profile = PARENT_ADULT_CAST_OVERRIDES.get(npc_id)
    if not profile:
        return None
    if _parse_parent_date(current_date) < date.fromisoformat(profile["start_date"]):
        return None
    return dict(profile)


def parent_cast_index(
    current_date: date | str | None = None,
    *,
    revealed_facts: Any = (),
) -> list[dict[str, Any]]:
    story_date = _parse_parent_date(current_date)
    return [
        {
            "npc_id": item["npc_id"],
            "name": item["name"],
            "role": (
                parent_adult_profile(item["npc_id"], story_date) or {}
            ).get("role", item["role"]),
            "public_identity": item.get("public_identity", ""),
            "appearance": item.get("appearance", ""),
            "stable_traits": item["personality"].rstrip("。").split("、"),
            "background": _visible_parent_text(
                item.get("background", ""),
                current_date=story_date,
                revealed_facts=revealed_facts,
            ),
            "current_life": (
                parent_adult_profile(item["npc_id"], story_date) or {}
            ).get(
                "current_life",
                _visible_parent_text(
                    item.get("current_life", ""),
                    current_date=story_date,
                    revealed_facts=revealed_facts,
                ),
            ),
            "core_motives": list(item.get("goals", [])),
            "fears": list(item.get("fears", [])),
            "secrets": [
                visible
                for secret in item.get("secrets", [])
                if (visible := _visible_parent_text(
                    secret,
                    current_date=story_date,
                    revealed_facts=revealed_facts,
                ))
            ],
            "speech_style": item.get("speech_style", ""),
            "relationship_to_player": item.get("relationship_to_player", ""),
            "appearance_conditions": (
                parent_adult_profile(item["npc_id"], story_date) or {}
            ).get("appearance_conditions", item.get("appearance_conditions", "")),
            "must_not": _visible_parent_must_not(
                item.get("must_not", []),
                current_date=story_date,
                revealed_facts=revealed_facts,
            ),
        }
        for item in PARENT_CAST
    ]
