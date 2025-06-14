import math
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
from .petconfig import GACHA_COST, GACHA_REWARDS, GACHA_CONSOLE_PRIZE, BASE_PETS, EVOLUTIONS, growth1, growth2, growth3, PET_SHOP_ITEMS, STATUS_DESCRIPTIONS
from hoshino.config import SUPERUSERS

PET_DATA_DIR = os.path.join(userPath, 'chongwu')
USER_PET_DATABASE = os.path.join(PET_DATA_DIR, 'user_pets.json')
USER_ITEMS_DATABASE = os.path.join(PET_DATA_DIR, 'user_items.json')

# 锁防止并发问题
user_pet_lock = asyncio.Lock()
user_items_lock = asyncio.Lock()

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
    return BASE_PETS

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
    # 先更新时间戳，避免时间差问题
    pet["last_update"] = current_time
    
    # 如果处于离家出走状态，不更新任何状态
    if pet["runaway"]:
        return pet
    #初始化成长值上限
    if pet["stage"] == 0:
        pet["growth_required"] = growth1
    elif pet["stage"] == 1:
        pet["growth_required"] = growth2
    elif pet["stage"] == 2:
        pet["growth_required"] = growth3
    
    
    # 随时间减少状态值
    pet["hunger"] = max(0, pet["hunger"] - time_passed / 3600 * 2)  # 每小时减少2点
    pet["energy"] = max(0, pet["energy"] - time_passed / 3600 * 2)  # 每小时减少2点
    
    # 检查是否触发离家出走条件
    if (pet["hunger"] < 10 or pet["energy"] < 10) :
        pet["happiness"] = max(0, pet["happiness"] - time_passed / 3600 * 30)  # 每小时减少大量好感度

    else:
        pet["happiness"] = max(0, pet["happiness"] - time_passed / 3600 * 1)  # 正常情况每小时减少1点
        
    if pet["happiness"] < 1:
        pet["runaway"] = True  # 标记为离家出走状态

    # 更新成长值

    growth_rate = pet.get("growth_rate", 1.0)
        # 成年体依然可以获得成长值，但没有上限
    pet["growth"] = min(pet["growth_required"], pet.get("growth", 0) + time_passed / 3600 * growth_rate)
    return pet

async def check_pet_evolution(pet):
    """检查宠物是否可以进化"""
    # 幼年体 -> 成长体
    if pet["stage"] == 0 and pet["growth"] >= pet.get("growth_required", 100):
        return "stage1"
    # 成长体 -> 成年体
    elif pet["stage"] == 1 and pet["growth"] >= pet.get("growth_required", 200):
        return "stage2"
    return None
    
    