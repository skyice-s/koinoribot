import os
import random
import base64
import aiohttp
import asyncio
import hoshino
import time
import requests

from .util import shift_time_style
from ..utils import loadData, saveData, is_http_url, chain_reply
from .._R import userPath

dbPath = os.path.join(userPath, 'fishing/db')
imgPath = os.path.join(dbPath, 'img')
sea_path = os.path.join(dbPath, 'sea.json')
comment_path = os.path.join(dbPath, 'comment.json')
count_path = os.path.join(dbPath, 'count.json')
blacklist_path = os.path.join(dbPath, 'black_list.json')

os.makedirs(imgPath, exist_ok=True)

def save_image_from_url(url, path):
    resp = requests.get(url)
    if resp.status_code == 200:
        with open(path, 'wb') as f:
            f.write(resp.content)

def image_to_base64(path):
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        hoshino.logger.error(f"图片转base64失败: {e}")
        return None

def set_bottle(user_id, group_id, time_stamp, content):
    sea = loadData(sea_path)
    count = loadData(count_path)
    if not count:
        count = {'count': 0}
    count['count'] += 1
    _id = count['count']

    processed_content = []
    for idx, item in enumerate(content):
        if item['type'] == 'image':
            url = item['data']['url']
            filename = f"{_id}_{idx}.jpg"
            local_path = os.path.join(imgPath, filename)
            save_image_from_url(url, local_path)
            processed_item = {
                'type': 'image',
                'data': {
                    'file': filename,
                    'subType': item['data']['subType'],
                    'url': url
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
        'content': processed_content
    }

    sea[_id] = bottle
    saveData(sea, sea_path)
    saveData(count, count_path)
    return _id

async def check_bottle(bot, ev, bottle_id=None):
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
            await bot.send_group_forward_msg(group_id=int(gid), message=content)
        except Exception as e:
            hoshino.logger.error(f'漂流瓶发送消息失败：{e}\n{str(e)}')
    saveData(sea, sea_path)
    return bottle, get_rand_id

async def admin_check_bottle(bot, ev, bottle_id):
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
    sea = loadData(sea_path)
    if str(bottle_id) not in sea:
        return {'code': 0, 'resp': '河神没有找到这个瓶子...'}
    comment_dict = loadData(comment_path)
    comment = comment_dict.get(str(bottle_id), {})
    if str(uid) in comment:
        return {'code': 0, 'resp': '你发现漂流瓶里已经有了自己的小纸条...'}
    comment[str(uid)] = content
    comment_dict[str(bottle_id)] = comment
    saveData(comment_dict, comment_path)
    return {'code': 1, 'resp': '你将小纸条放进了漂流瓶里，并目送漂流瓶漂向远方...'}

def delete_comment(bottle_id, uid):
    sea = loadData(sea_path)
    if str(bottle_id) not in sea:
        return {'code': 0, 'resp': '河神没有找到这个瓶子...'}
    comment_dict = loadData(comment_path)
    comment = comment_dict.get(str(bottle_id))
    if comment and str(uid) in comment:
        del comment[str(uid)]
        saveData(comment_dict, comment_path)
        return {'code': 1, 'resp': f'小纸条离开了{bottle_id}号漂流瓶...'}
    else:
        return {'code': 0, 'resp': f'瓶子里没有！'}

async def format_message(bot, ev, bottle, bottle_id, is_final=False):
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

    for idx, item in enumerate(content):
        if item['type'] == 'text':
            await chain_reply(bot, ev, user_id=uid, chain=chain, msg=item['data']['text'])
        elif item['type'] == 'image':
            filename = item['data']['file']
            local_path = os.path.join(imgPath, filename)
            base64_data = image_to_base64(local_path)
            if base64_data:
                await chain_reply(bot, ev, user_id=uid, chain=chain, msg=f"[CQ:image,file=base64://{base64_data}]")

    await chain_reply(bot, ev, user_id=uid, chain=chain, msg=f'漂流瓶id：{bid}\n投放地点(群聊)：{gid}\n投放时间：{_time}\n被捡起的次数：{caught}')
    if comment:
        await chain_reply(bot, ev, user_id=ev.self_id, chain=chain, msg='<-----漂流瓶的回复----->')
        for comm_id, comm_ctt in comment.items():
            await chain_reply(bot, ev, user_id=int(comm_id), chain=chain, msg=comm_ctt)
    return chain

def format_msg_no_forward(bot, ev, bottle, bottle_id):
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
    if _id not in sea:
        return '没有这个瓶子'
    del sea[_id]
    saveData(sea, sea_path)
    return '已成功移除该漂流瓶'

def check_permission(user_id):
    cur_time = int(time.time())
    black_list = loadData(blacklist_path)
    uid = str(user_id)
    if uid in black_list:
        if cur_time > black_list[uid]:
            del black_list[uid]
            saveData(black_list, blacklist_path)
            return False
        return True
    return False

def add_to_blacklist(user_id, _time: int = 86400):
    black_list = loadData(blacklist_path)
    uid = str(user_id)
    cur_time = int(time.time())
    expire_time = cur_time + int(_time)
    black_list[uid] = expire_time
    saveData(black_list, blacklist_path)
    otherStyleTime = time.strftime("%m月%d日%H:%M:%S", time.localtime(expire_time))
    return f'已成功将{user_id}添加至黑名单，将于{otherStyleTime}解禁'

def remove_from_blacklist(user_id):
    black_list = loadData(blacklist_path)
    uid = str(user_id)
    if uid in black_list:
        del black_list[uid]
        saveData(black_list, blacklist_path)
        return f'已成功将{user_id}移除黑名单'
    return f'{user_id}不在黑名单里'

def show_blacklist():
    black_list = loadData(blacklist_path)
    msg = '黑名单列表：'
    msg2 = ''
    if not black_list:
        return msg + '\n大家都是好孩子！'
    cur_time = int(time.time())
    for user, _time in black_list.items():
        if cur_time < _time:
            otherStyleTime = time.strftime("%m月%d日%H:%M:%S", time.localtime(_time))
            msg2 += f'\nQQ号：{user}\n解禁日期：{otherStyleTime}'
    return msg + (msg2 if msg2 else '\n大家都是好孩子！')

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
        return {'code': -1, 'reason': '含有链接，不可以放进漂流瓶里...'}
    elif not text and image == 0:
        return {'code': -1, 'reason': '这是一个空漂流瓶喔...请装入要发送的内容，如：#扔漂流瓶 你好'}
    elif len(text) > 200:
        return {'code': -1, 'reason': '字数太多了，漂流瓶里放不下...'}
    elif image > 4:
        return {'code': -1, 'reason': '图片太多了，漂流瓶里放不下...'}
    elif at:
        return {'code': -1, 'reason': '艾特会在漂流瓶里挥发掉...'}
    else:
        return {'code': 1, 'reason': None}

def get_bottle_amount():
    sea = loadData(sea_path)
    return len(list(sea.keys()))
