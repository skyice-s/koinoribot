from hoshino import Service, util, priv
from hoshino.typing import CQEvent
import re
import random
import hoshino
from .._R import get
from .ability_config import buff, debuff
from .. import money, config


sv = Service(
    name = '超能力',  #功能名
    use_priv = priv.NORMAL, #使用权限   
    manage_priv = priv.ADMIN, #管理权限
    visible = True, #False隐藏
    enable_on_default = True, #是否默认启用
    bundle = '通用', #属于哪一类
    )

no = get('emotion/no.png').cqcode

@sv.on_fullmatch('我的超能力')
async def my_ability(bot, ev: CQEvent):
    uid = ev.user_id
    name = ev.sender['card'] or ev.sender['nickname']
    user_gold = money.get_user_money(uid, 'gold')
    if user_gold < config.abilityfee:
        await bot.send(ev, f'\n生成超能力需要{config.abilityfee}金币哦~'+no, at_sender=True)
        return
    money.reduce_user_money(uid, 'gold', config.abilityfee)
    buff_list = list(buff) # 将集合转换为列表
    random_buff = random.choice(buff_list)
    debuff_list = list(debuff)
    random_debuff = random.choice(debuff_list)
    await bot.send(ev, f"\n你的超能力是:\n{random_buff}\n副作用是:\n{random_debuff}", at_sender=True)