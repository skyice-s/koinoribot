import json
import asyncio
from typing import Dict, Any
from .._R import get, userPath
import os
from datetime import datetime, timedelta, date
# 复用股票插件中的文件路径和锁
PORTFOLIOS_FILE = os.path.join(userPath, 'chaogu/user_portfolios.json')  # 需要调整为实际路径
portfolio_file_lock = asyncio.Lock()
GAMBLE_LIMITS_FILE = os.path.join(userPath, 'chaogu/daily_gamble_limits.json')
MAX_GAMBLE_ROUNDS = 5

# 赌博状态管理 (内存中)
# key: user_id, value: {'round': int, 'confirmed': bool, 'active': bool}
gambling_sessions = {}

# 每日限制文件锁
gamble_limit_lock = asyncio.Lock()


async def load_json_data(filename, default_data, lock):
    """异步安全地加载JSON数据"""
    async with lock:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default_data

async def get_user_portfolio(user_id: int) -> Dict[str, int]:
    """获取单个用户的持仓数据"""
    portfolios = await load_json_data(
        PORTFOLIOS_FILE, 
        {}, 
        portfolio_file_lock
    )
    return portfolios.get(str(user_id), {})
    
    
gamble_limit_lock = asyncio.Lock()

async def load_gamble_limits():
    """加载每日赌博限制数据"""
    return await load_json_data(GAMBLE_LIMITS_FILE, {}, gamble_limit_lock)

async def save_gamble_limits(data):
    """保存每日赌博限制数据"""
    await save_json_data(GAMBLE_LIMITS_FILE, data, gamble_limit_lock)

async def check_daily_gamble_limit(user_id):
    """检查用户今天是否已经赌过"""
    user_id_str = str(user_id)
    limits = await load_gamble_limits()
    today_str = date.today().isoformat()
    last_gamble_date = limits.get(user_id_str)
    if last_gamble_date == today_str:
        return False # 今天已经赌过了
    return True # 今天还没赌