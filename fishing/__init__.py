import os
import random

import hoshino
from hoshino import Service
from ..GroupFreqLimiter import check_reload_group, set_reload_group
from hoshino.util import FreqLimiter
from hoshino.config import SUPERUSERS
from ..config import BLACKUSERS
from .. import money, config
from .._R import get, userPath
from .util import shift_time_style, update_serif
from ..utils import chain_reply, saveData, loadData
from ..config import SEND_FORWARD, FISH_LIST
from .get_fish import fishing, buy_bait, free_fish, sell_fish, change_fishrod, compound_bottle, getUserInfo, \
    increase_value, decrease_value, buy_bottle
from .serif import cool_time_serif
from .get_bottle import get_bottle_amount, check_bottle, format_message, check_permission, check_content, set_bottle, \
    delete_bottle, add_to_blacklist, remove_from_blacklist, show_blacklist, format_msg_no_forward, add_comment, \
    delete_comment, admin_check_bottle
from .._interact import interact, ActSession
from .evnet_functions import random_event
from hoshino.typing import CQEvent as Event
from ..utilize import get_double_mean_money
import os
import asyncio
from datetime import datetime, timedelta
from ..chaogu.stock_utils import get_user_portfolio, check_daily_gamble_limit
default_info = {
    'fish': {'🐟': 0, '🦐': 0, '🦀': 0, '🐡': 0, '🐠': 0, '🔮': 0, '✉': 0, '🍙': 0},
    'statis': {'free': 0, 'sell': 0, 'total_fish': 0, 'frags': 0},
    'rod': {'current': 0, 'total_rod': [0]}
}


fish_price = config.FISH_PRICE

'''if not config.DEBUG_MODE:
    SUPERUSERS = [SUPERUSERS[0]]'''

event_list = list(random_event.keys())

sv = Service("冰祈与鱼", enable_on_default=True)

help_1 = '''
转账功能：
转账 QQ号 金币数量
示例：转账 123456 100
低保功能（仅限金币＜5000且没有私藏鱼饵和鱼时）：
直接发送 领低保
钓鱼功能：
1.#钓鱼帮助
2.#买鱼饵 数量（例：#买鱼饵 5）
3.钓鱼
4.十连钓鱼（95折优惠）、
5.百连钓鱼（9折优惠）
6.千连钓鱼/万连钓鱼/十万连钓鱼（仅用作调试）
7..#出售 鱼emoji 数量（例：#出售 🐟 2）
8.出售小鱼、一键出售
9.#放生 鱼emoji 数量（例：#放生 🐟 2）
10.#背包
----------
鱼emoji如：🐟，🦐，🦀，🐡，🐠，🦈
数量可选，不填则默认为1
出售可获得金币，放生可获得等价值的水心碎片
每75个水心碎片会自动合成为水之心
'''

help_2 = '''
漂流瓶功能：
1.#合成漂流瓶+数量（例：#合成漂流瓶 2）
2.#买漂流瓶+数量（例：#买漂流瓶 2）
3.#扔漂流瓶+内容（例：#扔漂流瓶 你好）
4.#捡漂流瓶
5.#漂流瓶数量
6.#回复 漂流瓶ID 内容（例：#回复114514 你好）
7.#删除回复
----------
数量可选，不填则默认为1
合成漂流瓶需要2个水之心
买漂流瓶需要225枚金币
捡漂流瓶需要一个水之心
回复他人的漂流瓶需要20金币
'''

rod_help = '''
当前鱼竿：
1.普通鱼竿
2.永不空军钓竿(不会空军)
3.海之眷顾钓竿(稀有鱼概率UP)
4.时运钓竿(概率双倍鱼)
发送"#换钓竿+ID"更换钓竿
'''.strip()

event_flag = {}

no = get('emotion/no.png').cqcode
ok = get('emotion/ok.png').cqcode
fish_list = FISH_LIST + ['✉', '🍙', '水之心']
admin_path = os.path.join(userPath, 'fishing/db/admin.json')
freq = FreqLimiter(config.COOL_TIME)
throw_freq = FreqLimiter(config.THROW_COOL_TIME)
get_freq = FreqLimiter(config.SALVAGE_COOL_TIME)
comm_freq = FreqLimiter(config.COMMENT_COOL_TIME)
bait_freq = FreqLimiter(10)


@sv.on_fullmatch('#钓鱼帮助', '钓鱼帮助', '/钓鱼帮助')
async def fishing_help(bot, ev):
    """
        拉取钓鱼帮助
    """
    chain = []
    await chain_reply(bot, ev, chain, help_1)
    await chain_reply(bot, ev, chain, help_2)
    if check_reload_group(ev.group_id, _type='boolean'):
        return
    set_reload_group(ev.group_id, _time=120)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)




@sv.on_fullmatch('🎣', '钓鱼')
async def go_fishing(bot, ev):
    uid = ev.user_id
    if ev.user_id in BLACKUSERS:
        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
        return
    user_info = getUserInfo(uid)

    # 冷却检测
    if not freq.check(uid) and not config.DEBUG_MODE:
        await bot.send(ev, random.choice(cool_time_serif) + f'({int(freq.left_time(uid))}s)')
        return

    # 检查鱼饵数量
    if user_info['fish'].get('🍙', 0) < 10:
        await bot.send(ev, '需要10个鱼饵喔，要买点鱼饵嘛？(或发送#钓鱼帮助)')
        return

    # 开始钓鱼
    freq.start_cd(uid)
    await bot.send(ev, '你开始了钓鱼...')

    # 消耗鱼饵
    decrease_value(uid, 'fish', '🍙', 10, user_info)

    # 执行钓鱼逻辑，传递 user_info
    resp = fishing(uid, user_info=user_info)

    # 处理钓鱼返回结果
    if resp['code'] == 1:
        msg = resp['msg']
        await bot.send(ev, msg, at_sender=True)
    elif resp['code'] == 2:  # 漂流瓶模式
        increase_value(uid, 'fish', '🔮', 1, user_info)
        await bot.send(ev, '你发现鱼竿有着异于平常的感觉，竟然钓到了一颗水之心🔮~', at_sender=True)
    elif resp['code'] == 3:  # 随机事件模式
        choose_ev = random.choice(event_list)
        hoshino.logger.info(choose_ev) if config.DEBUG_MODE else None
        session = ActSession.from_event(
            choose_ev, ev, max_user=1, usernum_limit=True)
        try:
            interact.add_session(session)
        except ValueError:
            hoshino.logger.error('两个人的随机事件冲突了。')
            increase_value(uid, 'fish', '✉', 1)
            await bot.send(ev, '你的鱼钩碰到了一个空漂流瓶！可以使用"#扔漂流瓶+内容"使用它哦！')
            return
        session.state['started'] = True
        event_flag[str(uid)] = choose_ev
        msg = random_event[choose_ev]['msg'] + \
            '\n'.join(random_event[choose_ev]['choice'])
        msg += '\n(发送选项开头数字ID完成选择~)'
        await bot.send(ev, msg, at_sender=True)

    # 加锁保存用户数据
    lock = asyncio.Lock()
    async with lock:
        dbPath = os.path.join(userPath, 'fishing/db')
        user_info_path = os.path.join(dbPath, 'user_info.json')
        total_info = loadData(user_info_path)
        total_info[uid] = user_info
        saveData(total_info, user_info_path)

##############################
def cal_all_fish_value(result):
    """
    计算用户所有鱼的价值
    """
    total_value = 0
    for fish, count in result.items():
        if fish in fish_price.keys():
            total_value += count * fish_price[fish]
    return total_value

import os
import asyncio
import time
#################################################################

# 设置共用冷却时间
COMMON_CD = config.fishcd

# 冷却时间管理字典
cooldown_data = {}

def start_cd(uid, command=None):
    """
    启动冷却CD, 共用相同的冷却时间
    """
    cooldown_data[uid] = time.time() + COMMON_CD  # 所有命令使用相同的冷却时间

def left_time(uid, command=None):
    """
    获取剩余冷却时间，根据命令名称判断冷却剩余时间
    """
    cooldown_time = cooldown_data.get(uid, 0) - time.time()
    return max(0, cooldown_time)
###########################################################################
async def send_red_packet(bot, group_id, total_gold, num_packets):
    """
        向群聊发送拼手气红包。
    """
    session_key = '系统红包'  # 标识当前会话的唯一名称

    # 使用模拟事件对象传入到 find_session 中
    dummy_event = Event()
    dummy_event.group_id = group_id
    dummy_event.user_id = 0  # 系统发起，user_id 设置为 0

    # 检查是否已有未领取完的红包会话
    session = interact.find_session(dummy_event, name=session_key)
    
    if session:  # 如果存在未领取完的红包，清理旧会话
        remain_money = sum(session.state['hb_list'])  # 获取剩下的金币
        if remain_money > 0:
            if session.state.get('owner'):  # 如果有发起人，则返还金币
                money.increase_user_money(session.state['owner'], 'gold', remain_money)
        session.close()  # 关闭旧会话

    # 验证红包参数
    if total_gold <= num_packets:
        await bot.send_group_msg(group_id=group_id, message="红包金额或数量设置有误，无法发送红包。")
        return

    # 创建拼手气红包
    xthongbao_list = get_double_mean_money(total_gold, num_packets)
    session = ActSession(
        name=session_key,
        group_id=group_id,
        user_id=0,  # 系统生成，不指向具体用户
        max_user=num_packets,
        expire_time=600,
        usernum_limit=True  # 限制最大用户数
    )
    interact.add_session(session)
    session.state['hb_list'] = xthongbao_list

    # 系统发起红包配置
    session.state['owner'] = None  # 无发起人
    session.state['users'] = []

    # 提示群聊红包发送成功
    await bot.send_group_msg(group_id=group_id, message=f'蠢萝莉破防了，落荒而逃！\n逃跑途中左脚踩右脚，绊倒的同时爆出一个{total_gold}金币红包，共{num_packets}份！\n使用“领红包”以获取红包\n“呜...好痛...”（迅速开溜）')
    
@sv.on_prefix('领红包')
async def qiang_hongbao(bot, ev):
    if not interact.find_session(ev, name='系统红包'):
        return
    session = interact.find_session(ev, name='系统红包')
    if session.is_expire():
        remain_money = sum(session.state['hb_list'])
        money.increase_user_money(session.state['owner'], 'gold', remain_money)
        await session.send(ev, f'红包过期，已返还剩余的{remain_money}枚金币')
        session.close()
        return
    if ev.user_id in session.state['users']:
        await bot.send(ev, '你已经抢过红包了！')
        return
    if session.state['hb_list']:
        user_gain = session.state['hb_list'].pop()
        session.state['users'].append(ev.user_id)
        money.increase_user_money(ev.user_id, 'gold', user_gain)
        await bot.send(ev, f'你抢到了{user_gain}枚金币~', at_sender=True)
    if not session.state['hb_list']:
        session.close()
        await bot.send(ev, '红包领完了~')
        return
###################################################################################################




# 初始化萝莉血量
Loli_MAX_HP = config.maxhp
Loli_hp = Loli_MAX_HP

# 血量百分比触发点及其对应的多条受击提示
hp_thresholds = {
    70: ["“（若无其事地整理裙摆）杂鱼大叔手抖成这样？（歪头）是怕打伤我要赔三年零花钱嘛？”", 
         "“（踮脚戳脸）只是稍微让让你而已！下次可不会放水了喂！（突然跳开）”", 
         "“（轻微掀起裙摆）就这？连胖次的外层防御都没攻破呢~乖乖继续给我爆金币吧！（嘲讽脸）”", 
         "“杂鱼，好逊的攻击，人家一点感觉都没有呢...”", 
         "“哼，咱才不会输呢！”"],
    33: ["“呜哇！（强装镇定）这点伤害，洒洒水啦~”",
         "“稍微有点厉害呀……不过和咱比，还是差远了哦~”",
         "“（掏出玩具手铐晃荡）一直骚扰人家，是想干嘛呢？现在收手，还来得及哦~”",
         "“呀！(抱头蹲防)好害怕哦——（忽然起身）好啦，骗你的啦~稍微卖个萌就心软啦？蠢呼呼的，注定是要被咱爆金币的哦~”",
         "“（偷偷揉屁股）刚才那招算你偷袭！（摸出皱巴巴契约书）现在认输可以八折付款...”"],
    10: ["“（跺鞋尖溅起灰尘）呜...只允许打到这个程度哦！（背手藏起颤抖）要是跪下来道歉...也不是不能考虑放过你...（用鞋底蹭地）”",
         "“（抽鼻子装作打哈欠）才没有认输呢！（捏着凌乱的裙摆）不过是一群杂鱼群友...罢了...（声音缩进衣领）”",
         "“（蜷成团子还在嘴硬）绝、绝对要把你画进工口漫画！变成参加Party被透晕的蠢萝莉，要是现在认输的话...可以考虑改结局...（睫毛垂下来）”",
         "“（生气地跺脚）再碰一下就把你照片P成萝莉控变态！（指甲抠掌心）现在说「姐姐大人对不起」...就勉强只发朋友圈三天哦...（转身踢石子）”",
         "“（眼泪汪汪）唔...才没有害怕呢！我真的会生气的哦！（撇过脑袋擦眼泪）如果现在认输的话，人家说不定会...原谅你...（逐渐小声）”"]
}

has_triggered = []  # 记录已触发的提醒

# 拼手气红包的金币总量和数量
REWARD_TOTAL_GOLD = 50000
REWARD_NUM = 10
bosstime = config.bosstime
@sv.on_fullmatch('捉萝莉')
async def catch_Loli(bot, ev):
    """
        玩家指令：捉萝莉
        消耗饭团，对萝莉造成随机伤害。
    """
    global Loli_hp, has_triggered

    uid = ev.user_id
    if ev.user_id in BLACKUSERS:
        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
        return
    if bosstime == 0:
        await bot.send(ev, '\n鱼塘风平浪静，没有发现蠢萝莉' +no, at_sender=True)
        return
    user_info = getUserInfo(uid)
    
    # 金币检查：在消耗饭团之前，先检查金币是否足够
    user_gold = money.get_user_money(uid, 'gold')  # 获取用户金币
    if user_gold < 2000:
        await bot.send(ev, '\n穷鬼不配和我玩哦~（一脸嫌弃）', at_sender=True)
        return
    
    # 检查冷却时间
    if left_time(uid) > 0 and not config.DEBUG_MODE:
        await bot.send(ev, random.choice(cool_time_serif) + f'({int(left_time(uid))}s)')
        return

    # 启动冷却
    start_cd(uid)
    
    # 消耗饭团检查
    if user_info['fish']['🍙'] < config.loliprice:
        await bot.send(ev, f'\n捉萝莉需要消耗{config.loliprice}个饭团，您的饭团不足！' +no, at_sender=True)
        return
    
    # 消耗饭团
    decrease_value(uid, 'fish', '🍙', config.loliprice, user_info)

    lock = asyncio.Lock()
    async with lock:
        dbPath = os.path.join(userPath, 'fishing/db')
        user_info_path = os.path.join(dbPath, 'user_info.json')
        total_info = loadData(user_info_path)
        total_info[uid] = user_info  # 更新完整的 `user_info`
        saveData(total_info, user_info_path)
    
    # 几率造成miss
    if random.random() < config.miss:  # 生成介于0和1之间的随机数
        user_gold = money.get_user_money(uid, 'gold')
        damage = random.randint(config.lowdamage, config.highdamage)
        if random.random() < config.bbjb:
            if user_gold >= damage:  # 确保玩家金币足够被扣减
                money.reduce_user_money(uid, 'gold', damage)  # 损失金币
                await bot.send(ev, f'\n你的攻击打出了miss，蠢萝莉进行了反击！你损失了{damage}金币！', at_sender=True)
                return
            else:
                money.reduce_user_money(uid, 'gold', user_gold)
                await bot.send(ev, f'\n你的攻击打出了miss，蠢萝莉进行了反击！不过你已家徒四壁，只损失了{user_gold}金币！', at_sender=True)
                return
        else:
            await bot.send(ev, f'\n你试图捉蠢萝莉，但她灵敏地躲开了你的攻击！本次造成0点伤害！', at_sender=True)
            return
    
    
# 概率爆出金币
    if random.random() < config.bjb:
        if random.random() < config.xinyun_bjb:
            damage = random.randint(config.lowdamage * 10, config.highdamage * 10)
            Loli_hp -= damage
            money.increase_user_money(uid, 'gold', damage * 10)
            await bot.send(ev, f'\n恭喜你！捉萝莉时触发了幸运暴击，爆出了 {damage * 10} 金币！', at_sender=True)
        else:
            damage = random.randint(config.lowdamage, config.highdamage)
            Loli_hp -= damage
            money.increase_user_money(uid, 'gold', damage)
            await bot.send(ev, f'\n恭喜你！捉萝莉时触发了暴击，造成了{damage}点伤害！同时爆出了 {damage} 金币！', at_sender=True)
    else:
        damage = random.randint(config.lowdamage, config.highdamage)
        Loli_hp -= damage
        await bot.send(ev, f'\n你对蠢萝莉造成了{damage}点伤害！蠢萝莉剩余{int((Loli_hp / Loli_MAX_HP) * 100)}%血量。', at_sender=True)

    # 检查是否需要发送受击提示
    for threshold, messages in hp_thresholds.items():
        if Loli_hp / Loli_MAX_HP * 100 <= threshold and threshold not in has_triggered:
            has_triggered.append(threshold)
            selected_message = random.choice(messages)  # 随机选择一条提示信息
            await bot.send(ev, f'{selected_message}')

    # 如果蠢萝莉血量小于等于0，触发战败逻辑
    if Loli_hp <= 0:
        Loli_hp = Loli_MAX_HP  # 重置蠢萝莉血量
        has_triggered = []  # 重置触发记录
        money.increase_user_money(uid, 'gold', config.jishagold)
        await bot.send(ev, f'\n你给予了蠢萝莉最后一击！获得了 {config.jishagold} 金币的奖励。', at_sender=True)
        # 向群聊发送拼手气红包
        group_id = ev.group_id
        await send_red_packet(bot, group_id, REWARD_TOTAL_GOLD, REWARD_NUM)

###########################################################################
async def multi_fishing(bot, ev, times, cost, star_cost, command_name):
    """
    多连钓鱼 - 消耗指定数量的饭团并进行指定次数的钓鱼
     bot: bot 对象
     ev: event 对象
     times: 钓鱼次数
     cost: 消耗的饭团数量
     command_name: 命令名称，用于输出信息
    """
    uid = ev.user_id
    user_starstone = money.get_user_money(uid, 'starstone')
    if user_starstone < star_cost:
        await bot.send(ev, '\n呜，一整天的就知道钓鱼......哼，不理你了！' +no, at_sender=True)
        return
    if ev.user_id in BLACKUSERS:
        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' + no, at_sender=True)
        return
    if bosstime == 1:
        await bot.send(ev, '\n操作失败，鱼塘被蠢萝莉占领了，请使用“捉萝莉”将蠢萝莉打败吧！' + no, at_sender=True)
        return
    
    user_info = getUserInfo(uid)

    # 检查钓鱼冷却时间
    if left_time(uid) > 0 and uid not in SUPERUSERS:
        await bot.send(ev, random.choice(cool_time_serif) + f'({int(left_time(uid))}s)')
        return

    # 检查鱼饵数量
    if user_info['fish'].get('🍙', 0) < cost:
        await bot.send(ev, f'{command_name}需要 {cost} 个饭团，您的饭团不足！')
        return
    money.reduce_user_money(uid, 'starstone', star_cost)
    # 启动钓鱼冷却
    start_cd(uid)

    # 消耗饭团
    decrease_value(uid, 'fish', '🍙', cost, user_info)

    #await bot.send(ev, f'你开始了{command_name}！')

    # 汇总结果字典
    result_summary = {}

    # 执行钓鱼
    for _ in range(times):
        resp = fishing(uid, skip_random_events=True, user_info=user_info)
        if resp['code'] == 1:
            msg = resp['msg']
            # 统计鱼类结果
            fish_type = ''.join(filter(lambda x: x in "🐟🦈🦀🦐🐠🐡🌟", msg))
            if fish_type:
                result_summary[fish_type] = result_summary.get(fish_type, 0) + 1

    value = cal_all_fish_value(result_summary)
    actual_cost = cost * 3.0 #修正cost计算
    judge = {
        "loss_low": f"（叉腰跺脚气鼓鼓）哈啊——？{actual_cost}円扔进水里都能听个响，结果就这¥{value}的废纸？（突然凑近眯眼）回报率只有{int((value/actual_cost)*100)}%…噗嗤！连街边扭蛋机都比你有尊严啦！快把钱包交给本小姐封印！ヽ(`Д´)ﾉ",
        "loss_moderate": f"（翘腿晃脚尖冷笑）哇哦~花了¥{actual_cost}抽到价值¥{value}？（掰手指）亏损{int((1-value/actual_cost)*100)}%耶~（突然拍桌）你是故意用脚趾戳计算器的吗！这种垃圾就算喂给流浪猫都会被嫌弃喵～♪",
        "loss_high": f"（吐舌头做鬼脸）略略略~{int((value/actual_cost)*100)}%回报率？这根本是反向理财天才嘛！（突然掏出小本本记仇）第114514次见证人类智商盆地——（用红笔在你脸上画猪头）下次请直接给我打钱，至少我不会让你亏到内裤穿孔啦！( ´▽｀)",
        "double_up": f"（发现value>=1.5*actual_cost时甩飞计算器）什…什么！居然赚了这么多了？！（耳朵发红跺脚）绝、绝对是系统BUG吧！才不承认你有狗屎运呢！（偷偷捡回计算器）但…但是分我一半金币的话，可以考虑给你加个「临时幸运笨蛋」称号哦…（声音越来越小）",
        "normal_profit": f"（托腮斜眼瞟屏幕）哼~赚了{int((value/actual_cost-1)*100)}%就得意了？（突然用指甲刮黑板）这点蚊子腿利润连买奶茶都不够甜诶！（甩出记账本）看好了——你抽卡时浪费的{value//10}小时，换算成时薪都能买一箱泡面了喔！（戳你锁骨）下次请我喝全糖布丁的话...勉强夸你是「庶民经济学入门者」啦～（扭头哼歌）",
        "huge_loss": f"（当亏损超80%时贴脸嘲讽）诶诶~¥{value}？连成本零头都不到呢！（突然掏出放大镜对准你）让本侦探看看——（惊呼）哇！发现珍稀物种「慈善赌王」！要不要给你颁个「散财童子终身成就奖」呀？奖杯就用你哭唧唧的表情包做叭～（咔嚓拍照声）",
        "massive_profit": f"（盈利200%以上时抱头蹲防）这不科学——！（从指缝偷看数字）{int((value/actual_cost-1)*100)}%的暴利什么的…（跳起来指鼻子）绝·对·是·诈·骗！快老实交代是不是卖了肾去抽卡！（突然扔出粉笔砸黑板）现在立刻马上！把玄学抽卡口诀交出来！！（＞д＜）\n幸运币+1",
        "extreme_loss": f"（亏损99%时歪头装无辜）呐呐~用¥{actual_cost}换¥{value}？（突然捶地狂笑）这不是把钞票塞进碎纸机还自带BGM嘛！要不要借你本小姐的数学笔记？（唰啦展开全是涂鸦的笔记本）看好了哦~「抽卡前请先拨打精神病院热线」用荧光笔标重点了呢～☆",
        "mild_profit": f"（盈利250%时背对屏幕碎碎念）区区{int((value/actual_cost-1)*100)}%涨幅…（突然转身泪眼汪汪）肯、肯定把后半辈子的运气都透支了吧？！（掏出塔罗牌乱甩）看我逆转因果律——（牌面突然自燃）呜哇！连占卜都站在笨蛋那边？！这不公平！！( TДT)\n幸运币+1",
        "zero_value": f"（当value=0时用扫帚戳你）醒醒啦守财奴！（转扫帚当麦克风）恭喜解锁隐藏成就「氪金黑洞」！您刚才支付的¥{actual_cost}已成功转化为——（压低声音）宇宙暗物质、开发组年终奖以及本小姐的新皮肤！（转圈撒虚拟彩带）要放鞭炮庆祝吗？噼里啪啦嘭——！（其实是砸键盘声）",
        "extreme_profit": f"（盈利300%以上时瞳孔地震）这这这{int((value/actual_cost-1)*100)}%的收益率…（突然揪住你领子摇晃）快说！是不是绑架了程序猿的猫？！（掏出纸笔）现在立刻签这份《欧气共享契约》！否则就把你账号名叫「人傻钱多速来」挂公告栏哦！我认真的！！（契约上画满小恶魔涂鸦）\n幸运币+1"
    }

    # 汇总结果文本
    summary_message = f"\n你的{command_name}汇总结果：\n"
    if result_summary:
        summary_message += "\n".join(f"{fish}: {count} 条" for fish, count in result_summary.items())
    else:
        summary_message += "你没有钓到任何有价值的鱼..."

    summary_message += f"\n\n总价值：{value} 金币\n总花费：{actual_cost} 金币\n"

    if value / actual_cost < 1 and value / actual_cost >= 0.7:
        summary_message += judge["loss_low"]
    elif value / actual_cost < 0.7 and value / actual_cost >= 0.3:
        summary_message += judge["loss_moderate"]
    elif value / actual_cost < 0.3 and value / actual_cost >= 0.1:
        summary_message += judge["loss_high"]
    elif value / actual_cost > 0.01 and value / actual_cost < 0.1:
        summary_message += judge["huge_loss"]
    elif value / actual_cost > 1 and value / actual_cost <= 1.5:
        summary_message += judge["normal_profit"]
    elif value / actual_cost > 1.5 and value / actual_cost <= 2:
        summary_message += judge["double_up"]
    elif value / actual_cost > 2 and value / actual_cost <= 2.5:
        money.increase_user_money(uid, 'luckygold', 1)
        summary_message += judge["massive_profit"]
    elif value / actual_cost > 2.5 and value / actual_cost <= 3:
        money.increase_user_money(uid, 'luckygold', 1)
        summary_message += judge["mild_profit"]
    elif value / actual_cost > 3:
        money.increase_user_money(uid, 'luckygold', 1)
        summary_message += judge["extreme_profit"]
    elif value / actual_cost == 0.01:
        summary_message += judge["extreme_loss"]
    elif value == 0:
        summary_message += judge["zero_value"]

    # 保存用户信息
    lock = asyncio.Lock()
    async with lock:
        dbPath = os.path.join(userPath, 'fishing/db')
        user_info_path = os.path.join(dbPath, 'user_info.json')
        total_info = loadData(user_info_path)
        total_info[uid] = user_info
        saveData(total_info, user_info_path)

    # 发送最终结果
    await bot.send(ev, summary_message, at_sender=True)


# 重新定义触发函数
@sv.on_fullmatch('十连钓鱼')
async def ten_fishing(bot, ev):
    await multi_fishing(bot, ev, 10, 95, config.star_price * 10, '十连钓鱼')

@sv.on_fullmatch('百连钓鱼')
async def hundred_fishing(bot, ev):
    await multi_fishing(bot, ev, 100, 900, config.star_price * 100, '百连钓鱼')

@sv.on_fullmatch('千连钓鱼')
async def thousand_fishing(bot, ev):
    if ev.user_id not in SUPERUSERS:
        await bot.send(ev, f'非管理员账户，禁止执行开发功能！' +no, at_sender=True)
        return
    await multi_fishing(bot, ev, 1000, 1, 0, '千连钓鱼')

@sv.on_fullmatch('万连钓鱼')
async def tenthousand_fishing(bot, ev):
    if ev.user_id not in SUPERUSERS:
        await bot.send(ev, f'非管理员账户，禁止执行开发功能！' +no, at_sender=True)
        return
    await multi_fishing(bot, ev, 10000, 1, 0, '万连钓鱼')

@sv.on_fullmatch('十万连钓鱼')
async def hundredthousand_fishing(bot, ev):
    if ev.user_id not in SUPERUSERS:
        await bot.send(ev, f'非管理员账户，禁止执行开发功能！' +no, at_sender=True)
        return
    await multi_fishing(bot, ev, 100000, 1, 0, '十万连钓鱼')

####################################################################
@sv.on_prefix('#买鱼饵', '#买饭团', '#买🍙', '买鱼饵', '买🍙')
async def buy_bait_func(bot, ev):
    uid = ev.user_id
#    if ev.user_id in BLACKUSERS:
#        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
#        return
    user_info = getUserInfo(uid)
    if user_info['fish']['🍙'] > 200000000:
        await bot.send(ev, '背包太满，装不下...' + no)
        return
    message = ev.message.extract_plain_text().strip()
    if not message or not str.isdigit(message):
        num = 1
    else:
        num = int(message)
    if num>50000000:
        await bot.send(ev, '一次只能购买50000000个鱼饵喔' + no)
        return
    user_gold = money.get_user_money(uid, 'gold')
    if user_gold<num * config.BAIT_PRICE:
        await bot.send(ev, '金币不足喔...' + no)
        return
    buy_bait(uid, num)
#    if not uid % 173 and not uid % 1891433 and not uid % 6:
#        money.increase_user_money(uid, 'gold', num * config.BAIT_PRICE * 0.04)
    await bot.send(ev, f'已经成功购买{num}个鱼饵啦~(金币-{num * config.BAIT_PRICE})')
buy_bottle_cmd = [i + j + k for i in ['#', '＃']
                  for j in ['买', '购买'] for k in ['漂流瓶', '✉']]


@sv.on_prefix(buy_bottle_cmd)
async def buy_bottle_func(bot, ev):
    """
        买漂流瓶(2023.7.18新增)
    """
    uid = ev.user_id
    user_info = getUserInfo(uid)
    if user_info['fish']['✉'] > 50:
        await bot.send(ev, '背包太满，装不下...' + no)
        return
    message = ev.message.extract_plain_text().strip()
    num = 1 if not message or not str.isdigit(message) else int(message)
    if num > 10:
        await bot.send(ev, '一次只能购买10个漂流瓶喔' + no)
        return
    user_gold = money.get_user_money(uid, 'gold')
    if user_gold < num * config.BOTTLE_PRICE:
        await bot.send(ev, '金币不足喔...' + no)
        return
    buy_bottle(uid, num)
    await bot.send(ev, f'成功买下{num}个漂流瓶~(金币-{num * config.BOTTLE_PRICE})')

open_bag_command = [i + j + k for i in ['#', '＃', '']
                    for j in ['', '我的'] for k in ['背包', '仓库']] + ['#🎒', '#bag'
]

@sv.on_fullmatch(open_bag_command)
async def my_fish(bot, ev):
    """
        查看背包
    """
    uid = ev.user_id
#    if ev.user_id in BLACKUSERS:
#        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
#        return
    user_info = getUserInfo(uid)
    msg = '背包：\n'
    items = ''
    for i, j in user_info['fish'].items():
        if j == 0:
            continue
        items += f'{i}×{j}\n'
    if not items:
        items = '空空如也...'
    msg = msg + items
    await bot.send(ev, msg.strip('\n'), at_sender=True)



@sv.on_prefix('#放生', '#free', '＃放生', '＃free')
async def free_func(bot, ev):
    message = ev.message.extract_plain_text().strip()
    msg_split = message.split()
    fish = ''
    num = 0
    if len(msg_split) == 2:
        if msg_split[0] not in FISH_LIST:
            return
        if not str.isdigit(msg_split[-1]):
            return
        fish = msg_split[0]
        num = int(msg_split[-1])
    elif len(msg_split) == 1:
        if msg_split[0] not in FISH_LIST:
            return
        fish = msg_split[0]
        num = 1
    else:
        return
    uid = ev.user_id
    result = free_fish(uid, fish, num)
    await bot.send(ev, result, at_sender=True)
    

@sv.on_fullmatch('出售小鱼', '#出售小鱼')
async def sell_small_fish(bot, ev):
    get_gold = 0
    def q_sell_fish(uid, fish, num, user_info):
        nonlocal get_gold
        uid = str(uid)
        if not user_info['fish'].get(fish):
            return f'你没有{fish}喔'
        if num > user_info['fish'][fish]:
            num = user_info['fish'][fish]
        decrease_value(uid, 'fish', fish, num, user_info)
        get_gold += num * fish_price[fish]
        return f'成功卖出{num}条{fish}，最终共获得{num * fish_price[fish]}金币'

    uid = ev.user_id
    if ev.user_id in BLACKUSERS:
        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
        return
    user_info = getUserInfo(uid)
    fishes = "🐟🦀🦐🐡🐠"
    result = []
    for fish in fishes:
        result.append(q_sell_fish(uid, fish, 9999, user_info))

    money.increase_user_money(uid, 'gold', get_gold)
    lock = asyncio.Lock()
    async with lock:
        dbPath = os.path.join(userPath, 'fishing/db')
        user_info_path = os.path.join(dbPath, 'user_info.json')
        total_info = loadData(user_info_path)
        total_info[uid] = user_info
        saveData(total_info, user_info_path)


    await bot.send(ev, '\n'.join(result), at_sender=True)
    
@sv.on_fullmatch('一键出售', '#一键出售')
async def sell_all_fish(bot, ev):
    get_gold = 0
    def all_sell_fish(uid, fish, num, user_info):
        nonlocal get_gold
        uid = str(uid)
        if not user_info['fish'].get(fish):
            return f'你没有{fish}喔'
        if num > user_info['fish'][fish]:
            num = user_info['fish'][fish]
        decrease_value(uid, 'fish', fish, num, user_info)
        get_gold += num * fish_price[fish]
        return f'成功卖出{num}条{fish}，最终共获得{num * fish_price[fish]}金币'

    uid = ev.user_id
#    if ev.user_id in BLACKUSERS:
#        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
#        return
    user_info = getUserInfo(uid)
    fishes = "🐟🦀🦐🐡🐠🦈🌟"
    result = []
    for fish in fishes:
        result.append(all_sell_fish(uid, fish, 99999, user_info))

    money.increase_user_money(uid, 'gold', get_gold)
    lock = asyncio.Lock()
    async with lock:
        dbPath = os.path.join(userPath, 'fishing/db')
        user_info_path = os.path.join(dbPath, 'user_info.json')
        total_info = loadData(user_info_path)
        total_info[uid] = user_info
        saveData(total_info, user_info_path)


    await bot.send(ev, '\n'.join(result), at_sender=True)



@sv.on_prefix('#出售', '#sell', '#出售', '卖鱼', 'sell', '出售')
async def free_func(bot, ev):
    message = ev.message.extract_plain_text().strip()
    msg_split = message.split()
    fish = ''
    num = 0
    if len(msg_split) == 2:
        if msg_split[0] not in ['🍙'] + FISH_LIST:
            return
        if not str.isdigit(msg_split[-1]):
            return
        fish = msg_split[0]
        num = int(msg_split[-1])
    elif len(msg_split) == 1:
        if msg_split[0] not in ['🍙'] + FISH_LIST:
            return
        fish = msg_split[0]
        num = 1
    else:
        return
    uid = ev.user_id
    result = sell_fish(uid, fish, num)
    await bot.send(ev, result, at_sender=True)

@sv.on_fullmatch('#钓鱼统计', '#钓鱼记录', '＃钓鱼统计', '＃钓鱼记录')
async def statistic_of_fish(bot, ev):
    uid = ev.user_id
    user_info = getUserInfo(uid)
    free_msg = f"已放生{user_info['statis']['free']}条鱼" if user_info['statis']['free'] else '还没有放生过鱼'
    sell_msg = f"已卖出{user_info['statis']['sell']}金币的鱼" if user_info['statis']['sell'] else '还没有出售过鱼'
    total_msg = f"总共钓上了{user_info['statis']['total_fish']}条鱼" if user_info['statis']['total_fish'] else '还没有钓上过鱼'
    await bot.send(ev, f'钓鱼统计：\n{free_msg}\n{sell_msg}\n{total_msg}', at_sender=True)


@sv.on_prefix('#换鱼竿', '＃换鱼竿')
async def change_rod_func(bot, ev):
    message = ev.message.extract_plain_text().strip()
    if not message:
        await bot.send(ev, rod_help)
        return
    if not str.isdigit(message):
        return
    _id = int(message)
    uid = ev.user_id
    result = change_fishrod(uid, _id)
    await bot.send(ev, result['msg'])


@sv.on_prefix('#换鱼竿', '＃换鱼竿')
async def change_rod_func(bot, ev):
    """
        换鱼竿（未实装）
    """
    message = ev.message.extract_plain_text().strip()
    if not message:
        await bot.send(ev, rod_help)
        return
    if not str.isdigit(message):
        return
    _id = int(message)
    uid = ev.user_id
    result = change_fishrod(uid, _id)
    await bot.send(ev, result['msg'])

@sv.on_prefix('#扔漂流瓶', '#丢漂流瓶', '＃扔漂流瓶', '扔漂流瓶')
async def driftbottle_throw(bot, ev):
    """
        扔漂流瓶
    """
    message = ev.message
    uid = ev.user_id
    if check_permission(uid):
        await bot.send(ev, '河神拒绝了你的漂流瓶...' + no)
        return
    user_info = getUserInfo(uid)
    if not user_info['fish']['✉']:
        await bot.send(ev, '背包里没有漂流瓶喔' + no)
        return
    if not throw_freq.check(uid) and not config.DEBUG_MODE:
        await bot.send(ev, '冰祈正在投放您的漂流瓶，休息一会再来吧~' + f'({int(throw_freq.left_time(uid))}s)')
        return
    resp = check_content(message)
    if resp['code'] < 0:
        await bot.send(ev, resp['reason'])
        return
    gid = ev.group_id
    _time = ev.time
    decrease_value(uid, 'fish', '✉', 1)
    resp = set_bottle(uid, gid, _time, message)
    throw_freq.start_cd(uid)
    await bot.send(ev, '你将漂流瓶放入了水中，目送它漂向诗与远方...')
    chain = []
    await chain_reply(bot, ev, user_id=uid, chain=chain, msg=f'QQ{uid}投放了一个漂流瓶。\n群聊：{gid}\n时间:{shift_time_style(_time)}\n漂流瓶ID:{resp}\n内容为：')
    await chain_reply(bot, ev, user_id=uid, chain=chain, msg=message)
    await bot.send_group_forward_msg(group_id=config.ADMIN_GROUP, messages=chain)

comment_cmd = [i + j for i in ['#', '＃'] for j in ['评论', '回复', '小纸条']]


@sv.on_prefix(comment_cmd)
async def comment_bottle_func(bot, ev):
    """
        对漂流瓶进行评论
    """
    uid = ev.user_id
    user_money = money.get_user_money(uid, 'gold')
    if check_permission(uid):
        await bot.send(ev, '漂流瓶拒绝了你的小纸条...' + no)
        return
    if user_money < config.COMMENT_PRICE:
        await bot.send(ev, f'评论漂流瓶需要{config.COMMENT_PRICE}枚金币' + no)
        return
    if not comm_freq.check(uid) and not config.DEBUG_MODE:
        await bot.send(ev, '小纸条正在重新装填中...' + f'({int(comm_freq.left_time(uid))}s)')
        return
    message = ev.message.extract_plain_text().strip()
    split_msg = message.split(' ', 1)
    if len(split_msg) != 2:
        return
    bottle_id = split_msg[0].strip()
    if not str.isdigit(bottle_id):
        return
    content = split_msg[1].strip()
    result = add_comment(bottle_id, uid, content)
    if result.get('code'):
        money.reduce_user_money(uid, 'gold', config.COMMENT_PRICE)
        try:
            await bot.send_group_msg(group_id=config.ADMIN_GROUP, message=f'{uid}对{bottle_id}号瓶子进行了评论：{content}')
        except Exception as e:
            hoshino.logger.error('向漂流瓶管理群发送消息失败：bot不在群里或被风控。')
    await bot.send(ev, result.get('resp'))
    comm_freq.start_cd(uid)


delete_comment_cmd = [i + j for i in ['#', '＃']
                      for j in ['删除回复', '删除评论', '删除小纸条']]


@sv.on_prefix(delete_comment_cmd)
async def delete_comment_func(bot, ev):
    """
        删除在某个漂流瓶下自己的回复
    """
    uid = ev.user_id
    message = ev.message.extract_plain_text().strip()
    if not str.isdigit(message):
        return
    result = delete_comment(message, uid)
    await bot.send(ev, result.get('resp'))


@sv.on_prefix('#超管删除回复', '#超管删除评论')
async def admin_del_comm_func(bot, ev):
    """
        强制删除某个漂流瓶下某个用户的回复
    """
    message = ev.message.extract_plain_text().strip()
    msg_split = message.split(' ', 1)
    if not len(msg_split):
        return
    bottle_id = msg_split[0]
    uid = msg_split[1]
    if not str.isdigit(bottle_id) or not str.isdigit(uid):
        return
    result = delete_comment(bottle_id, uid)
    await bot.send(ev, result.get('resp'))




@sv.on_fullmatch('#捡漂流瓶', '#捞漂流瓶', '＃捡漂流瓶', '捡漂流瓶')  # 仅做测试用
async def driftbottle_get(bot, ev):
    """
        捡漂流瓶
    """
    gid = ev.group_id
    uid = ev.user_id
    '''if int(uid) not in SUPERUSERS:
        return'''
    user_info = getUserInfo(uid)
    if user_info['fish']['🔮'] < 1:
        await bot.send(ev, f'捡漂流瓶需要{config.CRYSTAL_TO_NET}个水之心喔' + no)
        return
    bottle_amount = get_bottle_amount()
    if bottle_amount < 5:
        await bot.send(ev, f'漂流瓶太少了({bottle_amount}/5个)' + no)
        return
    if not get_freq.check(uid) and not config.DEBUG_MODE:
        await bot.send(ev, '漂流瓶累了，需要休息一会QAQ' + f'({int(get_freq.left_time(uid))}s)')
        return
    bottle, bottle_id = await check_bottle(bot, ev)
    if not bottle:
        await bot.send(ev, '没有漂流瓶可以捞喔...')
        return
    await bot.send(ev, f'你开始打捞漂流瓶...(🔮-{config.CRYSTAL_TO_NET})')
    if config.SEND_FORWARD:
        content = await format_message(bot, ev, bottle, bottle_id)
        await bot.send_group_forward_msg(group_id=ev.group_id, messages=content)
        get_freq.start_cd(uid)
        decrease_value(uid, 'fish', '🔮', config.CRYSTAL_TO_NET)
    else:
        content = format_msg_no_forward(bot, ev, bottle, bottle_id)
        await bot.send(ev, content)
        get_freq.start_cd(uid)
        # 就不扣水之心了



@sv.on_prefix('#合成漂流瓶', '＃合成漂流瓶', '合成漂流瓶')
async def driftbottle_compound(bot, ev):
    """
        合成漂流瓶
    """
    uid = ev.user_id
    message = ev.message.extract_plain_text().strip()
    if not message or not str.isdigit(message):
        amount = 1
    else:
        amount = int(message)
    user_info = getUserInfo(uid)
    result = compound_bottle(uid, amount)
    await bot.send(ev, result['msg'])


@sv.on_prefix('查看漂流瓶', '#查看漂流瓶')
async def admin_check_func(bot, ev):
    """
        管理员操作，查看瓶子，不增加捞起次数
    """
    uid = ev.user_id
    if uid not in SUPERUSERS:
        return
    message = ev.message.extract_plain_text().strip()
    if not str.isdigit(message):
        return
    result = await admin_check_bottle(bot, ev, message)
    if result.get('code'):
        await bot.send_group_forward_msg(group_id=ev.group_id, messages=result.get('resp'))
    else:
        await bot.send(ev, result.get('resp'))


@sv.on_prefix('捡特定漂流瓶', '#捡特定漂流瓶')
async def admin_driftbottle_get(bot, ev):
    uid = ev.user_id
    if uid not in SUPERUSERS:
        return
    message = ev.message.extract_plain_text().strip()
    if not str.isdigit(message):
        return
    bottle, bottle_id = await check_bottle(bot, ev, message)
    if not bottle:
        await bot.send(ev, '没有这个瓶子')
        return
    else:
        content = await format_message(bot, ev, bottle, bottle_id)
        await bot.send_group_forward_msg(group_id=ev.group_id, messages=content)


@sv.on_prefix('删除漂流瓶')
async def driftbottle_remove(bot, ev):
    """
        删除漂流瓶
    """
    gid = ev.group_id
    if gid != config.ADMIN_GROUP:
        return
    uid = ev.user_id
    message = ev.message.extract_plain_text().strip()
    if not (message and str.isdigit(message)):
        return
    if int(uid) not in SUPERUSERS:
        return
    resp = delete_bottle(message)
    await bot.send(ev, resp)


@sv.on_fullmatch('#清空')
async def driftbottle_truncate(bot, ev):
    """
        清空海域
    """
    uid = ev.user_id
    if int(uid) != SUPERUSERS[0]:
        return
    saveData({}, os.path.join(os.path.dirname(__file__), 'db/sea.json'))
    await bot.send(ev, ok)


@sv.on_fullmatch('#漂流瓶数量')
async def driftbottle_count(bot, ev):
    """
        查看漂流瓶数量
    """
    bottle_amount = get_bottle_amount()
    if not bottle_amount:
        await bot.send(ev, '目前水中没有漂流瓶...')
        return
    await bot.send(ev, f'当前一共有{get_bottle_amount()}个漂流瓶~')



@sv.on_prefix('#更新serif')
async def update_func(bot, ev):
    update_serif()
    await bot.send(ev, ok)


# <--------随机事件集-------->


@sv.on_fullmatch('1', '2', '3', '4')
async def random_event_trigger(bot, ev):
    uid = ev.user_id
    try:
        event_name = event_flag[str(uid)]
    except:
        hoshino.logger.info('随机事件未触发,事件标志未立起') if config.DEBUG_MODE else None
        return
    if not event_name:
        hoshino.logger.info('随机事件未触发,事件标志未设置') if config.DEBUG_MODE else None
        return
    session = interact.find_session(ev, name=event_name)
    if not session.state.get('started'):
        hoshino.logger.info('随机事件未触发,session未部署') if config.DEBUG_MODE else None
        return
    if uid != session.creator:
        hoshino.logger.info('非触发者的选择') if config.DEBUG_MODE else None
        return
    message = ev.raw_message
    _index = int(message.strip('/')) - 1
    if _index > len(random_event[event_name]['result']):
        hoshino.logger.info('序号超过选项数量') if config.DEBUG_MODE else None
        return
    event_flag[str(uid)] = ''
    session.close()
    await random_event[event_name]['result'][_index](bot, ev, uid)
    
    
##################################################################################################################
