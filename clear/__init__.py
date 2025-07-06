import gc
import time
from datetime import datetime
from hoshino import Service
from hoshino.config import SUPERUSERS
from hoshino.typing import CQEvent as Event, MessageSegment

sv = Service('memory_cleaner', help_='自动内存清理工具')

# 每天自动执行内存清理
# 已弃用，不如写个脚本每天自动重启
'''
@sv.scheduled_job('cron', hour='0', minute='5')
async def auto_memory_clean():
    """每小时自动清理内存"""
    start_time = time.time()
    before = gc.get_count()  # 获取当前垃圾回收计数
    
    # 执行垃圾回收
    collected = gc.collect()
    
    after = gc.get_count()
    end_time = time.time()
    
    # 记录日志
    log_msg = (
        f"[{datetime.now()}] 自动内存清理完成 | "
        f"回收对象: {collected} | "
        f"耗时: {end_time - start_time:.3f}s | "
        f"GC计数变化: {before} -> {after}"
    )
    sv.logger.info(log_msg)
'''
# 手动触发内存清理命令
@sv.on_fullmatch('清理内存')
async def manual_memory_clean(bot,ev):
    """手动触发内存清理 (仅限SUPERUSER)"""
    if ev.user_id not in SUPERUSERS:
        return
    start_time = time.time()
    before = gc.get_count()
    
    # 执行垃圾回收
    collected = gc.collect()
    
    after = gc.get_count()
    end_time = time.time()
    
    # 构造回复消息
    msg = (
        "♻️ 内存清理完成\n"
        f"回收对象数量: {collected}\n"
        f"耗时: {end_time - start_time:.3f}秒\n"
        f"GC计数变化: {before} → {after}"
    )
    
    await bot.send(ev, msg)
    sv.logger.info(f"手动内存清理由用户 {ev.user_id} 触发: {msg}")