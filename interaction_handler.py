import os

from nonebot.message import CanceledException, message_preprocessor

from ._interact import interact, ActSession
from .utils import loadData, saveData
from hoshino import logger
from hoshino.typing import CQEvent, HoshinoBot
from .config import PUBLIC_BOT
from .money import increase_user_money

wl_path = os.path.join(os.path.dirname(__file__), '../../public_wlist.json')

debug_mode = True  # 抢红包功能测试用的

@message_preprocessor
async def handler_interaction(bot: HoshinoBot, ev: CQEvent, _):
    if interact.find_session(ev):
        session = interact.find_session(ev)

        if ev.raw_message == 'exit' and ev.user_id == session.creator: #创建者选择退出
            msg = ''
            if session.name == '金币红包':
                remain_money = sum(session.state['hb_list'])
                if debug_mode:
                    increase_user_money(session.state['owner'], 'gold', remain_money)
                msg += f'\n已返还剩余的{remain_money}枚金币'
            session.close()
            await session.finish(ev, f'{session.name}已经结束~' + msg)

        if session.is_expire():
            msg = ''
            if session.name == '金币红包':
                remain_money = sum(session.state['hb_list'])
                if debug_mode:
                    increase_user_money(session.state['owner'], 'gold', remain_money)
                msg += f'\n已返还剩余的{remain_money}枚金币'
            session.close()
            await bot.send(ev, f'时间已到，{session.name}自动结束' + msg)

        func = session.actions.get(ev.raw_message) if ev.user_id in session.users else None

        if PUBLIC_BOT:
            wlist = loadData(wl_path)
            if ev.self_id not in list(wlist.values()):
                logger.info(f'unverified bot, ignore command')
                return

        if func:
            logger.info(f'triggered interaction action {func.__name__}')
            try:
                await func(ev, session)
            except CanceledException as e:
                logger.info(e)
            except Exception as ex:
                logger.exception(ex)
            raise CanceledException('handled by interact handler')
        elif session.handle_msg:
            await session.handle_msg(ev, session)
        else:
            pass