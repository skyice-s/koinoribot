import json
import os
import random
import time
import base64
from datetime import datetime, timedelta
import math
import asyncio
import io
from ..utils import chain_reply
from .._R import get, userPath
from hoshino import Service, priv, R
from hoshino.typing import CQEvent, MessageSegment
from .. import money
from hoshino.config import SUPERUSERS

no = get('emotion/no.png').cqcode
ok = get('emotion/ok.png').cqcode
sv = Service('pet_raising', manage_priv=priv.ADMIN, enable_on_default=True)

# 文件路径配置
PET_DATA_DIR = os.path.join(userPath, 'chongwu')
PET_DATABASE = os.path.join(PET_DATA_DIR, 'pet_data.json')
USER_PET_DATABASE = os.path.join(PET_DATA_DIR, 'user_pets.json')
USER_ITEMS_DATABASE = os.path.join(PET_DATA_DIR, 'user_items.json')

# 锁防止并发问题
pet_data_lock = asyncio.Lock()
user_pet_lock = asyncio.Lock()
user_items_lock = asyncio.Lock()


@sv.on_prefix(('购买宝石', '买宝石'))
async def buy_gem(bot, ev):
    user_id = ev.user_id
    args = ev.message.extract_plain_text().strip().split()
    
    # 检查参数
    if not args or not args[0].isdigit():
        await bot.send(ev, "请指定要购买的数量！\n例如：购买宝石 5", at_sender=True)
        return
    
    quantity = int(args[0])
    if quantity <= 0:
        await bot.send(ev, "购买数量必须大于0！", at_sender=True)
        return
    
    # 计算总价
    price_per_gem = 1000
    total_cost = quantity * price_per_gem
    
    # 检查用户金币
    user_gold = money.get_user_money(user_id, 'gold')
    if user_gold < total_cost:
        await bot.send(ev, f"金币不足！购买{quantity}个宝石需要{total_cost}金币，你只有{user_gold}金币。{no}", at_sender=True)
        return
    
    # 执行购买
    if money.reduce_user_money(user_id, 'gold', total_cost):
        money.increase_user_money(user_id, 'kirastone', quantity)
        await bot.send(ev, f"成功购买{quantity}个宝石，花费了{total_cost}金币！{ok}", at_sender=True)
    else:
        await bot.send(ev, "购买失败，请稍后再试！", at_sender=True)



# 扭蛋配置
GACHA_COST = 10  # 每个扭蛋消耗10宝石
GACHA_REWARDS = {
    "普通": {
        "小猫咪": 40,
        "小狗": 40,
        "小狐狸": 20
    },
    "稀有": {
        "魔法兔": 50,
        "小狐狸": 50
    },
    "史诗": {
        "蠢萝莉": 10,
        "熊猫宝宝": 90
    }
}
GACHA_CONSOLE_PRIZE = 50  # 安慰奖金币数量

# 基础宠物类型
BASE_PETS = {
    "小猫咪": {
        "max_hunger": 100,
        "max_energy": 100,
        "max_happiness": 100,
        "growth_rate": 1.2,
        "rarity": "普通"
    },
    "小狗": {
        "max_hunger": 120,
        "max_energy": 90,
        "max_happiness": 110,
        "growth_rate": 1.3,
        "rarity": "普通"
    },
    "魔法兔": {
        "max_hunger": 80,
        "max_energy": 120,
        "max_happiness": 150,
        "growth_rate": 1.5,
        "rarity": "稀有"
    },
    "蠢萝莉": {
        "max_hunger": 150,
        "max_energy": 150,
        "max_happiness": 80,
        "growth_rate": 1.8,
        "rarity": "史诗"
    },
    "小狐狸": {
        "max_hunger": 60,
        "max_energy": 200,
        "max_happiness": 100,
        "growth_rate": 1.6,
        "rarity": "稀有"
    },
    "熊猫宝宝": {
        "max_hunger": 200,
        "max_energy": 100,
        "max_happiness": 200,
        "growth_rate": 2.0,
        "rarity": "传说"
    }
}

# 宠物商店物品
PET_SHOP_ITEMS = {
    "普通食物": {
        "price": 5,
        "hunger": 20,
        "energy": 5,
        "happiness": 5,
        "effect": "恢复宠物饱食度"
    },
    "高级料理": {
        "price": 10,
        "hunger": 50,
        "energy": 15,
        "happiness": 15,
        "effect": "大幅恢复宠物状态"
    },
    "玩具球": {
        "price": 10,
        "hunger": -5,
        "energy": -10,
        "happiness": 30,
        "effect": "增加宠物快乐度"
    },
    "能量饮料": {
        "price": 15,
        "hunger": 10,
        "energy": 50,
        "happiness": 10,
        "effect": "快速恢复宠物精力"
    },
    "成长药剂": {
        "price": 30,
        "hunger": 0,
        "energy": 0,
        "happiness": 0,
        "effect": "加速宠物成长",
        "special": "growth"
    },
    "变异药剂": {
        "price": 50,
        "hunger": 0,
        "energy": 0,
        "happiness": 0,
        "effect": "有几率使宠物变异",
        "special": "mutate"
    },
    "宠物扭蛋": {
        "price": 10,
        "effect": "随机获得一只宠物",
        "type": "gacha"
    }
}

# 宠物状态描述
STATUS_DESCRIPTIONS = {
    "hunger": {
        80: "吃得饱饱的",
        50: "有点饿了",
        30: "非常饥饿",
        0: "饿得不行了"
    },
    "energy": {
        80: "精力充沛",
        50: "有点累了",
        30: "非常疲惫",
        0: "精疲力尽"
    },
    "happiness": {
        80: "非常开心",
        50: "心情一般",
        30: "不太高兴",
        0: "非常沮丧"
    }
}

# 宠物进化路线
EVOLUTIONS = {
    "小猫咪": ["大猫咪", "猫娘", "猫耳女仆"],
    "小狗": ["大狗", "犬娘", "神圣狼女"],
    "魔法兔": ["月兔", "玉兔", "月宫仙子"],
    "蠢萝莉": ["贪财萝莉", "嘴馋萝莉", "小萝莉"],
    "小狐狸": ["藏狐", "小狐娘", "九尾狐娘"],
    "熊猫宝宝": ["大熊猫", "熊猫娘", "黑白圣女"]
}

# 初始化数据目录
os.makedirs(PET_DATA_DIR, exist_ok=True)

# --- 辅助函数 ---
async def load_json_data(filename, default_data, lock):
    """异步安全地加载JSON数据"""
    async with lock:
        if not os.path.exists(filename):
            return default_data
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default_data

async def save_json_data(filename, data, lock):
    """异步安全地保存JSON数据"""
    async with lock:
        try:
            temp_filename = filename + ".tmp"
            with open(temp_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            os.replace(temp_filename, filename)
        except IOError as e:
            print(f"Error saving JSON data to {filename}: {e}")

async def get_pet_data():
    """获取宠物基础数据"""
    return await load_json_data(PET_DATABASE, BASE_PETS, pet_data_lock)

async def get_user_pets():
    """获取所有用户的宠物数据"""
    return await load_json_data(USER_PET_DATABASE, {}, user_pet_lock)

async def save_user_pets(data):
    """保存所有用户的宠物数据"""
    await save_json_data(USER_PET_DATABASE, data, user_pet_lock)

async def get_user_items():
    """获取所有用户的物品数据"""
    return await load_json_data(USER_ITEMS_DATABASE, {}, user_items_lock)

async def save_user_items(data):
    """保存所有用户的物品数据"""
    await save_json_data(USER_ITEMS_DATABASE, data, user_items_lock)

async def get_user_pet(user_id):
    """获取单个用户的宠物"""
    user_pets = await get_user_pets()
    return user_pets.get(str(user_id), None)

async def update_user_pet(user_id, pet_data):
    """更新用户的宠物数据"""
    user_pets = await get_user_pets()
    user_pets[str(user_id)] = pet_data
    await save_user_pets(user_pets)

async def remove_user_pet(user_id):
    """移除用户的宠物"""
    user_pets = await get_user_pets()
    if str(user_id) in user_pets:
        del user_pets[str(user_id)]
        await save_user_pets(user_pets)
        return True
    return False

async def get_user_item_count(user_id, item_name):
    """获取用户拥有的特定物品数量"""
    user_items = await get_user_items()
    return user_items.get(str(user_id), {}).get(item_name, 0)

async def add_user_item(user_id, item_name, quantity=1):
    """给用户添加物品"""
    user_items = await get_user_items()
    if str(user_id) not in user_items:
        user_items[str(user_id)] = {}
    user_items[str(user_id)][item_name] = user_items[str(user_id)].get(item_name, 0) + quantity
    await save_user_items(user_items)

async def use_user_item(user_id, item_name, quantity=1):
    """使用用户物品"""
    user_items = await get_user_items()
    if str(user_id) not in user_items or user_items[str(user_id)].get(item_name, 0) < quantity:
        return False
    user_items[str(user_id)][item_name] -= quantity
    if user_items[str(user_id)][item_name] <= 0:
        del user_items[str(user_id)][item_name]
    await save_user_items(user_items)
    return True

async def get_status_description(stat_name, value):
    """获取状态描述"""
    thresholds = sorted(STATUS_DESCRIPTIONS[stat_name].keys(), reverse=True)
    for threshold in thresholds:
        if value >= threshold:
            return STATUS_DESCRIPTIONS[stat_name][threshold]
    return "状态异常"

async def update_pet_status(pet):
    """更新宠物状态"""
    current_time = time.time()
    last_update = pet.get("last_update", current_time)
    time_passed = current_time - last_update
    
    # 随时间减少状态值
    pet["hunger"] = max(0, pet["hunger"] - time_passed / 3600 * 5)  # 每小时减少5点
    pet["energy"] = max(0, pet["energy"] - time_passed / 3600 * 3)  # 每小时减少3点
    pet["happiness"] = max(0, pet["happiness"] - time_passed / 3600 * 2)  # 每小时减少2点
    
    # 更新成长值
    growth_rate = pet.get("growth_rate", 1.0)
    pet["growth"] = min(100, pet.get("growth", 0) + time_passed / 3600 * growth_rate)
    
    pet["last_update"] = current_time
    return pet

async def check_pet_evolution(pet):
    """检查宠物是否可以进化"""
    if pet["growth"] >= 100 and pet["type"] in EVOLUTIONS:
        evolutions = EVOLUTIONS[pet["type"]]
        current_stage = pet.get("stage", 0)
        if current_stage < len(evolutions) - 1:
            return evolutions[current_stage + 1]
    return None

# --- 扭蛋系统 ---
@sv.on_prefix(('购买扭蛋', '买扭蛋'))
async def buy_gacha(bot, ev: CQEvent):
    user_id = ev.user_id
    args = ev.message.extract_plain_text().strip().split()
    
    try:
        quantity = int(args[0]) if args else 1
        if quantity <= 0:
            await bot.send(ev, "购买数量必须是正整数！", at_sender=True)
            return
    except ValueError:
        await bot.send(ev, "购买数量必须是有效的数字！", at_sender=True)
        return

    total_cost = quantity * GACHA_COST
    user_stones = money.get_user_money(user_id, 'kirastone')

    if user_stones < total_cost:
        await bot.send(ev, f"宝石不足！购买{quantity}个扭蛋需要{total_cost}宝石，你只有{user_stones}宝石。", at_sender=True)
        return

    # 扣除宝石并添加扭蛋
    if money.reduce_user_money(user_id, 'kirastone', total_cost):
        await add_user_item(user_id, "宠物扭蛋", quantity)
        await bot.send(ev, f"成功购买了{quantity}个宠物扭蛋！使用'开启扭蛋'来试试手气吧！", at_sender=True)
    else:
        await bot.send(ev, "购买失败，请稍后再试！", at_sender=True)

@sv.on_fullmatch(('我的扭蛋', '查看扭蛋'))
async def show_gacha(bot, ev: CQEvent):
    user_id = ev.user_id
    gacha_count = await get_user_item_count(user_id, "宠物扭蛋")
    await bot.send(ev, f"你目前拥有{gacha_count}个宠物扭蛋。使用'开启扭蛋'来试试手气吧！", at_sender=True)

@sv.on_fullmatch('开启扭蛋')
async def open_gacha(bot, ev: CQEvent):
    user_id = ev.user_id
    
    # 检查是否已有宠物
    if await get_user_pet(user_id):
        await bot.send(ev, "你已经有宠物了，无法开启新扭蛋！", at_sender=True)
        return
    
    # 检查是否有扭蛋
    if not await use_user_item(user_id, "宠物扭蛋"):
        await bot.send(ev, "你没有宠物扭蛋！使用'购买扭蛋'来获取。", at_sender=True)
        return
    
    # 扭蛋结果
    anwei = random.random() * 100
    if anwei < 60:
        money.increase_user_money(user_id, 'gold', GACHA_CONSOLE_PRIZE)
        await bot.send(ev, f"很遗憾，这次没有抽中宠物。你获得了{GACHA_CONSOLE_PRIZE}金币作为安慰奖！", at_sender=True)
        return
    roll = random.random() * 100
    pet_type = None
    
    if roll < 70:  # 70%普通
        pool = GACHA_REWARDS["普通"]
    elif roll < 95:  # 25%稀有
        pool = GACHA_REWARDS["稀有"]
    else:  # 5%史诗
        pool = GACHA_REWARDS["史诗"]
    
    # 从选择的池中随机宠物
    pet_type = random.choices(list(pool.keys()), weights=list(pool.values()))[0]
    
    if pet_type:
        # 保存临时宠物数据，等待用户确认
        temp_pet = {
            "type": pet_type,
            "temp_data": True,
            "gacha_time": time.time()
        }
        await update_user_pet(user_id, temp_pet)
        
        pet_data = await get_pet_data()
        rarity = pet_data[pet_type]["rarity"]
        await bot.send(ev, f"恭喜！你抽中了{rarity}宠物【{pet_type}】！\n"
                          f"请在5分钟内使用'领养宠物 [名字]'来领养它，或使用'放弃宠物'放弃。\n否则你将无法开启新扭蛋。", at_sender=True)
    else:
        # 安慰奖
        money.increase_user_money(user_id, 'gold', GACHA_CONSOLE_PRIZE)
        await bot.send(ev, f"很遗憾，这次没有抽中宠物。你获得了{GACHA_CONSOLE_PRIZE}金币作为安慰奖！", at_sender=True)

@sv.on_prefix(('领养宠物', '确认领养'))
async def confirm_adopt(bot, ev: CQEvent):
    user_id = ev.user_id
    pet_name = ev.message.extract_plain_text().strip()
    
    if not pet_name:
        await bot.send(ev, "请为你的宠物取个名字！\n例如：领养宠物 小白", at_sender=True)
        return
    
    if len(pet_name) > 10:
        await bot.send(ev, "宠物名字太长了，最多10个字符！", at_sender=True)
        return
    
    # 检查临时宠物数据
    temp_pet = await get_user_pet(user_id)
    if not temp_pet or not temp_pet.get("temp_data"):
        await bot.send(ev, "你没有待领养的宠物！", at_sender=True)
        return
    
    # 检查是否超时
    if time.time() - temp_pet.get("gacha_time", 0) > 300:
        await remove_user_pet(user_id)
        await bot.send(ev, "领养时间已过期！", at_sender=True)
        return
    
    # 检查名字是否已存在
    user_pets = await get_user_pets()
    for uid, pet in user_pets.items():
        if pet.get("name") == pet_name and uid != str(user_id):
            await bot.send(ev, f"名字'{pet_name}'已经被其他宠物使用了，请换一个名字！", at_sender=True)
            return
    
    # 创建正式宠物
    pet_type = temp_pet["type"]
    pet_data = await get_pet_data()
    base_pet = pet_data[pet_type]
    
    new_pet = {
        "type": pet_type,
        "name": pet_name,
        "hunger": base_pet["max_hunger"],
        "energy": base_pet["max_energy"],
        "happiness": base_pet["max_happiness"],
        "max_hunger": base_pet["max_hunger"],
        "max_energy": base_pet["max_energy"],
        "max_happiness": base_pet["max_happiness"],
        "growth": 0,
        "growth_rate": base_pet["growth_rate"],
        "stage": 0,
        "skills": [],
        "last_update": time.time(),
        "adopted_time": time.time()
    }
    
    await update_user_pet(user_id, new_pet)
    await bot.send(ev, f"恭喜！你成功领养了一只{pet_name}({pet_type})！", at_sender=True)

@sv.on_fullmatch(('放弃宠物', '丢弃扭蛋宠物'))
async def cancel_adopt(bot, ev: CQEvent):
    user_id = ev.user_id
    temp_pet = await get_user_pet(user_id)
    
    if not temp_pet or not temp_pet.get("temp_data"):
        await bot.send(ev, "你没有待领养的宠物！", at_sender=True)
        return
    
    await remove_user_pet(user_id)
    await bot.send(ev, "你放弃了这次扭蛋获得的宠物。", at_sender=True)

# --- 宠物用品系统 ---
@sv.on_prefix(('宠物商店', '购买'))
async def buy_pet_item(bot, ev: CQEvent):
    user_id = ev.user_id
    args = ev.message.extract_plain_text().strip().split()
    
    if not args:
        # 显示商店列表
        item_list = []
        for name, info in PET_SHOP_ITEMS.items():
            price = info["price"]
            effect = info.get("effect", "")
            item_list.append(f"{name} - {price}宝石 ({effect})")
        
        await bot.send(ev, "可购买的宠物用品:\n" + "\n".join(item_list) + 
                      "\n使用'购买宠物用品 [名称] [数量]'来购买", at_sender=True)
        return
    
    item_name = args[0]
    try:
        quantity = int(args[1]) if len(args) > 1 else 1
        if quantity <= 0:
            await bot.send(ev, "购买数量必须是正整数！", at_sender=True)
            return
    except ValueError:
        await bot.send(ev, "购买数量必须是有效的数字！", at_sender=True)
        return
    
    if item_name not in PET_SHOP_ITEMS:
        await bot.send(ev, f"没有名为'{item_name}'的宠物用品！", at_sender=True)
        return
    
    price = PET_SHOP_ITEMS[item_name]["price"] * quantity
    user_stones = money.get_user_money(user_id, 'kirastone')
    
    if user_stones < price:
        await bot.send(ev, f"宝石不足！购买{quantity}个{item_name}需要{price}宝石，你只有{user_stones}宝石。", at_sender=True)
        return
    
    # 扣钱并添加物品
    if money.reduce_user_money(user_id, 'kirastone', price):
        await add_user_item(user_id, item_name, quantity)
        await bot.send(ev, f"成功购买了{quantity}个{item_name}！", at_sender=True)
    else:
        await bot.send(ev, "购买失败，请稍后再试！", at_sender=True)

@sv.on_prefix(('宠物背包', '查看宠物用品'))
async def show_pet_items(bot, ev: CQEvent):
    user_id = ev.user_id
    user_items = (await get_user_items()).get(str(user_id), {})
    
    if not user_items:
        await bot.send(ev, "你目前没有宠物用品。使用'购买宠物用品'来获取。", at_sender=True)
        return
    
    item_list = [f"{name} ×{count}" for name, count in user_items.items()]
    await bot.send(ev, "你拥有的宠物用品:\n" + "\n".join(item_list) + 
                  "\n使用'使用宠物用品 [名称]'来使用", at_sender=True)

@sv.on_prefix(('使用宠物用品', '使用'))
async def use_pet_item(bot, ev: CQEvent):
    user_id = ev.user_id
    item_name = ev.message.extract_plain_text().strip()
    
    if not item_name:
        await bot.send(ev, "请指定要使用的物品名称！", at_sender=True)
        return
    
    # 检查是否拥有该物品
    if not await use_user_item(user_id, item_name):
        await bot.send(ev, f"你没有{item_name}或者数量不足！", at_sender=True)
        return
    
    # 检查是否是扭蛋
    if item_name == "宠物扭蛋":
        await bot.send(ev, "请直接使用'开启扭蛋'命令来使用扭蛋。", at_sender=True)
        await add_user_item(user_id, item_name)  # 退回物品
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, item_name)  # 退回物品
        return
    
    pet = await update_pet_status(pet)
    
    # 应用物品效果
    if item_name not in PET_SHOP_ITEMS:
        await bot.send(ev, f"无效的物品名称: {item_name}", at_sender=True)
        await add_user_item(user_id, item_name)  # 退回物品
        return
    
    item = PET_SHOP_ITEMS[item_name]
    pet["hunger"] = min(pet["max_hunger"], pet["hunger"] + item.get("hunger", 0))
    pet["energy"] = min(pet["max_energy"], pet["energy"] + item.get("energy", 0))
    pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + item.get("happiness", 0))
    
    # 特殊效果处理
    special_msg = ""
    if "special" in item:
        if item["special"] == "growth":
            pet["growth_rate"] *= 1.2
            pet["growth_rate"] = min(pet["growth_rate"], 3.0)  # 最大3倍成长速度
            special_msg = "成长速度提高了！"
        elif item["special"] == "mutate" and random.random() < 0.1:  # 10%变异几率
            pet["type"] = "变异" + pet["type"]
            pet["max_hunger"] *= 1.5
            pet["max_energy"] *= 1.5
            pet["max_happiness"] *= 1.5
            special_msg = "宠物发生了变异！"
    
    await update_user_pet(user_id, pet)
    
    effect_msg = []
    if item.get("hunger", 0) != 0:
        effect_msg.append(f"饱食度: {item['hunger']:+}")
    if item.get("energy", 0) != 0:
        effect_msg.append(f"精力: {item['energy']:+}")
    if item.get("happiness", 0) != 0:
        effect_msg.append(f"快乐度: {item['happiness']:+}")
    
    await bot.send(ev, f"你对{pet['name']}使用了{item_name}！\n" +
                  ("\n".join(effect_msg) if effect_msg else "") +
                  (f"\n{special_msg}" if special_msg else ""), at_sender=True)

@sv.on_prefix(('玩耍', '陪玩宠物'))
async def play_with_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    pet = await update_pet_status(pet)
    
    # 检查宠物精力
    if pet["energy"] < 20:
        await bot.send(ev, f"{pet['name']}太累了，需要休息！", at_sender=True)
        return
    
    # 玩耍效果
    pet["energy"] = max(0, pet["energy"] - 15)
    pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + 25)
    pet["growth"] = min(100, pet["growth"] + 1)
    
    # 随机获得技能
    if random.random() < 0.2 and len(pet["skills"]) < 5:  # 20%几率获得新技能
        skills = ["卖萌", "握手", "翻滚", "装死", "跳舞", "唱歌", "杂技", "寻宝"]
        new_skill = random.choice([s for s in skills if s not in pet["skills"]])
        pet["skills"].append(new_skill)
        skill_msg = f"并学会了新技能'{new_skill}'！"
    else:
        skill_msg = ""
    
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"你和{pet['name']}玩得很开心！{skill_msg}", at_sender=True)

@sv.on_prefix(('休息', '宠物休息'))
async def rest_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    pet = await update_pet_status(pet)
    
    # 休息效果
    pet["energy"] = min(pet["max_energy"], pet["energy"] + 40)
    pet["happiness"] = max(0, pet["happiness"] - 5)  # 休息会减少一点快乐度
    
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"{pet['name']}正在休息，精力恢复了！", at_sender=True)


@sv.on_prefix(('改名', '宠物改名'))
async def rename_pet(bot, ev):
    user_id = ev.user_id
    new_name = ev.message.extract_plain_text().strip()
    if not new_name:
        await bot.send(ev, "请提供新的宠物名字！\n例如 宠物改名 [新名字]", at_sender=True)
        return
    
    if len(new_name) > 10:
        await bot.send(ev, "宠物名字太长了，最多10个字符！", at_sender=True)
        return
    
    # 检查名字是否已存在
    user_pets = await get_user_pets()
    for uid, pet in user_pets.items():
        if pet["name"] == new_name and uid != str(user_id):
            await bot.send(ev, f"名字'{new_name}'已经被其他宠物使用了，请换一个名字！", at_sender=True)
            return
    
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    old_name = pet["name"]
    pet["name"] = new_name
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"成功将'{old_name}'改名为'{new_name}'！", at_sender=True)

@sv.on_prefix(('进化宠物', '宠物进化'))
async def evolve_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    pet = await update_pet_status(pet)
    evolution = await check_pet_evolution(pet)
    
    if not evolution:
        await bot.send(ev, f"{pet['name']}还不能进化或已经达到最终形态！", at_sender=True)
        return
    
    # 进化需要100金币
    cost = 100
    user_gold = money.get_user_money(user_id, 'gold')
    
    if user_gold < cost:
        await bot.send(ev, f"进化需要{cost}金币，你只有{user_gold}金币。", at_sender=True)
        return
    
    # 执行进化
    old_type = pet["type"]
    pet["type"] = evolution
    pet["stage"] += 1
    pet["growth"] = 0  # 重置成长度
    pet["max_hunger"] *= 1.2
    pet["max_energy"] *= 1.2
    pet["max_happiness"] *= 1.2
    
    if money.reduce_user_money(user_id, 'gold', cost):
        await update_user_pet(user_id, pet)
        await bot.send(ev, f"恭喜！{old_type}进化为{evolution}！", at_sender=True)
    else:
        await bot.send(ev, "进化失败，请稍后再试！", at_sender=True)
        
        
@sv.on_prefix(('我的宠物', '查看宠物'))
async def show_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    
    if not pet:
        await bot.send(ev, "你还没有宠物，使用'领养宠物'来领养一只吧！", at_sender=True)
        return
    
    # 更新宠物状态
    pet = await update_pet_status(pet)
    await update_user_pet(user_id, pet)
    
    # 检查进化
    evolution = await check_pet_evolution(pet)
    if evolution:
        await bot.send(ev, f"你的宠物可以进化为{evolution}了！使用'进化宠物'来让它进化。", at_sender=True)
    
    # 显示宠物状态
    hunger_desc = await get_status_description("hunger", pet["hunger"])
    energy_desc = await get_status_description("energy", pet["energy"])
    happiness_desc = await get_status_description("happiness", pet["happiness"])
    
    adopted_date = datetime.fromtimestamp(pet["adopted_time"]).strftime('%Y-%m-%d')
    
    message = [
        f"宠物名称：{pet['name']}\n 种族：{pet['type']}",
        f"领养日期: {adopted_date}",
        f"成长度: {pet['growth']:.1f}/100",
        f"饱食度: {pet['hunger']:.1f}/{pet['max_hunger']} ({hunger_desc})",
        f"精力: {pet['energy']:.1f}/{pet['max_energy']} ({energy_desc})",
        f"快乐度: {pet['happiness']:.1f}/{pet['max_happiness']} ({happiness_desc})",
        f"技能: {', '.join(pet['skills']) if pet['skills'] else '暂无'}",
        "投喂食物、或使用'玩耍'或'休息'来照顾她吧~"
    ]
    
    await bot.send(ev, "\n".join(message), at_sender=True)

@sv.on_prefix(('放生宠物', '丢弃宠物'))
async def release_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    # 确认操作
    confirm = ev.message.extract_plain_text().strip().lower()
    if confirm != "确认":
        await bot.send(ev, f"确定要放生{pet['name']}吗？这将永久失去它！\n使用'放生宠物 确认'来确认操作", at_sender=True)
        return
    
    # 根据宠物成长度返还部分金币
    #base_price = (await get_pet_data()).get(pet["type"], {}).get("price", 0)
    #refund = int(base_price * (pet["growth"] / 100) * 0.5  # 返还50%价值
    
    await remove_user_pet(user_id)
    await bot.send(ev, f"你放生了{pet['name']}。", at_sender=True)


# 帮助信息
pet_help = """
宠物养成系统帮助：

【扭蛋系统】
1. 购买扭蛋 [数量] - 购买宠物扭蛋(10宝石/个)
2. 开启扭蛋 - 开启一个扭蛋(可能获得宠物或安慰奖)
3. 领养宠物 [名字] - 领养扭蛋获得的宠物
4. 放弃宠物 - 放弃扭蛋获得的宠物

【宠物用品】
1. 宠物商店 - 查看可购买的宠物用品
2. 购买 [名称] [数量] - 购买指定宠物用品
3. 宠物背包 - 查看拥有的宠物用品
4. 使用 [名称] - 对宠物使用物品

【宠物管理】
1. 我的宠物 - 查看宠物状态
2. 陪玩宠物 - 与宠物玩耍
3. 宠物休息 - 让宠物休息
4. 宠物改名 [新名字] - 为宠物改名
5. 进化宠物 - 进化符合条件的宠物
6. 放生宠物 确认 - 放生当前宠物

【其他】
1. 买宝石 [数量] - 购买宝石
2. 宠物帮助 - 显示本帮助
"""

@sv.on_fullmatch(('宠物帮助', '宠物养成帮助'))
async def pet_help_command(bot, ev):
    chain = []
    await chain_reply(bot, ev, chain, pet_help)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)
