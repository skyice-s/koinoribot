import json
import os
import random
import time
import base64
from datetime import datetime, timedelta
import math
import asyncio # 用于文件锁
import io         # 用于在内存中处理图像
import plotly.graph_objects as go
import plotly.io as pio
from ..utils import chain_reply
import matplotlib
matplotlib.use('Agg') # 设置Matplotlib后端为非交互式，适用于服务器环境
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


from hoshino import Service, priv, R
from hoshino.typing import CQEvent, MessageSegment
from .. import money 
sv = Service('stock_market', manage_priv=priv.ADMIN, enable_on_default=True)
ADMIN_UID = 180162404 

# --- 新增功能常量 ---
try:
    # 这是标准方法，适用于大多数情况
    current_plugin_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # 如果在某些特殊环境 (如某些打包工具或交互式解释器) __file__ 未定义，
    # 可以尝试使用 inspect 模块作为后备
    import inspect
    current_plugin_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

PLUGIN_DATA_DIR = os.path.join(current_plugin_dir, 'data')
STOCKS_FILE = os.path.join(PLUGIN_DATA_DIR, 'stock_data.json')
PORTFOLIOS_FILE = os.path.join(PLUGIN_DATA_DIR, 'user_portfolios.json')
HISTORY_DURATION_HOURS = 24 # 只保留过去24小时数据

# 锁，防止并发读写JSON文件导致数据损坏
stock_file_lock = asyncio.Lock()
portfolio_file_lock = asyncio.Lock()

# 股票定义 (名称: 初始价格)
STOCKS = {
    "萝莉股": 100.0,
    "猫娘股": 120.0,
    "魔法少女股": 140.0,
    "梦月股": 500.0,
    "梦馨股": 200.0,
    "高达股": 90.0,
    "雾月股": 240.0,
    "傲娇股": 130.0,
    "病娇股": 70.0,
    "梦灵股": 250.0,
}

# --- 辅助函数：读写JSON ---

async def load_json_data(filename, default_data, lock):
    """异步安全地加载JSON数据"""
    async with lock:
        if not os.path.exists(filename):
            return default_data
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # 文件损坏或读取错误，返回默认值
            return default_data

async def save_json_data(filename, data, lock):
    """异步安全地保存JSON数据"""
    async with lock:
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            # 使用临时文件和原子移动来增加保存的安全性
            temp_filename = filename + ".tmp"
            with open(temp_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            os.replace(temp_filename, filename) # 原子操作替换
        except IOError as e:
            print(f"Error saving JSON data to {filename}: {e}")
            # Consider logging the error more formally in a real application
            # pass # Or raise the exception if needed

# --- 辅助函数：获取和更新数据 ---

async def get_stock_data():
    """获取所有股票数据"""
    default = {
        name: {"initial_price": price, "history": []}
        for name, price in STOCKS.items()
    }
    return await load_json_data(STOCKS_FILE, default, stock_file_lock)

async def save_stock_data(data):
    """保存所有股票数据"""
    await save_json_data(STOCKS_FILE, data, stock_file_lock)

async def get_user_portfolios():
    """获取所有用户持仓"""
    return await load_json_data(PORTFOLIOS_FILE, {}, portfolio_file_lock)

async def save_user_portfolios(data):
    """保存所有用户持仓"""
    await save_json_data(PORTFOLIOS_FILE, data, portfolio_file_lock)

async def get_current_stock_price(stock_name, stock_data=None):
    """获取指定股票的当前价格"""
    if stock_data is None:
        stock_data = await get_stock_data()
    
    if stock_name not in stock_data or not stock_data[stock_name]["history"]:
        # 如果没有历史记录，返回初始价格
        return stock_data.get(stock_name, {}).get("initial_price")
    
    # 返回最新价格
    return stock_data[stock_name]["history"][-1][1] # history is [(timestamp, price), ...]

async def get_stock_price_history(stock_name, stock_data=None):
    """获取指定股票过去24小时的价格历史"""
    if stock_data is None:
        stock_data = await get_stock_data()
    
    if stock_name not in stock_data:
        return []
        
    cutoff_time = time.time() - HISTORY_DURATION_HOURS * 3600
    history = stock_data[stock_name].get("history", [])
    
    # 筛选出24小时内的数据
    recent_history = [(ts, price) for ts, price in history if ts >= cutoff_time]
    return recent_history

async def get_user_portfolio(user_id):
    """获取单个用户的持仓"""
    portfolios = await get_user_portfolios()
    return portfolios.get(str(user_id), {}) # user_id 转为字符串以匹配JSON键

async def update_user_portfolio(user_id, stock_name, change_amount):
    """更新用户持仓 (正数为买入，负数为卖出)"""
    portfolios = await get_user_portfolios()
    user_id_str = str(user_id)
    
    if user_id_str not in portfolios:
        portfolios[user_id_str] = {}
        
    current_amount = portfolios[user_id_str].get(stock_name, 0)
    new_amount = current_amount + change_amount
    
    if new_amount < 0:
        # This should ideally be checked before calling update_user_portfolio
        print(f"Error: Attempted to make stock {stock_name} amount negative for user {user_id}")
        return False # Indicate failure

    if new_amount == 0:
        # 如果数量归零，从持仓中移除该股票
        if stock_name in portfolios[user_id_str]:
            del portfolios[user_id_str][stock_name]
        # 如果用户不再持有任何股票，可以考虑移除该用户条目（可选）
        # if not portfolios[user_id_str]:
        #     del portfolios[user_id_str]
    else:
        portfolios[user_id_str][stock_name] = new_amount
        
    await save_user_portfolios(portfolios)
    return True # Indicate success
    



@sv.scheduled_job('cron', hour='*', minute='0') # 每小时的0分执行
# async def update_all_stock_prices(): # 函数名用 update_all_stock_prices 更清晰
async def hourly_price_update_job(): # 或者叫这个
    """定时更新所有股票价格"""
    print(f"[{datetime.now()}] Running hourly stock price update...")
    stock_data = await get_stock_data()
    current_time = time.time()
    cutoff_time = current_time - HISTORY_DURATION_HOURS * 3600

    changed = False
    for name, data in stock_data.items():
        initial_price = data["initial_price"]
        history = data.get("history", [])
        
        # 清理旧数据
        original_len = len(history)
        history = [(ts, price) for ts, price in history if ts >= cutoff_time]
        if len(history) != original_len:
             changed = True

        # 计算新价格
        if not history:
            current_price = initial_price
        else:
            current_price = history[-1][1]

        # --- 随机波动逻辑 ---
        # 更平滑的波动：小的随机游走 + 轻微向初始价格回归的趋势
        change_percent = random.uniform(-0.15, 0.15) # 基础波动范围
        # 轻微向初始价回归 (可选, 防止价格无限漂移)
        regression_factor = 0.01 # 回归强度
        change_percent += regression_factor * (initial_price - current_price) / current_price

        new_price = current_price * (1 + change_percent)

        # --- 价格限制 ---
        min_price = initial_price * 0.01
        max_price = initial_price * 2.00 # 100%
        new_price = max(min_price, min(new_price, max_price))
        
        # 保留两位小数
        new_price = round(new_price, 2) 

        # 添加新价格到历史记录
        if not history or history[-1][1] != new_price: # 仅当价格变化时记录
             history.append((current_time, new_price))
             stock_data[name]["history"] = history # 更新回主数据
             changed = True
        else:
             # 如果价格未变，仍需更新清理后的历史记录
             stock_data[name]["history"] = history


    if changed:
        await save_stock_data(stock_data)
        print(f"[{datetime.now()}] Stock prices updated and saved.")
    else:
        print(f"[{datetime.now()}] Stock prices checked, no significant changes to save.")

# --- 初始化：确保数据文件存在且结构正确 ---
# 可以在机器人启动时运行一次
async def initialize_stock_market():
    """初始化股票市场数据"""
    print("Initializing stock market data...")
    stock_data = await get_stock_data()
    portfolios = await get_user_portfolios() # 加载一次以创建文件（如果不存在）
    
    needs_save = False
    # 确保所有定义的股票都在数据中
    for name, initial_price in STOCKS.items():
        if name not in stock_data:
            stock_data[name] = {"initial_price": initial_price, "history": []}
            needs_save = True
        elif "initial_price" not in stock_data[name] or stock_data[name]["initial_price"] != initial_price:
             stock_data[name]["initial_price"] = initial_price # 更新初始价格（如果代码中修改了）
             needs_save = True
        if "history" not in stock_data[name]:
            stock_data[name]["history"] = []
            needs_save = True
            
    # 可以在这里触发一次价格更新，确保启动时有初始价格点
    # await hourly_price_update_job() # 如果希望启动时就更新

    if needs_save:
        await save_stock_data(stock_data)
        print("Stock data initialized/updated.")
    await save_user_portfolios(portfolios) #确保文件存在
    print("Stock market initialization complete.")


def generate_stock_chart(stock_name, history):
    """使用 Plotly 生成股票历史价格图表的 PNG 图片"""
    if not history:
        return None

    timestamps, prices = zip(*history)
    
    # 将Unix时间戳转换为datetime对象，Plotly可以直接使用
    dates = [datetime.fromtimestamp(ts) for ts in timestamps]

    # 创建 Plotly Figure
    fig = go.Figure()

    # 添加价格折线图
    fig.add_trace(go.Scatter(
        x=dates,
        y=prices,
        mode='lines+markers', # 线条加标记点
        marker=dict(size=4),  # 标记点大小
        line=dict(shape='linear'), # 线性连接
        name='价格' # 图例名称
    ))

    # 获取当前价格和初始价格用于标题和注释
    current_price = history[-1][1]
    # !! 注意: STOCKS 现在需要在这个函数作用域内可访问，或者作为参数传入
    # !! 或者从 stock_data 中获取 initial_price (如果传入 stock_data 会更好)
    # !! 假设 STOCKS 是全局可访问的
    initial_price = STOCKS.get(stock_name, 0) 

    # 更新图表布局
    fig.update_layout(
        title=f'{stock_name} 过去{HISTORY_DURATION_HOURS}小时价格走势 (初始: {initial_price:.2f})',
        xaxis_title='时间',
        yaxis_title='价格 (金币)',
        xaxis=dict(
            tickformat='%H:%M', # X轴刻度格式 时:分
            # 可以根据需要调整刻度间隔，Plotly 通常会自动处理
            # tickmode='auto',
            # nbins= 10, # 尝试控制刻度数量
        ),
        yaxis=dict(
            # tickformat='.2f' # Y轴保留两位小数
        ),
        hovermode='x unified', # 鼠标悬停时显示统一信息
        template='plotly_white', # 使用简洁的白色主题
        margin=dict(l=50, r=50, t=80, b=50), # 调整边距
        # 如果需要中文标题/标签，Plotly通常能自动处理，但依赖系统字体
        # title_font_family="SimHei, Microsoft YaHei, sans-serif", # 尝试指定字体
        # font_family="SimHei, Microsoft YaHei, sans-serif"
    )
    
    # 添加当前价格注释 (右上角)
    fig.add_annotation(
        x=dates[-1], # x 坐标为最后一个数据点的时间
        y=current_price, # y 坐标为当前价格
        xref="x", # 参照 x 轴
        yref="y", # 参照 y 轴
        text=f'当前: {current_price:.2f}',
        showarrow=True,
        arrowhead=1,
        ax=50, # 箭头在x方向的偏移
        ay=-30 # 箭头在y方向的偏移 (向上指)
        # 或者使用相对位置：
        # x=1, y=1, xref='paper', yref='paper', # 参照整个绘图区域的右上角
        # text=f'当前: {current_price:.2f}',
        # showarrow=False,
        # xanchor='right', yanchor='top',
        # font=dict(size=12, color="black"),
        # bgcolor="wheat", bordercolor="black", borderwidth=1, borderpad=4,
    )


    try:
        # 将图表导出为 PNG 图片字节流
        # scale 参数可以提高图片分辨率，默认为 1
        img_bytes = pio.to_image(fig, format='png', scale=2)
        
        # 将字节流包装在 BytesIO 对象中，以便像文件一样处理
        buf = io.BytesIO(img_bytes)
        buf.seek(0)
        return buf
    except Exception as e:
        # 如果导出失败（例如 kaleido 问题），打印错误并返回 None
        print(f"Error generating Plotly chart image for {stock_name}: {e}")
        # 在实际应用中，这里应该使用日志记录
        # logger.error(f"Error generating Plotly chart image for {stock_name}: {e}")
        return None


# --- 命令处理函数 ---

@sv.on_rex(r'^(.+股)走势$') # 匹配 "xxx股走势"
async def handle_stock_quote(bot, ev):
    match = ev['match']
    stock_name = match[1].strip() # 获取股票名称

    if stock_name not in STOCKS:
        await bot.send(ev, f'未知股票: {stock_name}。可用的股票有: {", ".join(STOCKS.keys())}')
        return

    stock_data = await get_stock_data()
    history = await get_stock_price_history(stock_name, stock_data)
    
    if not history:
        initial_price = stock_data[stock_name]["initial_price"]
        await bot.send(ev, f'{stock_name} 暂时还没有价格历史记录。初始价格为 {initial_price:.2f} 金币。')
        return

    chart_buf = generate_stock_chart(stock_name, history)
    
    if chart_buf:
        # 1. 获取 BytesIO 中的字节数据
        image_bytes = chart_buf.getvalue()
        # 2. 进行 Base64 编码
        b64_str = base64.b64encode(image_bytes).decode()
        # 3. 构建 CQ 码字符串
        cq_code = f"[CQ:image,file=base64://{b64_str}]"
        #  4. 发送 CQ 码
        await bot.send(ev, cq_code)
        chart_buf.close()  # 重要！避免内存泄漏

@sv.on_rex(r'^买入\s*(.+股)\s*(\d+)$')
async def handle_buy_stock(bot, ev):
    user_id = ev.user_id
    match = ev['match']
    stock_name = match[1].strip()
    
    try:
        amount_to_buy = int(match[2])
        if amount_to_buy <= 0:
            await bot.send(ev, '购买数量必须是正整数。')
            return
    except ValueError:
        await bot.send(ev, '购买数量无效。')
        return

    if stock_name not in STOCKS:
        await bot.send(ev, f'未知股票: {stock_name}。')
        return

    current_price = await get_current_stock_price(stock_name)
    if current_price is None:
        await bot.send(ev, f'{stock_name} 当前无法交易，请稍后再试。')
        return

    # 使用 math.ceil 确保花费的金币是整数且足够支付（向上取整）
    total_cost = math.ceil(current_price * amount_to_buy) 

    # 检查用户金币 (假设 money 模块存在且可用)
    user_gold = money.get_user_money(user_id, 'gold')
    if user_gold is None:
         await bot.send(ev, '无法获取您的金币信息。')
         return
         
    if user_gold < total_cost:
        await bot.send(ev, f'金币不足！购买 {amount_to_buy} 股 {stock_name} 需要 {total_cost} 金币，您只有 {user_gold} 金币。当前单价: {current_price:.2f}')
        return

    # 执行购买
    if money.reduce_user_money(user_id, 'gold', total_cost):
        if await update_user_portfolio(user_id, stock_name, amount_to_buy):
             await bot.send(ev, f'购买成功！您以 {current_price:.2f} 金币/股的价格买入了 {amount_to_buy} 股 {stock_name}，共花费 {total_cost} 金币。', at_sender=True)
        else:
             # 如果更新持仓失败，需要回滚金币（重要！）
             money.increase_user_money(user_id, 'gold', total_cost)
             await bot.send(ev, '购买失败，更新持仓时发生错误。您的金币已退回。')
    else:
        await bot.send(ev, '购买失败，扣除金币时发生错误。')


@sv.on_rex(r'^卖出\s*(.+股)\s*(\d+)$')
async def handle_sell_stock(bot, ev):
    user_id = ev.user_id
    match = ev['match']
    stock_name = match[1].strip()
    
    try:
        amount_to_sell = int(match[2])
        if amount_to_sell <= 0:
            await bot.send(ev, '出售数量必须是正整数。')
            return
    except ValueError:
         await bot.send(ev, '出售数量无效。')
         return

    if stock_name not in STOCKS:
        await bot.send(ev, f'未知股票: {stock_name}。')
        return

    user_portfolio = await get_user_portfolio(user_id)
    current_holding = user_portfolio.get(stock_name, 0)

    if current_holding < amount_to_sell:
        await bot.send(ev, f'您没有足够的 {stock_name} 来出售。您当前持有 {current_holding} 股，尝试出售 {amount_to_sell} 股。', at_sender=True)
        return

    current_price = await get_current_stock_price(stock_name)
    if current_price is None:
        await bot.send(ev, f'{stock_name} 当前无法交易，请稍后再试。')
        return

    # 使用 math.floor 确保获得的金币是整数（向下取整）
    total_earnings = math.floor(current_price * amount_to_sell)

    # 执行出售
    if await update_user_portfolio(user_id, stock_name, -amount_to_sell): # 传入负数表示减少
        money.increase_user_money(user_id, 'gold', total_earnings)
        await bot.send(ev, f'出售成功！您以 {current_price:.2f} 金币/股的价格卖出了 {amount_to_sell} 股 {stock_name}，共获得 {total_earnings} 金币。', at_sender=True)
    else:
        # 如果更新持仓失败，不需要回滚金币，因为金币还没增加
        await bot.send(ev, '出售失败，更新持仓时发生错误。')

# 使用 on_prefix 更灵活，可以接受 "我的股仓" 或 "查看股仓" 等
@sv.on_prefix(('我的股仓', '查看股仓'))
async def handle_my_portfolio(bot, ev):
    user_id = ev.user_id
    user_portfolio = await get_user_portfolio(user_id)

    if not user_portfolio:
        await bot.send(ev, '您的股仓是空的，快去买点股票吧！', at_sender=True)
        return

    stock_data = await get_stock_data() # 批量获取一次数据，减少重复加载
    
    report_lines = [f"{ev.sender['nickname']} 的股仓详情:"]
    total_value = 0.0
    stock_details_for_charting = [] # 存储需要画图的股票信息

    for stock_name, amount in user_portfolio.items():
        current_price = await get_current_stock_price(stock_name, stock_data)
        if current_price is None:
            current_price = stock_data.get(stock_name, {}).get("initial_price", 0) # Fallback to initial or 0
            value_str = "???"
        else:
            value = current_price * amount
            value_str = f"{value:.2f}"
            total_value += value
        
        report_lines.append(f"- {stock_name}: {amount} 股, 当前单价: {current_price:.2f}, 总价值: {value_str} 金币")
        
        # 记录下来以便后续生成图表
        stock_details_for_charting.append(stock_name)


    report_lines.append(f"--- 股仓总价值: {total_value:.2f} 金币 ---")
    
    # 先发送文本总结
    await bot.send(ev, "\n".join(report_lines), at_sender=True)
    '''
    sent_charts = 0
    for stock_name in stock_details_for_charting:
        history = await get_stock_price_history(stock_name, stock_data)
        if history:
            chart_buf = generate_stock_chart(stock_name, history)
            if chart_buf:
                # --- 修改开始 ---
                image_bytes = chart_buf.getvalue()
                b64_str = base64.b64encode(image_bytes).decode()
                cq_code = f"[CQ:image,file=base64://{b64_str}]"
                await bot.send(ev, cq_code)
                # --- 修改结束 ---
                sent_charts += 1
            await asyncio.sleep(0.5) # 短暂延迟防止刷屏
    '''

# --- 新增命令：股票列表 ---
@sv.on_prefix(('股票列表')) # 可以使用 "股票列表" 或 "股市行情" 触发
async def handle_stock_list(bot, ev):
    stock_data = await get_stock_data() # 加载所有股票数据

    if not stock_data:
        await bot.send(ev, "暂时无法获取股市数据，请稍后再试。")
        return

    report_lines = ["📈 当前股市行情概览:"]
    # 按股票名称排序，使列表顺序固定
    sorted_stock_names = sorted(stock_data.keys())

    all_prices_found = True
    for stock_name in sorted_stock_names:
        # 从已加载的数据中获取当前价格
        current_price = await get_current_stock_price(stock_name, stock_data)

        if current_price is not None:
            # 格式化输出，保留两位小数
            report_lines.append(f"◽ {stock_name}: {current_price:.2f} 金币")
        else:
            # 如果由于某种原因无法获取价格（例如数据文件问题或新添加的股票尚未更新）
            initial_price = STOCKS.get(stock_name, "未知") # 尝试获取初始价作为备用
            report_lines.append(f"◽ {stock_name}: 价格未知 (初始: {initial_price})")
            all_prices_found = False # 标记一下有价格未找到

    if len(report_lines) == 1: # 如果只有标题行，说明没有股票数据
        await bot.send(ev, "当前市场没有可交易的股票。")
        return

    # 如果所有价格都正常获取，可以添加一个更新时间戳
    if all_prices_found:
        # 尝试获取最新价格的时间戳 (选择第一个股票的最后一个历史点作为代表)
        try:
            first_stock_data = stock_data[sorted_stock_names[0]]
            if first_stock_data.get("history"):
                last_update_ts = first_stock_data["history"][-1][0]
                last_update_time = datetime.fromtimestamp(last_update_ts).strftime('%Y-%m-%d %H:%M:%S')
                report_lines.append(f"\n(数据更新于: {last_update_time})")
            else:
                report_lines.append("\n(部分股票价格为初始价)")
        except (IndexError, KeyError):
             report_lines.append("\n(无法获取准确更新时间)")


    # 发送整合后的列表
    await bot.send(ev, "\n".join(report_lines))
    
    
@sv.on_fullmatch('更新股价') # 使用完全匹配，指令必须是 "更新股价"
async def handle_manual_price_update(bot, ev):
    admin_uid = ev.user_id
    # 1. 权限验证
    if admin_uid != ADMIN_UID:
        await bot.send(ev, '权限不足，只有管理员才能手动更新股价。')
        return

    # 发送一个处理中的提示，因为更新可能需要一点时间
    await bot.send(ev, "收到指令，正在手动触发股价更新...", at_sender=True)

    try:
        # 2. 调用核心的股价更新函数
        # 这个函数包含了加载数据、计算新价格、清理旧数据、保存数据的完整逻辑
        await hourly_price_update_job()

        # 3. 发送成功反馈
        # 获取当前时间用于反馈
        now_time_str = datetime.now().strftime('%H:%M:%S')
        await bot.send(ev, f"✅ 股价已于 {now_time_str} 手动更新完成！\n您可以使用 '股票列表' 或具体股票的 '走势' （例如：猫娘股趋势）指令查看最新价格。", at_sender=True)

    except Exception as e:
        # 4. 如果更新过程中出现任何未预料的错误，则捕获并报告
        # 在实际应用中，这里应该有更详细的日志记录
        error_message = f"手动更新股价时遇到错误：{type(e).__name__} - {e}"
        print(f"[ERROR] Manual stock update failed: {error_message}") # 打印到控制台/日志
        # 向管理员发送错误通知
        await bot.send(ev, f"❌ 手动更新股价失败。\n错误详情: {error_message}\n请检查后台日志获取更多信息。", at_sender=True)
        
        
help_chaogu = '''
炒股游戏帮助：

温馨提醒：股市有风险，切莫上头。

**指令列表：**
1.  股票列表：查看所有股票的名字和实时价格
2.  买入 [股票名称] [具体数量]：例如：买入 萝莉股 10
3.  卖出 [股票名称] [具体数量]：例如：卖出 萝莉股 10
4.  我的股仓：查看自己现在持有的股票
5.  [股票名称]走势：查看某一股票的价格折线图走势（会炸内存，慎用），例如：萝莉股走势
初始股票价格：
    "萝莉股": 100.0,
    "猫娘股": 120.0,
    "魔法少女股": 140.0,
    "梦月股": 500.0,
    "梦馨股": 200.0,
    "高达股": 90.0,
    "雾月股": 240.0,
    "傲娇股": 130.0,
    "病娇股": 70.0,
    "梦灵股": 250.0,
'''
@sv.on_fullmatch('炒股帮助')
async def chaogu_help(bot, ev):
    """
        拉取游戏帮助
    """
    chain = []
    await chain_reply(bot, ev, chain, help_chaogu)
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)
