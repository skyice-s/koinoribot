from hoshino import Service, priv
from hoshino.typing import CQEvent

sv = Service('_bqhelp_', manage_priv=priv.SUPERUSER, visible=False)
TOP_MANUAL = '''
= 冰祈使用说明 =
旧版功能：https://www.lanxy.ink/?p=476
\n新增功能请发送：
\n钓鱼帮助\n炒股帮助\n宠物帮助\n金币炸弹帮助
\n若想快速赚取金币，不妨试试惊险又刺激的“一场豪赌”吧！
\n幸运币获取途径：钓鱼、签到、宠物技能、宠物扭蛋
\n宝石获取途径：买宝石+数量、宠物技能
\n发送 领养云冰祈 将你自己的bot接入云冰祈（目前仅支持yunzai）
'''.strip()
@sv.on_prefix('冰祈帮助')
async def send_help(bot, ev: CQEvent):
    await bot.send(ev, TOP_MANUAL)
