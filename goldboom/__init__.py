import json
import asyncio
from aiocqhttp.message import MessageSegment
from hoshino.service import Service
from hoshino.typing import HoshinoBot, CQEvent as Event
from hoshino.util import silence
from random import randint, shuffle
from itertools import cycle
from hoshino import R
from ..utils import chain_reply, saveData, loadData
from .._R import get, userPath
import sys
import os
from .. import money, config
from hoshino.config import SUPERUSERS
import time

sv = Service('金币炸弹', visible=True, enable_on_default=True)
no = get('emotion/no.png').cqcode
ok = get('emotion/ok.png').cqcode
# 游戏会话管理
game_sessions = {}  # {group_id: {session_id: 金币炸弹session}}
session_id_counter = 0 # 用于生成唯一的会话ID
MAX_POT_LIMIT = 1000 #最大奖池
PENALTY = 1000 #失败惩罚
TIMEOUT = 300 # 超时时间

# 金币炸弹会话类
class GoldBombSession:
    def __init__(self, group_id, starter_id, bot):
        global session_id_counter
        session_id_counter += 1
        self.session_id = session_id_counter #生成唯一的会话ID
        self.group_id = group_id
        self.starter_id = starter_id
        self.bot = bot  # HoshinoBot 实例
        self.players = {}  # {user_id: pot_amount}  每个玩家的金币奖池
        self.player_order = [] # 玩家顺序列表
        self.is_running = False # 游戏是否正在运行
        self.prepared = {}  # {user_id: True/False}  玩家是否准备
        self.failed = {} # {user_id: True/False} 玩家是否失败
        self.all_stopped = False # 玩家是否都停止下注
        self.turn = None  # 当前回合玩家
        self.task = None  # 定时任务
        self.start_time = None # 记录游戏开始的时间

    async def start(self):
        self.is_running = True # 标记游戏开始
        self.start_time = time.time()  # 记录游戏开始的时间
        self.player_order = list(self.players.keys())
        shuffle(self.player_order)  # 打乱玩家顺序
        self.turn = cycle(self.player_order) # 轮流下注的玩家
        await self.next_turn()  # 开始第一回合
        self.set_timer() # 启动定时任务

    async def next_turn(self):
        # 找到下一个没有失败的玩家
        while True:
            # 检查是否所有玩家都失败
            if all(self.failed.get(user_id, False) for user_id in self.players):
                await self.end_game()
                break

            # 增加判断：如果只剩一个玩家且该玩家已失败，则结束游戏
            if len(self.player_order) == 0:
                 await self.end_game()
                 break
            try:

                next_player = next(self.turn)
                if not self.failed.get(next_player, False): # 确保玩家没有失败
                    self.current_player = next_player
                    await self.bot.send_group_msg(group_id=self.group_id, message=f'轮到 {MessageSegment.at(self.current_player)} 下注 (下注/停止下注)。')
                    break # 找到下一个玩家，跳出循环
            except StopIteration:  # 所有玩家都停止下注或失败
                await self.end_game()
                break # 跳出循环
            except Exception as e:
                print(f"next_turn error: {e}")
                await self.end_game()
                break

    async def bet(self, user_id):
        if user_id != self.current_player:
            await self.bot.send_group_msg(group_id=self.group_id, message=f'还没轮到你下注。');
            return

        amount = randint(100, 500)
        current_pot = self.players[user_id]
        new_pot = current_pot + amount

        if new_pot > MAX_POT_LIMIT:
            self.failed[user_id] = True # 标记玩家失败
            self.players[user_id] = MAX_POT_LIMIT # 奖池固定为上限
            await self.bot.send_group_msg(group_id=self.group_id, message=f'{MessageSegment.at(user_id)} 下注 {amount} 金币，超出上限！判定失败，已达到{MAX_POT_LIMIT}金币，禁止继续下注。')

            #从玩家顺序中移除，防止无限循环
            if user_id in self.player_order:
                self.player_order.remove(user_id)

            await self.next_turn() # 轮到下一位玩家

        else:
            self.players[user_id] = new_pot
            await self.bot.send_group_msg(group_id=self.group_id, message=f'{MessageSegment.at(user_id)} 下注 {amount} 金币，目前奖池 {new_pot}。')
            await self.next_turn()

    async def stop_bet(self, user_id):
        if user_id not in self.players:
            return

        self.player_order.remove(user_id) # 从玩家顺序中移除
        if not self.player_order: # 如果所有玩家都停止下注
            await self.end_game()
            return

        # 重置轮换器
        self.turn = cycle(self.player_order)
        await self.next_turn()

    async def end_game(self):
        if not self.is_running:
            return

        self.is_running = False
        await self.bot.send_group_msg(group_id=self.group_id, message='所有玩家已停止下注或失败，正在结算...')

        winner = None
        min_diff = float('inf')
        all_failed = True  # 默认所有人都失败

        # 寻找离上限最近的玩家
        for user_id, pot in self.players.items():
            if not self.failed.get(user_id, False):  # 排除失败的玩家
                all_failed = False  # 至少有一个人没失败
                diff = MAX_POT_LIMIT - pot
                if diff < min_diff:
                    min_diff = diff
                    winner = user_id

        # 判断胜负
        if all_failed:
            message = '所有玩家都失败了，游戏流局！每人扣除1000金币。\n'
            for user_id in self.players:
                money.reduce_user_money(user_id, 'gold', PENALTY)
                message += f'{MessageSegment.at(user_id)} 扣除 {PENALTY} 金币。\n'
            await self.bot.send_group_msg(group_id=self.group_id, message=message)

        else:
            message = f'恭喜 {MessageSegment.at(winner)} 获胜，获得奖池中的所有金币！\n'
            wining_money = self.players[winner]
            money.increase_user_money(winner, 'gold', wining_money)
            message += f'获得 {wining_money} 金币。\n'
            for user_id in self.players:
                if user_id != winner:
                     money.reduce_user_money(user_id, 'gold', PENALTY)
                     message += f'{MessageSegment.at(user_id)} 扣除 {PENALTY} 金币。\n'
            await self.bot.send_group_msg(group_id=self.group_id, message=message)

        # 清理会话
        self.cancel_timer()
        del game_sessions[self.group_id][self.session_id]
        if not game_sessions[self.group_id]:
            del game_sessions[self.group_id]

    async def close(self):
        if not self.is_running:
            return

        self.is_running = False
        await self.bot.send_group_msg(group_id=self.group_id, message='游戏已关闭。')

        self.cancel_timer() #取消定时任务
        del game_sessions[self.group_id][self.session_id]
        if not game_sessions[self.group_id]:
            del game_sessions[self.group_id]

    # 定时任务
    async def auto_close(self):
        if self.is_running:  # 只有当游戏正在运行时才执行
            if time.time() - self.start_time >= TIMEOUT: # 检查是否超时
                await self.bot.send_group_msg(group_id=self.group_id, message='游戏会话超时，自动关闭。')
                await self.close()

    def set_timer(self):
        self.task = asyncio.ensure_future(self.auto_close_loop())
        self.task.set_name(f"金币炸弹-{self.group_id}-{self.session_id}") #设置任务名称

    async def auto_close_loop(self):
        while self.is_running:
            await asyncio.sleep(60)  # 每隔60秒检查一次是否超时
            await self.auto_close()

    def cancel_timer(self):
        if self.task:
            self.task.cancel()

    async def player_ready(self, user_id):
        if user_id not in self.players:
            await self.bot.send_group_msg(group_id=self.group_id, message='你还没有加入游戏。')
            return

        self.prepared[user_id] = True # 标记玩家已准备
        await self.bot.send_group_msg(group_id=self.group_id, message=f'{MessageSegment.at(user_id)} 已准备。')

        if len(self.players) >= 2 and all(self.prepared.values()): # 检查是否所有玩家都已准备
            await self.bot.send_group_msg(group_id=self.group_id, message='所有玩家已准备，游戏即将开始...')
            await self.start()

    async def player_quit(self, user_id):
        if user_id not in self.players:
            await self.bot.send_group_msg(group_id=self.group_id, message='你还没有加入游戏。')
            return

        if self.is_running: # 游戏已经开始
            await self.bot.send_group_msg(group_id=self.group_id, message='游戏已经开始，无法退出。')
            return

        del self.players[user_id] # 移除玩家
        if user_id in self.prepared:
            del self.prepared[user_id]

        await self.bot.send_group_msg(group_id=self.group_id, message=f'{MessageSegment.at(user_id)} 退出了游戏。')

        if not self.players: # 没有玩家了
            await self.close()

# 指令处理
@sv.on_fullmatch('金币炸弹')
async def start_game(bot: HoshinoBot, ev: Event):
    group_id = ev.group_id
    user_id = ev.user_id

    if group_id in game_sessions and game_sessions[group_id]:
        await bot.send(ev, '当前群已有进行中的金币炸弹游戏。')
        return

    # 创建新的游戏会话
    session = GoldBombSession(group_id, user_id, bot)

    # 初始化会话
    if group_id not in game_sessions:
        game_sessions[group_id] = {}
    game_sessions[group_id][session.session_id] = session

    await bot.send(ev, f'金币炸弹游戏已发起，等待玩家加入，发送“加入游戏”加入游戏。')

@sv.on_fullmatch('加入游戏')
async def join_game(bot: HoshinoBot, ev: Event):
    group_id = ev.group_id
    user_id = ev.user_id
    user_gold = money.get_user_money(user_id, 'gold')
    if user_gold<1000:
        await bot.send(ev, '你没有足够的赌资喔...' + no)
        return
    if group_id not in game_sessions or not game_sessions[group_id]:
        await bot.send(ev, '当前群没有进行中的金币炸弹游戏，发送“金币炸弹”发起游戏。')
        return

    # 获取当前会话
    session = list(game_sessions[group_id].values())[0] #只取第一个

    if user_id in session.players:
        await bot.send(ev, '你已经加入了游戏。')
        return

    if len(session.players) >= 3:
        await bot.send(ev, '游戏人数已满。')
        return

    # 加入玩家
    session.players[user_id] = 0  # 初始金币奖池为0
    session.prepared[user_id] = False  # 初始为未准备
    session.failed[user_id] = False # 初始为未失败

    await bot.send(ev, f'{MessageSegment.at(user_id)} 加入游戏。当前人数 {len(session.players)}/3。请发送"准备"开始游戏')

@sv.on_fullmatch('准备')
async def player_ready(bot: HoshinoBot, ev: Event):
    group_id = ev.group_id
    user_id = ev.user_id

    if group_id not in game_sessions or not game_sessions[group_id]:
        await bot.send(ev, '当前群没有进行中的金币炸弹游戏。')
        return

    session = list(game_sessions[group_id].values())[0]
    if session.is_running:
        await bot.send(ev, '游戏已经开始了。')
        return

    await session.player_ready(user_id)

@sv.on_fullmatch('退出游戏')
async def player_quit(bot: HoshinoBot, ev: Event):
    group_id = ev.group_id
    user_id = ev.user_id

    if group_id not in game_sessions or not game_sessions[group_id]:
        await bot.send(ev, '当前群没有进行中的金币炸弹游戏。')
        return

    session = list(game_sessions[group_id].values())[0]
    await session.player_quit(user_id)

@sv.on_fullmatch('下注')
async def bet(bot: HoshinoBot, ev: Event):
    group_id = ev.group_id
    user_id = ev.user_id

    if group_id not in game_sessions or not game_sessions[group_id]:
        await bot.send(ev, '当前群没有进行中的金币炸弹游戏。')
        return

    session = list(game_sessions[group_id].values())[0]
    if not session.is_running:
        await bot.send(ev, '游戏尚未开始，请等待所有玩家准备。')
        return

    await session.bet(user_id)

@sv.on_fullmatch('停止下注')
async def stop_bet(bot: HoshinoBot, ev: Event):
    group_id = ev.group_id
    user_id = ev.user_id

    if group_id not in game_sessions or not game_sessions[group_id]:
        await bot.send(ev, '当前群没有进行中的金币炸弹游戏。')
        return

    session = list(game_sessions[group_id].values())[0]
    if not session.is_running:
         await bot.send(ev, '游戏尚未开始，请等待所有玩家准备。')
         return
    await bot.send(ev, f'{MessageSegment.at(user_id)} 停止下注。')
    await session.stop_bet(user_id)
    
    
@sv.on_prefix('关闭游戏')
async def close_game_by_admin(bot: HoshinoBot, ev: Event):
    """
    管理员直接关闭当前群聊中的金币炸弹会话。
    """
    group_id = ev.group_id
    user_id = ev.user_id

    if user_id not in SUPERUSERS:
        await bot.send(ev, "只有管理员才能使用此指令。", at_sender=True)
        return

    if group_id not in game_sessions or not game_sessions[group_id]:
        await bot.send(ev, '当前群没有进行中的金币炸弹游戏。')
        return

    # 关闭当前群组的所有金币炸弹会话
    sessions_to_close = list(game_sessions[group_id].items())  # 复制一份会话列表，避免迭代中修改字典
    for session_id, session in sessions_to_close:
        await session.close() #先正确关闭session
        del game_sessions[group_id][session_id]  # 从字典中删除会话

    # 检查是否需要删除 group_id 对应的键
    if not game_sessions[group_id]:
        del game_sessions[group_id]

    await bot.send(ev, '管理员已关闭当前群的金币炸弹游戏。')
    
help_goldboom = '''
金币炸弹游戏帮助：

这是一个最多三人参与的金币奖池游戏。

**游戏流程：**
1.  发送“金币炸弹”发起游戏。
2.  玩家发送“加入游戏”加入游戏。
3.  加入游戏的玩家发送“准备”指令，当所有玩家都准备后，游戏开始。
4.  玩家轮流发送“下注”指令，随机增加自己奖池的金币。
5.  每个玩家的奖池上限为1000金币，超过上限则立即判定失败。
6.  玩家可以发送“停止下注”指令提前结束自己的下注。
7.  当所有玩家都停止下注或失败后，游戏结束，未失败的玩家中，奖池金额最接近上限的玩家获胜，获得自己奖池中的所有金币。
8.  失败的玩家扣除1000金币。
9.  游戏开始前，玩家可以发送“退出游戏”指令退出游戏
10. 如果游戏超过3分钟无人操作，则自动关闭会话。

**指令列表：**
*   金币炸弹：发起游戏
*   加入游戏：加入游戏
*   准备：准备游戏
*   退出游戏：退出游戏
*   下注：增加奖池金额
*   停止下注：停止下注
*   金币炸弹帮助：查看游戏帮助
'''
@sv.on_fullmatch('金币炸弹帮助')
async def goldboom_help(bot, ev):
    """
        拉取游戏帮助
    """
    chain = []
    await chain_reply(bot, ev, chain, help_goldboom)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)