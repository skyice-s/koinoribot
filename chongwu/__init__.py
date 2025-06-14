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
from .. import money, config
from .petconfig import GACHA_COST, GACHA_REWARDS, GACHA_CONSOLE_PRIZE, BASE_PETS, EVOLUTIONS, growth1, growth2, growth3, PET_SHOP_ITEMS, STATUS_DESCRIPTIONS, PET_SKILLS
from .pet import get_pet_data, get_user_pets, save_user_pets, get_user_items, save_user_items, get_user_pet, update_user_pet, remove_user_pet, get_user_item_count 
from .pet import add_user_item, use_user_item, get_status_description, update_pet_status, check_pet_evolution
from hoshino.config import SUPERUSERS

no = get('emotion/no.png').cqcode
ok = get('emotion/ok.png').cqcode
sv = Service('pet_raising', manage_priv=priv.ADMIN, enable_on_default=True)






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
        await bot.send(ev, f"宝石不足！购买{quantity}个扭蛋需要{total_cost}宝石，你只有{user_stones}宝石。\n 使用[买宝石 数量]来购买一些宝石吧~", at_sender=True)
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

@sv.on_fullmatch('开启扭蛋', '开扭蛋')
async def open_gacha(bot, ev: CQEvent):
    user_id = ev.user_id
    
    # 检查是否有扭蛋
    if not await use_user_item(user_id, "宠物扭蛋"):
        await bot.send(ev, "你没有宠物扭蛋！使用'购买扭蛋'来获取。", at_sender=True)
        return
    
    # 获取用户宠物数据
    pet_data = await get_user_pet(user_id)
    
    # 检查是否有宠物且是否正式领养
    if pet_data:
        # 检查是否有temp_data字段来判断是否未正式领养
        if "temp_data" in pet_data:
            pet_type = pet_data["type"]
            # 返还扭蛋
            await add_user_item(user_id, "宠物扭蛋")
            await bot.send(ev, f"\n你已经有一只宠物({pet_type})等待领养了，请先领养或放弃她。" +no, at_sender=True)
            return
        else:
            # 已有正式领养的宠物，按照原逻辑处理
            anwei = random.random() * 100
            if anwei < 50:
                money.increase_user_money(user_id, 'gold', GACHA_CONSOLE_PRIZE)
                await bot.send(ev, f"\n你已经有宠物了，本次扭蛋里没有宠物，你获得了{GACHA_CONSOLE_PRIZE}金币作为安慰奖...", at_sender=True)
                return
            else:
                money.increase_user_money(user_id, 'luckygold', 1)
                await bot.send(ev, f"\n你已经有宠物了，本次扭蛋里没有宠物，但是有1枚幸运币...", at_sender=True)
                return
    else:
        # 没有宠物的情况
        anwei = random.random() * 100
        if anwei < 25:
            money.increase_user_money(user_id, 'gold', GACHA_CONSOLE_PRIZE)
            await bot.send(ev, f"\n扭蛋里没有宠物，你获得了{GACHA_CONSOLE_PRIZE}金币作为安慰奖...", at_sender=True)
            return
        elif anwei < 50:
            money.increase_user_money(user_id, 'luckygold', 1)
            await bot.send(ev, f"\n扭蛋里没有宠物，但是有1枚幸运币...", at_sender=True)
            return
    
    roll = random.random() * 100
    pet_type = None
    
    if roll < 55:  # 普通
        pool = GACHA_REWARDS["普通"]
    elif roll < 80:  # 稀有
        pool = GACHA_REWARDS["稀有"]
    elif roll < 98:  # 史诗
        pool = GACHA_REWARDS["史诗"]
    else:  # 传说
        pool = GACHA_REWARDS["传说"]
    
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
        await bot.send(ev, f"\n恭喜！你抽中了{rarity}宠物【{pet_type}】！\n"
                          f"请使用'领养宠物 [名字]'来领养它，或使用'放弃宠物'放弃。\n否则你将无法开启新扭蛋。", at_sender=True)
    else:
        # 安慰奖
        money.increase_user_money(user_id, 'gold', GACHA_CONSOLE_PRIZE)
        await bot.send(ev, f"很遗憾，这次没有抽中宠物。你获得了{GACHA_CONSOLE_PRIZE}金币作为安慰奖！", at_sender=True)

@sv.on_prefix('领养宠物')
async def confirm_adopt(bot, ev: CQEvent):
    user_id = ev.user_id
    pet_name = ev.message.extract_plain_text().strip()
    
    if not pet_name:
        await bot.send(ev, "\n请为你的宠物取个名字！\n例如：领养宠物 小白", at_sender=True)
        return
    
    if len(pet_name) > 10:
        await bot.send(ev, "\n宠物名字太长了，最多10个字符！", at_sender=True)
        return
    
    # 检查临时宠物数据
    temp_pet = await get_user_pet(user_id)
    if not temp_pet or not temp_pet.get("temp_data"):
        await bot.send(ev, "\n你没有待领养的宠物,不妨试试开扭蛋获取一个吧？", at_sender=True)
        return
    
    # 检查名字是否已存在
    user_pets = await get_user_pets()
    for uid, pet in user_pets.items():
        if pet.get("name") == pet_name and uid != str(user_id):
            await bot.send(ev, f"\n名字'{pet_name}'已经被其他宠物使用了，请换一个名字！", at_sender=True)
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
        "stage": 0,  # 幼年体
        "growth_required": growth1,  # 进化到成长体需要的成长值
        "last_event_date": None,  # 添加这个字段，初始为None
        "skills": [],
        "runaway" : False,
        "last_update": time.time(),
        "adopted_time": time.time()
    }
    
    await update_user_pet(user_id, new_pet)
    await bot.send(ev, f"恭喜！你成功领养了一只{pet_name}({pet_type})！", at_sender=True)

@sv.on_fullmatch(('放弃宠物', '丢弃扭蛋宠物'))
async def cancel_adopt(bot, ev: CQEvent):
    user_id = ev.user_id
    temp_pet = await get_user_pet(user_id)
    pet_type = temp_pet["type"]
    if not temp_pet or not temp_pet.get("temp_data"):
        await bot.send(ev, "你没有待领养的宠物！", at_sender=True)
        return
    
    await remove_user_pet(user_id)
    await bot.send(ev, f"你放弃了一只{pet_type}。", at_sender=True)

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
                      "\n使用'购买 [名称] [数量]'来购买", at_sender=True)
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
                  "\n请发送‘宠物帮助’来查看具体的使用方法", at_sender=True)

# 投喂宠物指令
@sv.on_prefix(('投喂', '喂食宠物', '投喂宠物'))
async def feed_pet(bot, ev: CQEvent):
    user_id = ev.user_id
    food_type = ev.message.extract_plain_text().strip()
    
    # 检查食物类型是否有效
    valid_foods = {
        "普通料理": "普通料理",
        "高级料理": "高级料理", 
        "豪华料理": "豪华料理"
    }
    
    if food_type not in valid_foods:
        await bot.send(ev, "\n请指定正确的食物类型：普通/高级/豪华料理\n例如：投喂 高级料理\n使用能量饮料请发送'补充精力'\n进化宠物请发送'宠物进化'", at_sender=True)
        return
    
    item_name = valid_foods[food_type]
    
    # 检查是否拥有该物品
    if not await use_user_item(user_id, item_name):
        await bot.send(ev, f"你没有{item_name}！", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, item_name)  # 退回物品
        return
    
    pet = await update_pet_status(pet)
    if pet["runaway"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】离家出走了，无法投喂！", at_sender=True)
        await add_user_item(user_id, item_name)
        return
    
    # 应用食物效果
    item = PET_SHOP_ITEMS[item_name]
    pet["hunger"] = min(pet["max_hunger"], pet["hunger"] + item["hunger"])
    pet["energy"] = min(pet["max_energy"], pet["energy"] + item["energy"])
    pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + item["happiness"])
    pet["growth"] = min(pet["growth_required"], pet["growth"] + item["growth"])
    await update_user_pet(user_id, pet)
    
    effect_msg = [
        f"饱食度: +{item['hunger']}",
        f"精力: +{item['energy']}",
        f"好感度: +{item['happiness']}",
        f"成长值: +{item['growth']}"
    ]
    
    await bot.send(ev, f"\n你给{pet['name']}投喂了{item_name}！\n" + "\n".join(effect_msg), at_sender=True)

# 使用玩具球指令
@sv.on_fullmatch('丢玩具球')
async def play_with_ball(bot, ev):
    user_id = ev.user_id
    
    # 检查是否拥有玩具球
    if not await use_user_item(user_id, "玩具球"):
        await bot.send(ev, "你没有玩具球！", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, "玩具球")
        return
    
    pet = await update_pet_status(pet)
    if pet["runaway"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】离家出走了，无法玩耍！", at_sender=True)
        await add_user_item(user_id, "玩具球")
        return
    
    # 检查宠物精力
    if pet["energy"] < 20:
        await bot.send(ev, f"{pet['name']}太累了，需要休息！", at_sender=True)
        await add_user_item(user_id, "玩具球")
        return
    
    # 应用玩具球效果
    item = PET_SHOP_ITEMS["玩具球"]
    pet["hunger"] = max(0, pet["hunger"] + item["hunger"])
    pet["energy"] = max(0, pet["energy"] + item["energy"])
    pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + item["happiness"])
    
    await update_user_pet(user_id, pet)
    
    await bot.send(ev, f"\n你和{pet['name']}一起玩玩具球，它看起来很开心！\n饱食度{item['hunger']}\n精力{item['energy']}\n好感度+{item['happiness']}", at_sender=True)

# 使用能量饮料指令
@sv.on_fullmatch(('恢复精力', '补充精力'))
async def give_energy_drink(bot, ev):
    user_id = ev.user_id
    
    # 检查是否拥有能量饮料
    if not await use_user_item(user_id, "能量饮料"):
        await bot.send(ev, "你没有能量饮料！", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, "能量饮料")
        return
    
    pet = await update_pet_status(pet)
    if pet["runaway"]:
        await bot.send(ev, f"\n你的宠物【{pet['name']}】离家出走了，无法使用！", at_sender=True)
        await add_user_item(user_id, "能量饮料")
        return
    
    # 应用能量饮料效果
    item = PET_SHOP_ITEMS["能量饮料"]
    pet["energy"] = min(pet["max_energy"], pet["energy"] + item["energy"])
    pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + item["happiness"])
    
    await update_user_pet(user_id, pet)
    
    await bot.send(ev, f"\n你给{pet['name']}喝了能量饮料，它立刻精神焕发！\n精力+{item['energy']}\n好感度+{item['happiness']}", at_sender=True)

# 寻回宠物指令
@sv.on_fullmatch(('寻回宠物', '找回宠物'))
async def retrieve_pet(bot, ev):
    user_id = ev.user_id
    
    # 检查是否拥有最初的契约
    if not await use_user_item(user_id, "最初的契约"):
        await bot.send(ev, "你没有最初的契约！", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, "最初的契约")
        return
    
    if not pet["runaway"]:
        await bot.send(ev, "你的宠物没有离家出走！", at_sender=True)
        await add_user_item(user_id, "最初的契约")
        return
    
    # 应用效果
    current_time = time.time()
    pet["runaway"] = False
    pet["happiness"] = pet["max_happiness"] * 0.3
    pet["hunger"] = pet["max_hunger"] * 0.3
    pet["energy"] = pet["max_energy"] * 0.3
    pet["last_update"] = current_time
    
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"\n你找回了{pet['name']}，这一次，一定要好好珍惜哦~", at_sender=True)

# 重置进化路线指令
@sv.on_fullmatch(('重置进化路线', '重新进化'))
async def reroll_evolution(bot, ev):
    user_id = ev.user_id
    
    # 检查是否拥有时之泪
    if not await use_user_item(user_id, "时之泪"):
        await bot.send(ev, "你没有时之泪！", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, "时之泪")
        return
    
    pet = await update_pet_status(pet)
    if pet["runaway"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】离家出走了，无法重置进化！", at_sender=True)
        await add_user_item(user_id, "时之泪")
        return
    
    # 检查是否是成长体
    if pet["stage"] != 1:
        await bot.send(ev, "只有成长体宠物可以重置进化路线！", at_sender=True)
        await add_user_item(user_id, "时之泪")
        return
    
    original_type = pet["type"]
    # 概率保持原分支
    if random.random() < 0.5:
        await bot.send(ev, f"{pet['name']}的进化分支没有改变。", at_sender=True)
        return
    
    # 找到原始幼年体类型
    base_type = None
    for base, evolutions in EVOLUTIONS.items():
        if isinstance(evolutions, dict):  # 幼年体的进化选项
            for evo_name, evo_type in evolutions.items():
                if evo_type == original_type:
                    base_type = base
                    break
        if base_type:
            break
    
    if not base_type:
        await bot.send(ev, "无法找到原始进化路线。", at_sender=True)
        await add_user_item(user_id, "时之泪")
        return
    
    # 随机选择新分支(排除当前分支)
    evolution_options = EVOLUTIONS[base_type]
    available_choices = [k for k in evolution_options.keys()
                        if evolution_options[k] != original_type]
    
    if not available_choices:
        await bot.send(ev, "没有可用的进化分支改变。", at_sender=True)
        await add_user_item(user_id, "时之泪")
        return
    
    evolution_choice = random.choice(available_choices)
    new_type = evolution_options[evolution_choice]
    pet["type"] = new_type

    
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"\n{pet['name']}的进化分支改变了！现在是{new_type}！", at_sender=True)
    
    
@sv.on_fullmatch('学习技能')
async def learn_skill(bot, ev):
    user_id = ev.user_id
    
    # 检查是否有技能药水
    if not await use_user_item(user_id, "技能药水"):
        await bot.send(ev, "你没有技能药水！购买需要50宝石。", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, "技能药水")  # 退回药水
        return

    # 检查是否已学会所有技能
    available_skills = [skill for skill in PET_SKILLS.keys() if skill not in pet["skills"]]
    if not available_skills:
        await bot.send(ev, f"你的宠物【{pet['name']}】已经学会了所有技能！", at_sender=True)
        return

    pet = await update_pet_status(pet)
    if pet["runaway"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】离家出走了，无法学习技能！", at_sender=True)
        await add_user_item(user_id, "技能药水")
        return
    
    # 检查技能槽是否已满
    if pet["stage"] == 0:
        max_skills = 1
    elif pet["stage"] == 1:
        max_skills = 3
    elif pet["stage"] == 2:
        max_skills = 5
    if len(pet["skills"]) >= max_skills and user_id not in SUPERUSERS:
        await bot.send(ev, f"你的宠物技能槽已满（当前阶段最多{max_skills}个技能）！", at_sender=True)
        await add_user_item(user_id, "技能药水")
        return
    
    # 概率学习成功
    if random.random() < 0.6:
        new_skill = random.choice(available_skills)
        pet["skills"].append(new_skill)
        await update_user_pet(user_id, pet)
        await bot.send(ev, f"恭喜！{pet['name']}学会了新技能【{new_skill}】！\n效果：{PET_SKILLS[new_skill]['description']}", at_sender=True)
    else:
        await bot.send(ev, "学习失败了...技能药水已经消耗。", at_sender=True)

#遗忘技能
@sv.on_prefix('遗忘', '遗忘技能')
async def forget_skill(bot, ev):
    user_id = ev.user_id
    skill_name = ev.message.extract_plain_text().strip()
    
    # 检查是否有遗忘药水
    if not await use_user_item(user_id, "遗忘药水"):
        await bot.send(ev, "你没有遗忘药水！购买需要10宝石。", at_sender=True)
        return
    
    # 检查是否有宠物
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        await add_user_item(user_id, "遗忘药水")  # 退回药水
        return
    
    pet = await update_pet_status(pet)
    if pet["runaway"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】离家出走了，无法遗忘技能！", at_sender=True)
        await add_user_item(user_id, "遗忘药水")
        return
    
    # 检查是否有该技能
    if skill_name not in pet["skills"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】没有技能【{skill_name}】！", at_sender=True)
        await add_user_item(user_id, "遗忘药水")
        return
    
    # 遗忘技能
    pet["skills"].remove(skill_name)
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"成功让【{pet['name']}】遗忘了技能【{skill_name}】！", at_sender=True)


# 宠物事件指令
# 宠物事件指令
@sv.on_fullmatch('宠物事件')
async def trigger_pet_skills(bot, ev):
    user_id = ev.user_id
    now_date = datetime.now().date()  # 获取当前日期

    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return

    # 先更新一次宠物状态，处理自然衰减等
    pet = await update_pet_status(pet)

    if pet["runaway"]:
        await bot.send(ev, f"你的宠物【{pet['name']}】离家出走了，无法触发事件！", at_sender=True)
        return

    # 初始化最后事件日期
    last_event_date = None
    
    # 从宠物数据中获取最后事件日期
    pet_last_event = pet.get("last_event_date")
    if pet_last_event:
        try:
            # 如果last_event_date是时间戳，转换为日期
            if isinstance(pet_last_event, (int, float)):
                last_event_date = datetime.fromtimestamp(pet_last_event).date()
            # 如果已经是字符串格式的日期，转换为日期对象
            elif isinstance(pet_last_event, str):
                last_event_date = datetime.strptime(pet_last_event, "%Y-%m-%d").date()
        except (TypeError, ValueError) as e:
            print(f"Error parsing last_event_date: {e}")
            # 如果日期格式有问题，当做没有执行过
            last_event_date = None

    # 检查是否已经执行过今日事件
    if last_event_date and last_event_date == now_date:
        await bot.send(ev, "今天已经触发过宠物事件了，请明天再来！", at_sender=True)
        return

    if not pet.get("skills"): # 使用 .get() 避免 skills 键不存在时出错
        await bot.send(ev, f"{pet['name']}还没有学会任何技能！", at_sender=True)
        # 更新最后执行时间为今天
        await update_user_pet(user_id, pet)
        return

    results = []
    # 在这里集中处理技能效果
    for skill_name in pet["skills"]:
        try:
            if skill_name == "宝石爱好者":
                amount = random.randint(1, 20)
                money.increase_user_money(user_id, 'kirastone', amount)
                results.append(f"\n{pet['name']}外出玩耍时偶遇无人看守的宝石矿井，偷偷捡回了{amount}枚宝石。")
            elif skill_name == "盼望长大":
                growth_gain = 10
                # Ensure growth does not exceed required for current stage
                pet['growth'] = min(pet.get('growth_required', math.inf), pet['growth'] + growth_gain)
                results.append(f"\n{pet['name']}很喜欢你，决定要努力长大来报答你，成长值+{growth_gain}。")
            elif skill_name == "金币爱好者":
                amount = random.randint(1000, 20000)
                money.increase_user_money(user_id, 'gold', amount)
                results.append(f"\n{pet['name']}外出玩耍时捡到了一个钱包，里面有{amount}金币。")
            elif skill_name == "幸运星":
                amount = random.randint(1, 3)
                money.increase_user_money(user_id, 'luckygold', amount)
                results.append(f"\n{pet['name']}外出玩耍时偶遇音祈，由于可爱的外表，深受对方喜爱，获得了上帝的祝福。幸运币+{amount}。")
            elif skill_name == "卖萌":
                amount = random.randint(100, 2000)
                money.increase_user_money(user_id, 'starstone', amount)
                results.append(f"\n{pet['name']}外出玩耍时偶遇梦灵，由于太可爱了，被大小姐rua了个爽，并收获了大量好感度（星星+{amount}）。")
            elif skill_name == "美食家":
                food_item = random.choice(["普通料理", "高级料理", "豪华料理", "能量饮料"])
                await add_user_item(user_id, food_item, 1)
                results.append(f"\n{pet['name']}外出玩耍时偶遇商店的抽奖活动，赢得了{food_item}。")
            elif skill_name == "自我管理":
                enum = random.randint(10, 80)
                hnum = random.randint(10, 80)
                pet["energy"] = min(pet["max_energy"], pet["energy"] + enum)
                pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + hnum)
                results.append(f"\n{pet['name']}已经习惯了你早出晚归的生活，她知道你赚金币养她很不容易。通过自我情绪管理，她恢复{enum}精力和{hnum}好感。")
            # 添加其他技能的处理...
            else:
                results.append(f"【{skill_name}】是未知技能，无法发动。")

        except Exception as e:
            results.append(f"【{skill_name}】发动时发生错误：{str(e)}")
            # 可以选择是否在此记录详细错误日志

    # 在所有技能执行完毕后，保存宠物状态的更改（特别是成长值）和本次事件的日期
    pet["last_event_date"] = now_date.strftime("%Y-%m-%d")  # 存储为字符串格式的日期
    await update_user_pet(user_id, pet)

    # 发送事件结果
    msg_parts = [f"{pet['name']}今天发生了以下事件："] + results
    await bot.send(ev, "\n".join(msg_parts), at_sender=True)

@sv.on_prefix(('摸摸宠物', '陪伴宠物'))
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
    pet["energy"] = max(0, pet["energy"] - 5)
    pet["happiness"] = min(pet["max_happiness"], pet["happiness"] + 15)
    await update_user_pet(user_id, pet)
    await bot.send(ev, f"\n{pet['name']}很享受你的抚摸，并用脸蛋轻轻蹭了蹭你的手...\n精力-5\n好感+15", at_sender=True)
    


@sv.on_prefix(('改名', '宠物改名'))
async def rename_pet(bot, ev):
    user_id = ev.user_id
    new_name = ev.message.extract_plain_text().strip()
    
    if not new_name:
        await bot.send(ev, "请提供新的宠物名字！\n例如 宠物改名 [新名字]", at_sender=True)
        return
    
    new_name = ' '.join(new_name.split())
    
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
    
    # 检查进化条件
    if pet["stage"] == 0 and pet["growth"] >= pet.get("growth_required", 100):
        # 幼年体 -> 成长体
        # 检查是否有奶油蛋糕
        if not await use_user_item(user_id, "奶油蛋糕"):
            await bot.send(ev, "进化需要奶油蛋糕！", at_sender=True)
            return
        if random.random() < 0.5:
            await bot.send(ev, f"\n很可惜，{pet['name']}进化失败了...", at_sender=True)
            return
        # 随机选择进化分支
        evolution_options = EVOLUTIONS[pet["type"]]
        evolution_choice = random.choice(["成长体1", "成长体2", "成长体3"])
        new_type = evolution_options[evolution_choice]
        
        pet["type"] = new_type
        pet["stage"] = 1
        pet["growth"] = 0
        pet["growth_required"] = growth2  # 进化到成年体需要500成长值
        pet["max_hunger"] *= 1.5
        pet["max_energy"] *= 1.5
        pet["max_happiness"] *= 1.5
        
        await update_user_pet(user_id, pet)
        await bot.send(ev, f"恭喜！{pet['name']}进化为{new_type}！", at_sender=True)
    
    elif pet["stage"] == 1 and pet["growth"] >= pet.get("growth_required", 200):
        # 成长体 -> 成年体
        # 检查是否有豪华蛋糕
        if not await use_user_item(user_id, "豪华蛋糕"):
            await bot.send(ev, "进化需要豪华蛋糕！", at_sender=True)
            return
        if random.random() < 0.6:
            await bot.send(ev, f"\n很可惜，{pet['name']}进化失败了...", at_sender=True)
            return
        if pet["type"] in EVOLUTIONS:
            new_type = EVOLUTIONS[pet["type"]]
            pet["type"] = new_type
            pet["stage"] = 2
            pet["growth"] = 0
            pet["growth_required"] = growth3  # 成年体不再需要成长
            pet["max_hunger"] *= 2.0
            pet["max_energy"] *= 2.0
            pet["max_happiness"] *= 2.0
            
            await update_user_pet(user_id, pet)
            await bot.send(ev, f"恭喜！{pet['name']}进化为{new_type}！", at_sender=True)
        else:
            await bot.send(ev, f"{pet['name']}没有后续进化形态！", at_sender=True)
    else:
        await bot.send(ev, f"{pet['name']}还不满足进化条件！", at_sender=True)

@sv.on_prefix(('我的宠物', '查看宠物'))
async def show_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物，使用'领养宠物'来领养一只吧！", at_sender=True)
        return
    if "temp_data" in pet:
        pet_type = pet["type"]
        await bot.send(ev, f"\n你有一只宠物({pet_type})正在等待领养。\n输入 “领养宠物 取一个名字” 来领养她。\n或者输入 放弃宠物 拒绝领养。" , at_sender=True)
        return
    
    if pet["runaway"]:
        await bot.send(ev, f"{pet['name']}已经离家出走了！使用'最初的契约'可以寻回它。", at_sender=True)
        return
    
    # 更新宠物状态
    pet = await update_pet_status(pet)
    await update_user_pet(user_id, pet)
    
    # 检查进化
    evolution = await check_pet_evolution(pet)
    if evolution == "stage1":
        await bot.send(ev, f"你的宠物可以进化为成长体了！使用'进化宠物'来让它进化。", at_sender=True)
    elif evolution == "stage2":
        await bot.send(ev, f"你的宠物可以进化为成年体了！使用'进化宠物'来让它进化。", at_sender=True)
    
    # 显示宠物状态
    hunger_desc = await get_status_description("hunger", pet["hunger"])
    energy_desc = await get_status_description("energy", pet["energy"])
    happiness_desc = await get_status_description("happiness", pet["happiness"])
    adopted_date = datetime.fromtimestamp(pet["adopted_time"]).strftime('%Y-%m-%d')
    
    stage_name = {
        0: "幼年体",
        1: "成长体",
        2: "成年体"
    }.get(pet["stage"], "未知")
    
    message = [
        f"\n宠物名称：{pet['name']}",
        f"种族：{pet['type']} ({stage_name})",
        f"领养日期: {adopted_date}",
        f"成长度: {pet['growth']:.1f}/{pet.get('growth_required', 0)}",
        f"饱食度: {pet['hunger']:.1f}/{pet['max_hunger']} ({hunger_desc})",
        f"精力: {pet['energy']:.1f}/{pet['max_energy']} ({energy_desc})",
        f"好感度: {pet['happiness']:.1f}/{pet['max_happiness']} ({happiness_desc})",
        f"技能: {', '.join(pet['skills']) if pet['skills'] else '暂无'}",
        "请好好照顾她哦，也可以发送‘宠物帮助’查看全部指令~"
    ]
    
    await bot.send(ev, "\n".join(message), at_sender=True)

@sv.on_prefix(('放生宠物', '丢弃宠物'))
async def release_pet(bot, ev):
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    if pet["runaway"]:
        await bot.send(ev, f"{pet['name']}已经离家出走了！使用'最初的契约'可以寻回它。", at_sender=True)
        return
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    # 确认操作
    confirm = ev.message.extract_plain_text().strip().lower()
    if confirm != "确认":
        await bot.send(ev, f"确定要放生{pet['name']}吗？这将永久失去它！\n使用'放生宠物 确认'来确认操作", at_sender=True)
        return
    
    await remove_user_pet(user_id)
    await bot.send(ev, f"你放生了{pet['name']}。", at_sender=True)

@sv.on_fullmatch('宠物排行榜')
async def pet_ranking(bot, ev):
    """显示成长值最高的前10只成年体宠物"""
    user_pets = await get_user_pets()
    
    # 筛选成年体宠物并按成长值排序
    adult_pets = []
    for user_id, pet in user_pets.items():
        if pet.get("stage") == 2:  # 仅成年体
            pet = await update_pet_status(pet)
            adult_pets.append((pet["growth"], pet["name"], pet["type"], user_id))
    
    if not adult_pets:
        await bot.send(ev, "目前还没有成年体宠物上榜哦！", at_sender=True)
        return
    
    # 按成长值降序排序
    adult_pets.sort(reverse=True)
    
    # 构建排行榜消息
    msg = ["\n🏆 宠物排行榜-TOP10 🏆"]
    for rank, (growth, name, pet_type, user_id) in enumerate(adult_pets[:10], 1):
        try:
            user_info = await bot.get_group_member_info(group_id=ev.group_id, user_id=int(user_id))
            nickname = user_info.get("nickname", user_id)
        except:
            nickname = user_id
        msg.append(f"第{rank}名: {name}({pet_type}) \n 成长值:{growth:.1f} ")
    
    await bot.send(ev, "\n".join(msg), at_sender=True)

@sv.on_fullmatch('宠物排名')
async def my_pet_ranking(bot, ev):
    """查看自己宠物的排名"""
    user_id = ev.user_id
    pet = await get_user_pet(user_id)
    if not pet:
        await bot.send(ev, "你还没有宠物！", at_sender=True)
        return
    
    pet = await update_pet_status(pet)
    
    if pet["stage"] != 2:  # 仅成年体可查看排名
        await bot.send(ev, "只有成年体宠物可以查看排名哦！", at_sender=True)
        return
    
    user_pets = await get_user_pets()
    
    # 筛选所有成年体宠物
    adult_pets = []
    for uid, p in user_pets.items():
        if p.get("stage") == 2:
            p = await update_pet_status(p)
            adult_pets.append((p["growth"], uid))
    
    if not adult_pets:
        await bot.send(ev, "目前还没有成年体宠物上榜哦！", at_sender=True)
        return
    
    # 按成长值排序
    adult_pets.sort(reverse=True)
    
    # 查找自己的排名
    my_growth = pet["growth"]
    rank = None
    same_growth_count = 0
    
    for i, (growth, uid) in enumerate(adult_pets):
        if uid == str(user_id):
            rank = i + 1
            break
        if growth == my_growth:
            same_growth_count += 1
    
    if rank is None:
        await bot.send(ev, "你的宠物未上榜！", at_sender=True)
    else:
        total_pets = len(adult_pets)
        await bot.send(ev, f"你的宠物【{pet['name']}】当前排名: 第{rank}名 \n成长值: {my_growth:.1f}", at_sender=True)






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
4. 投喂 [料理名称] -消耗【对应的料理】
5. 丟玩具球 - 消耗【玩具球】
6. 寻回宠物 - 消耗【最初的契约】
7. 重置进化路线 - 消耗【时之泪】
8. 进化宠物 - 消耗1个 【奶油蛋糕/豪华蛋糕】
9. 补充精力 - 消耗1个 【能量饮料】
10.学习技能 - 消耗1个 【技能药水】（具体请发送 技能帮助）
11.遗忘 [技能名称] - 消耗1个 【遗忘药水】


【宠物管理】
1. 我的宠物 - 查看宠物状态
2. 摸摸宠物 - 陪伴宠物（恢复好感）
3. 宠物改名 [新名字] - 为宠物改名
4. 放生宠物 确认 - 放生当前宠物
5. 宠物事件 - 触发宠物的所有技能
6. 技能百科 - 查看可学习的技能列表

【其他】
1. 买宝石 [数量] - 购买宝石
2. 退还宝石 [数量] - 退还宝石
3. 宠物帮助 - 显示本帮助
4. 宠物排行榜 - 查看成长值最高的成年体宠物
5. 宠物排名 - 查看自己宠物的排名

【温馨提醒】
1. 当饱食度或精力值过低时，好感度会迅速下降
2. 当好感度过低时，宠物会离家出走
3. 离家出走期间，宠物将停止长大
4. 排行榜功能需要宠物成长至完全体才能开启


"""

@sv.on_fullmatch(('宠物帮助', '宠物养成帮助'))
async def pet_help_command(bot, ev):
    chain = []
    await chain_reply(bot, ev, chain, pet_help)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)
    
pet_skill = """
幼年体/成长体/成年体可学习1/3/5个技能
可学习的技能一览：
"宝石爱好者": 捡回一些宝石
"盼望长大":  获得一些成长值
"金币爱好者": 捡回一些金币
"美食家": 捡回随机食物
"自我管理": 恢复一些精力和好感度
"卖萌": 获得一定的星星
"幸运星": 捡回一些幸运币
"""
@sv.on_fullmatch(('查看所有技能', '技能百科', '技能帮助'))
async def pet_skillhelp_command(bot, ev):
    chain = []
    await chain_reply(bot, ev, chain, pet_skill)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)