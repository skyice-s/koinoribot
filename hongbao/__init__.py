from hoshino import Service
from hoshino.util import FreqLimiter
from .._interact import interact, ActSession
from .._R import get
from ..utilize import get_double_mean_money
from ..money import get_user_money, reduce_user_money, increase_user_money
from ..config import BLACKUSERS


sv = Service('抢红包-冰祈')

no = get('emotion/no.png').cqcode

freq = FreqLimiter(10)

debug_mode = False  # 测试模式，不消耗金币

@sv.on_prefix('发红包')
async def fa_hongbao(bot, ev):
    message = ev.message.extract_plain_text().strip()
    if not message:
        return
    if interact.find_session(ev, name='金币红包'):
        session = interact.find_session(ev, name='金币红包')
        if session.is_expire():

            # 剩余的钱返还给发起人
            remain_money = sum(session.state['hb_list'])
            if not debug_mode:
                increase_user_money(session.state['owner'], 'gold', remain_money)
            session.close()
        else:
            await bot.send(ev, f'当前还有没领完的金币红包~')
            return

    if ev.user_id in BLACKUSERS:
        await bot.send(ev, '\n操作失败，账户被冻结，请联系管理员寻求帮助。' +no, at_sender=True)
        return
    # 此处为冷却时间判定
    if not freq.check(ev.user_id):
        await bot.send(ev, '十秒钟之内只能发一个红包' + no)
        return

    money_and_mxuser = message.split()
    if len(money_and_mxuser) == 1:
        currency = message
        max_user = '5'
    else:
        currency = money_and_mxuser[0]
        max_user = money_and_mxuser[1]
    print(currency, max_user)

    if not str.isdigit(currency) or not str.isdigit(max_user):
        await bot.send(ev, '要阿拉伯数字' + no)
        return

    currency = int(currency)
    max_user = int(max_user)

    group_info = await bot.get_group_info(group_id=ev.group_id, no_cache=True)

    if max_user <= 2 or max_user > group_info['member_count']:
        await bot.send(ev, '红包个数不对' + no)
        return

    user_money = get_user_money(ev.user_id, 'gold')

    if currency <= max_user or currency > int(user_money):
        await bot.send(ev, '金币数量不对' + no)
        return

    freq.start_cd(ev.user_id)

    if not debug_mode:
        reduce_user_money(ev.user_id, 'gold', currency)

    hongbao_list = get_double_mean_money(currency, max_user)
    session = ActSession.from_event('金币红包', ev, usernum_limit = True, max_user = max_user, expire_time=600)
    interact.add_session(session)
    session.state['hb_list'] = hongbao_list
    session.state['owner'] = ev.user_id
    session.state['users'] = []

    user_info = await bot.get_group_member_info(group_id=ev.group_id, user_id=ev.user_id)
    nickname = user_info['nickname']

    await bot.send(ev, f'{nickname}发了一个{currency}枚金币的红包，一共有{max_user}份~\n使用"抢红包"来领取红包')


@sv.on_prefix('抢红包')
async def qiang_hongbao(bot, ev):
    if not interact.find_session(ev, name='金币红包'):
        return
    session = interact.find_session(ev, name='金币红包')
    if session.is_expire():
        remain_money = sum(session.state['hb_list'])
        if not debug_mode:
            increase_user_money(session.state['owner'], 'gold', remain_money)
        await session.send(ev, f'红包过期，已返还剩余的{remain_money}枚金币')
        session.close()
        return
    if ev.user_id in session.state['users']:
        await bot.send(ev, '你已经抢过红包了！')
        return
    if session.state['hb_list']:
        user_gain = session.state['hb_list'].pop()
        session.state['users'].append(ev.user_id)
        if not debug_mode:
            increase_user_money(ev.user_id, 'gold', user_gain)
            await bot.send(ev, f'你抢到了{user_gain}枚金币~', at_sender=True)
    if not session.state['hb_list']:
        session.close()
        await bot.send(ev, '红包领完了~')
        return







