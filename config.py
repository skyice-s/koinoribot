# 冰祈插件相关配置文件


# 好友、群聊管理
white_list_group = 1027790249    # 白名单群聊
group_auto_approve = False      # 是否自动同意进群(需进入白名单群）
friend_auto_approve = False     # 是否自动同意好友邀请（需进入白名单群）
star_cost_mode = False          # 是否需要消耗星星来获得bot好友


SEND_FORWARD = True  # 是否启用合并转发（应对风控）
PUBLIC_BOT = True  # 是否启用云bot模式（一般可忽略）


# 腾讯api
# 密钥可前往 https://console.cloud.tencent.com/cam/capi 网站进行获取
TXSecretId = ''
TXSecretKey = ''

# 天行api，使用范围：土味情话，彩虹屁，可前往 https://www.tianapi.com/ 获取
tianxing_apikey = ''

# 有道翻译api
youdao_appkey = ''
youdao_secret = ''

# 随机美图
AUTO_SAVE = True  # 是否保存到本地
AUTO_DELETE = False  # 是否撤回
DELETE_TIME = 30  # 撤回的等待时间

# arcaeaAPI
api_url = 'https://server.awbugl.top/arcapi/'
token = ''

# danbooru
SAVE_MODE = False  # 是否保存到本地
DELETE_MODE = False  # 是否自动撤回

# 今天吃什么
foods_whitelist = [837052156, 974114299, 807505574]  # 可以添加菜谱的群聊，为空则所有人都能添加

# 网络代理
proxies = {}

# openai api (已失效过期)
OPEN_API = ''
OPEN_ORG = ''

#chatplus 令牌
chat_whitelist = False  # 是否启动白名单模式
PLUS_TOKEN = ''


# jhapi api
# ??? 用法不明
JHAPI_API = ''

#新增功能
maxhp = 100000                   #萝莉初始血量
lowdamage = 1000                  #捉萝莉伤害下限
highdamage = 5000               #捉萝莉伤害上限
loliprice = 1000                 #捉萝莉需要消耗的鱼饵数量
miss = 0.5                      #捉萝莉miss概率(a)
bbjb = 0.5                      #miss后爆用户金币的概率(b)——综合概率：a*b
bjb = 0.5                      #爆萝莉金币的概率（c）——综合概率：(1-a)*c
xinyun_bjb = 0.03               #捉萝莉幸运大奖概率（d）——综合概率：(1-a)*c*d
jishagold = 10000               #击杀奖励
bosstime = 2                    #是否开启boss战  0关闭  1开启  其余数字则鱼塘和boss战同时开启
min_rest = 10000                #转账后最少需剩余多少金币
dibao = 1                       #是否开启低保发放，0关闭，1开启
stone_fee = 0.5                 #退还宝石手续费比率，0为不收取
maxtype = 4                     #股票持有种类上限
maxcount = 500                  #每种股票持有数量上限
star_price = 0                  #多连钓鱼是否消耗对应数量的星星（1为消耗，0为不消耗）


# 钓鱼
ADMIN_GROUP = 348831286                         # 漂流瓶审核群(必须有一个)
COOL_TIME = 5                                  # 单抽钓鱼冷却时长
fishcd = 15                                     #除单抽钓鱼以外的通用钓鱼冷却
THROW_COOL_TIME = 5                            # 扔漂流瓶冷却时长
SALVAGE_COOL_TIME = 5                          # 捡漂流瓶冷却时长
COMMENT_COOL_TIME = 5                          # 评论漂流瓶冷却时长
BAIT_PRICE = 3                                  # 鱼饵的价格
BOTTLE_PRICE = 200                              # 漂流瓶的价格，建议为 (水之心转化为漂流瓶的数量+1)×碎片转化为水之心的数量
COMMENT_PRICE = 50                              # 评论漂流瓶需要的金币（删除不会返还）
FRAG_TO_CRYSTAL = 75                            # 碎片转化为水之心的数量
CRYSTAL_TO_BOTTLE = 1                           # 水之心转化为漂流瓶的数量
CRYSTAL_TO_NET = 1                              # 捞漂流瓶需要的水之心数量
BLACKUSERS = []

FISH_LIST = ['🐟', '🦐', '🦀', '🐡', '🐠', '🦈', '🌟']   # 可钓起的鱼列表，如果更新则务必在下面添加其价格和上钩概率

FISH_PRICE = {'🍙': 1, '🐟': 5, '🦐': 10, '🦀': 35, '🐡': 45, '🐠': 75, '🦈': 100, '🌟': 2000}  # 鱼的价格
#         '🍙': 1, '🐟': 5, '🦐': 10, '🦀': 35, '🐡': 45, '🐠': 75, '🦈': 100, '🌟': 2000

# (A, B, C, D, E) 没钓到鱼/ 随机事件/ 钓到鱼/ 钓到金币/ 钓到水之心 的概率（%），必须为整数，且务必加起来等于100
# 通常来说改第一个元组的内容就行（其他鱼竿没有实装）
PROBABILITY = [(9, 15, 65, 10, 1), (20, 2, 75, 2, 1), (20, 2, 75, 2, 1)]
#     34, 1, 63, 1, 1
#     99, 0, 1, 0, 0

# 海之眷顾 所有鱼的上钩概率(%)，(必须为整数，维度要和鱼的种类一致，且务必加起来等于100)
# 通常来说改第一个元组的内容就行（其他鱼竿没有实装）
PROBABILITY_2 = [(36, 24, 18, 11, 6, 4, 1), (27, 26, 25, 8, 8, 5, 1), (27, 26, 25, 8, 8, 5, 1)]
#     30, 25, 16, 14, 8, 6, 1
#     39, 25, 17, 8, 6, 4, 1
DEBUG_MODE = False          # 调试模式
FREEZE_FC = 75              # 固定first_choose的值，如果为0则不固定
FREEZE_SC = 950             # 固定second_choose的值，同上
