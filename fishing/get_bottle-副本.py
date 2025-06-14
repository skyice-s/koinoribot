import os, random

import hoshino
from .util import shift_time_style
from ..utils import loadData, saveData, is_http_url, chain_reply
from .._R import userPath
import time


dbPath = os.path.join(userPath, 'fishing/db')
sea_path = os.path.join(dbPath, 'sea.json')
comment_path = os.path.join(dbPath, 'comment.json')
count_path = os.path.join(dbPath, 'count.json')
blacklist_path = os.path.join(dbPath, 'black_list.json')


def set_bottle(user_id, group_id, time_stamp, content):
    """
        扔漂流瓶
    """
    sea = loadData(sea_path)
    count = loadData(count_path)
    if not count:
        count = {'count': 0}
    count['count'] += 1
    _id = count['count']
    
    # 处理content格式
    processed_content = []
    for item in content:
        if item['type'] == 'image':
            # 统一file和url为url的值
            processed_item = {
                'type': 'image',
                'data': {
                    'file': item['data']['url'],  # 将file字段改为url的值
                    'subType': item['data']['subType'],
                    'url': item['data']['url']
                }
            }
            processed_content.append(processed_item)
        else:
            processed_content.append(item)
    
    bottle = {
        'uid': user_id,
        'gid': group_id,
        'time': time_stamp,
        'caught': 0,
        'content': processed_content  # 使用处理后的content
    }
    
    sea[_id] = bottle
    saveData(sea, sea_path)
    saveData(count, count_path)
    return _id


async def check_bottle(bot, ev, bottle_id = None):
    """
        捡漂流瓶
    """
    sea = loadData(sea_path)
    bottleId_list = list(sea.keys())
    if not bottleId_list:
        return None, None
    get_rand_id = random.choice(bottleId_list) if not bottle_id else str(bottle_id)
    hoshino.logger.info(f'捞起了{get_rand_id}号瓶子')
    sea[get_rand_id]['caught'] += 1
    bottle = sea[get_rand_id]
    if random.random() < (sea[get_rand_id]['caught'] ** 2 / 400):
        gid = sea[get_rand_id].get('gid')
        del sea[get_rand_id]
        try:
            content = await format_message(bot, ev, bottle, get_rand_id, gid)
            await bot.send_group_forward_msg(group_id=int(gid),
                                     message=content)
        except Exception as e:
            hoshino.logger.error(f'漂流瓶发送消息失败：{e}\n{str(e)}')
    saveData(sea, sea_path)
    return bottle, get_rand_id


async def admin_check_bottle(bot, ev, bottle_id):
    """
        检查瓶子
    """
    sea = loadData(sea_path)
    bottleId_list = list(sea.keys())
    if not bottleId_list:
        return {'code': 0, 'resp': '海里没有瓶子'}
    if str(bottle_id) not in bottleId_list:
        return {'code': 0, 'resp': '海里没有这个瓶子'}
    bottle = sea[str(bottle_id)]
    message = await format_message(bot, ev, bottle, bottle_id)
    return {'code': 1, 'resp': message}


def add_comment(bottle_id, uid, content):
    """
        评论漂流瓶
    """
    sea = loadData(sea_path)
    bottleId_list = list(sea.keys())
    if str(bottle_id) not in bottleId_list:
        return {'code': 0, 'resp': '河神没有找到这个瓶子...'}
    comment_dict = loadData(comment_path)
    comment = comment_dict.get(str(bottle_id))
    if not comment:
        comment = {}
        comment_dict[str(bottle_id)] = comment

    if comment.get(str(uid)):
        return {'code': 0, 'resp': '你发现漂流瓶里已经有了自己的小纸条...'}

    comment_dict[str(bottle_id)][str(uid)] = content
    saveData(comment_dict, comment_path)
    return {'code': 1, 'resp': '你将小纸条放进了漂流瓶里，并目送漂流瓶漂向远方...'}


def delete_comment(bottle_id, uid):
    sea = loadData(sea_path)
    bottleId_list = list(sea.keys())
    if str(bottle_id) not in bottleId_list:
        return {'code': 0, 'resp': '河神没有找到这个瓶子...'}
    comment_dict = loadData(comment_path)
    comment = comment_dict.get(str(bottle_id))
    if not comment:
        return {'code': 0, 'resp': f'瓶子里没有！'}
    if comment.get(str(uid)):
        del comment_dict[str(bottle_id)][str(uid)]
        saveData(comment_dict, comment_path)
        return {'code': 1, 'resp': f'小纸条离开了{bottle_id}号漂流瓶...'}
    else:
        return {'code': 0, 'resp': f'瓶子里没有！'}


async def format_message(bot, ev, bottle: dict, bottle_id, is_final = False):
    """
        格式化漂流瓶内容(合并转发)

    :param is_final: 当前是否是被捞起状态
    """
    uid = bottle['uid']
    gid = bottle['gid']
    bid = bottle_id
    _time = shift_time_style(bottle['time'])
    caught = bottle['caught']
    content = bottle['content']

    comment_dict = loadData(comment_path)
    comment = comment_dict.get(str(bottle_id))
    chain = []
    msg = '我的漂流瓶已经被捡走~\n内容为：' if is_final else '你捡到了我的漂流瓶~\n内容为：'
    await chain_reply(bot, ev, user_id=uid, chain=chain, msg=msg)
    await chain_reply(bot, ev, user_id=uid, chain=chain, msg=content)
    await chain_reply(bot, ev, user_id=uid, chain=chain, msg=f'漂流瓶id：{bid}\n投放地点(群聊)：{gid}\n投放时间：{_time}\n被捡起的次数：{caught}')
    if comment:
        await chain_reply(bot, ev, user_id=ev.self_id, chain=chain, msg=f'<-----漂流瓶的回复----->')
        for comm_id, comm_ctt in comment.items():
            await chain_reply(bot, ev, user_id=int(comm_id), chain=chain, msg=comm_ctt)
    return chain


def format_msg_no_forward(bot, ev, bottle: dict, bottle_id):
    """
        格式化漂流瓶内容(直接发送)
    """
    uid = bottle['uid']
    gid = bottle['gid']
    bid = bottle_id
    _time = shift_time_style(bottle['time'])
    caught = bottle['caught']
    content = bottle['content']
    msg = f'你捡到了{uid}的漂流瓶~\n投放时间：{_time}\n被捡起的次数：{caught}\n内容为：\n{content}'
    return msg


def delete_bottle(_id):
    _id = str(_id)
    sea = loadData(sea_path)
    bottleId_list = list(sea.keys())
    if _id not in bottleId_list:
        return '没有这个瓶子'
    del sea[_id]
    saveData(sea, sea_path)
    return '已成功移除该漂流瓶'


def check_permission(user_id):
    """
        检查是否在黑名单里，以及黑名单时长是否已到
    """
    cur_time = int(time.time())
    black_list = loadData(blacklist_path)
    uid = str(user_id)
    if uid in black_list.keys():
        if cur_time > black_list[uid]:
            del black_list[uid]
            saveData(black_list, blacklist_path)
            return False
        else:
            return True
    else:
        return False


def add_to_blacklist(user_id, _time: int = 86400):
    """
        添加用户至漂流瓶黑名单
        时长可选，默认为1天
    """
    black_list = loadData(blacklist_path)
    uid = str(user_id)
    cur_time = int(time.time())
    expire_time = cur_time + int(_time)
    black_list[uid] = expire_time
    saveData(black_list, blacklist_path)
    timeArray = time.localtime(expire_time)
    otherStyleTime = time.strftime("%m月%d日%H:%M:%S", timeArray)
    return f'已成功将{user_id}添加至黑名单，将于{otherStyleTime}解禁'


def remove_from_blacklist(user_id):
    """
        移除黑名单
    """
    black_list = loadData(blacklist_path)
    uid = str(user_id)
    if uid in black_list:
        del black_list[uid]
        saveData(black_list, blacklist_path)
        return f'已成功将{user_id}移除黑名单'
    else:
        return f'{user_id}不在黑名单里'


def show_blacklist():
    """
        列出黑名单
    """
    black_list = loadData(blacklist_path)
    msg = '黑名单列表：'
    msg2 = ''
    if len(black_list) == 0:
        msg += '\n大家都是好孩子！'
        return msg
    cur_time = int(time.time())
    for user, _time in black_list.items():
        timeArray = time.localtime(_time)
        if cur_time < _time:
            otherStyleTime = time.strftime("%m月%d日%H:%M:%S", timeArray)
            msg2 += f'\nQQ号：{user}\n解禁日期：{otherStyleTime}'
        else:
            continue
    if not msg2:
        msg += '\n大家都是好孩子！'
    else:
        msg += msg2
    return msg


def check_content(content: list):
    text = ''
    image = 0
    at = 0
    for i in content:
        if i['type'] == 'image':
            image += 1
        if i['type'] == 'text':
            text += i['data']['text']
        if i['type'] == 'at':
            at += 1
    if is_http_url(text):
        resp = {'code': -1, 'reason': '含有链接，不可以放进漂流瓶里...'}
    elif not text and image == 0:
        resp = {'code': -1, 'reason': '这是一个空漂流瓶喔...请装入要发送的内容，如：#扔漂流瓶 你好'}
    elif len(text) > 200:
        resp = {'code': -1, 'reason': '字数太多了，漂流瓶里放不下...'}
    elif image > 4:
        resp = {'code': -1, 'reason': '图片太多了，漂流瓶里放不下...'}
    elif at:
        resp = {'code': -1, 'reason': '艾特会在漂流瓶里挥发掉...'}
    else:
        resp = {'code': 1, 'reason': None}
    return resp


def get_bottle_amount():
    sea = loadData(sea_path)
    return len(list(sea.keys()))