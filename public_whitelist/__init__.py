from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import os
import hoshino
from hoshino import Service
from hoshino.config import SUPERUSERS
from ..utils import saveData, loadData, chain_reply
from .._interact import interact, ActSession
from nonebot.message import MessageSegment
from hoshino.typing import CQEvent as Event, CommandSession, CQHttpError, NoticeSession

sv = Service('公网多端白名单', visible=False)
file_path = os.path.join(os.path.dirname(
    __file__), '../../../public_wlist.json')


user_limit = True
max_user = 100
permit_group = [748733770, 348831286, 984760873]
permit_bot = [3625681236, 2241893540, 1801284184]


@sv.on_prefix('添加公网白名单')
async def add_public_bot_whitelist(bot, ev):
    if ev.user_id not in SUPERUSERS:
        return
    white_list = loadData(file_path)
    message = ev.message.extract_plain_text().strip()
    user_and_bot = message.split()
    if not len(user_and_bot) == 2:
        await bot.send(ev, '要主人QQ(先)和botQQ(后)噢')
        return
    owner = str(user_and_bot[0])
    bot__ = int(user_and_bot[1])
    if owner not in list(white_list.keys()) and bot__ not in list(white_list.values()):
        white_list[owner] = bot__
        saveData(white_list, file_path)
        await bot.send(ev, f'已成功添加该bot({bot__})，并绑定主人({owner})')
    else:
        await bot.send(ev, '该主人已有bot或bot已被认领~')
    return


@sv.on_prefix('云冰祈', '领养云冰祈')
async def auto_add_whitelist(bot, ev):
    if ev.self_id not in permit_bot:
        return
    if ev.group_id not in permit_group:
        return
    session = interact.find_session(ev, '注册云冰祈')
    if session:
        if session.is_expire():
            session.close()
        else:
            await bot.send(ev, '有人正在领养云冰祈，请稍等一下~')
            return
    wlist = loadData(file_path)
    if str(ev.user_id) in list(wlist.keys()):
        await bot.send(ev, '你已经领养过一个云冰祈了\n如果想重新领养，请先 注销云冰祈')
        return
    if user_limit:
        if len(list(wlist.keys())) >= max_user:
            await bot.send(ev, '已达到云冰祈领养上限(50个)...')
            return
    session = ActSession.from_event(
        name='注册云冰祈', event=ev, max_user=1, expire_time=300)
    interact.add_session(session)
    session.state['owner'] = str(ev.user_id)
    session.state['bot'] = 0
    session.state['device'] = ''
    await bot.send(ev, '（领养前，请务必先添加我为好友哦~否则发不出私信。）\n要领养云冰祈咯~请输入bot的QQ号')

help_1 = '''请依次对你的bot私聊发送以下每一行内容。(确保你的云崽安装了ws-plugin)'''

help_2 = '''#ws添加连接'''
help_3 = '''ko,1'''

help_4 = '''ws://47.105.55.194:5021/ws,5,0'''







@sv.on_message()
async def cloudkoinori_get_owner(bot, ev):
    session = interact.find_session(ev, name='注册云冰祈')
    if not session:
        return
    submit = ev.message.extract_plain_text().strip()
    if str(ev.user_id) != session.state['owner']:
        if ev.user_id in SUPERUSERS and submit == '退出':
            session.close()
            await bot.send(ev, '强行结束领养了...')
        return
    if submit == '退出':
        session.close()
        await bot.send(ev, '已结束领养云冰祈~')
        return
    if not session.state['bot']:
        if not str.isdigit(submit):
            await bot.send(ev, '需要输入qq号码~')
            return
        if int(submit) == ev.user_id:
            await bot.send(ev, '请使用bot主人注册账号~而且自身不能是bot')
            return
        session.state['bot'] = int(submit)
        await bot.send(ev, '请输入连接设备：yunzai/gocq(已弃用)')
        return
    if session.state['bot'] and not session.state['device']:
        if submit not in ['114514191981012345', 'yunzai']:
            await bot.send(ev, '目前只支持yunzai')
            return
        session.state['device'] = submit
        if submit == 'yunzai':
            config_file = 'ws-config.yaml'
        else:
            config_file = 'config.yml'
        await bot.send(ev, f'已准备好领养资料：\n主人：{session.state["owner"]}\nbot：{session.state["bot"]}\n发送“确认领养”结束领养过程\n如果信息有误，请输入“退出”\n领养后，请不要让你的bot进入本群或任何已存在冰祈的群聊。')
        return
    else:
        if submit != '确认领养':
            return
        elif submit == '退出':
            session.close()
            await bot.send(ev, '已结束领养云冰祈~')
            return
        else:
            receiver = session.state['owner'] + '@qq.com'
            if session.state['device'] == 'gocq':
                await bot.send(ev, '暂不支持')
                session.close()
                return
                content = f'主人QQ:{session.state["owner"]}\nbotQQ:{session.state["bot"]}\n使用设备:{session.state["device"]}\n请将配置文件覆盖原有的config.yml~\n请妥善保管配置文件~'
                attach_fp = os.path.join(
                    os.path.dirname(__file__), 'config.yml')
                attach_name = 'config.yml'
                try:
                    white_list = loadData(file_path)
                    if session.state["owner"] not in list(white_list.keys()) and session.state["bot"] not in list(white_list.values()):
                        white_list[session.state["owner"]
                                   ] = session.state["bot"]
                        mail(receiver, content, attach_fp, attach_name)
                        saveData(white_list, file_path)
                        await bot.send(ev, '邮件已成功发送，请注意查收~')
                    else:
                        await bot.send(ev, '该主人已有bot或bot已被认领~')
                    session.close()
                    return
                except Exception as e:
                    hoshino.logger.error(f'gocq附件发送邮件失败：{str(e)}')
                    session.close()
                    await bot.send(ev, '邮件发送失败了QAQ')
                    return
            else:
                content = f'主人QQ:{session.state["owner"]}\nbotQQ:{session.state["bot"]}\n使用设备:{session.state["device"]}\n请将配置文件覆盖原有的ws-config.yaml~\n请妥善保管配置文件~'
                attach_fp = os.path.join(
                    os.path.dirname(__file__), 'ws-config.yaml')
                attach_name = 'ws-config.yaml'
                try:
                    white_list = loadData(file_path)
                    if session.state["owner"] not in list(white_list.keys()) and session.state["bot"] not in list(white_list.values()):
                        white_list[session.state["owner"]
                                   ] = session.state["bot"]
                        mail(receiver, content, attach_fp, attach_name)
                        saveData(white_list, file_path)
                        #await bot.send(ev, '领养完成，请按照提示完成接下来的操作。')
                        await bot.send(ev, '领养完成，已添加白名单。请查看QQ私信并按照提示完成接下来的操作。\n如果没有私信，说明没有添加好友。请先 注销云冰祈 ，然后添加好友，再重复领养步骤。')
                        chain = []
                        await chain_reply(bot, ev, chain, help_1)
                        await chain_reply(bot, ev, chain, help_2)
                        await chain_reply(bot, ev, chain, help_3)
                        await chain_reply(bot, ev, chain, help_4)
                        #await bot.send_group_forward_msg(group_id=ev.group_id, messages=chain)
                        await bot.send_private_forward_msg(user_id=ev.user_id, messages=chain)
                        #await bot.send_private_msg(user_id=ev.user_id,message='请依次对你的bot私聊发送以下每一行内容（确保你的yunzai已经安装ws-plugin）。\n\n#ws添加连接\n\nko,1\n\nws://47.105.55.194:5021/ws,5,0')
                    else:
                        await bot.send(ev, '该主人已有bot或bot已被认领~')
                    session.close()
                    return
                except Exception as e:
                    hoshino.logger.error(f'gocq附件发送邮件失败：{str(e)}')
                    session.close()
                    #await bot.send(ev, '邮件发送失败了QAQ')
                    return


@sv.on_prefix('注销云冰祈')
async def logout_cloud_koinori(bot, ev):
    #if ev.user_id not in SUPERUSERS:
        #return
    message = str(ev.user_id)
    white_list = loadData(file_path)
    if message in list(white_list.keys()):
        botqq = white_list.pop(message)
        saveData(white_list, file_path)
        await bot.send(ev, f'bot({botqq})注销云冰祈了...')
    else:
        await bot.send(ev, '你还没有领养云冰祈...')
    return


def mail(receiver, content, attach_fp=None, attach_name='config.yml'):
    """
        发送邮件
    :param receiver: 接收者邮箱
    :param content: 正文内容
    :param attach_fp: 附件的文件位置
    :param attach_name: 附件文件名
    :return:
    """
    return
    email_host = "smtp.qq.com"
    email_port = 465
    email_sender = "2826417152@qq.com"
    password = 'yxtryaoqsrozdfag'
    email_receiver = [receiver]
    email_cc = [receiver]

    body_html = content
    msg = MIMEMultipart()
    msg.attach(MIMEText(body_html, 'plain'))  # 'plain'发送纯文本，'html'发送html格式文本

    if attach_fp:
        att = MIMEText(
            open(attach_fp, 'r', encoding='utf-8').read(), 'base64', 'utf-8')
        att["Content-Type"] = 'application/octet-stream'
        att.add_header("Content-Disposition", "attachment",
                       filename=("utf-8", "", attach_name))
        msg.attach(att)  # 添加附件

    msg["Subject"] = "请查收云冰祈的配置文件"  # 邮件主题描述
    msg["From"] = email_sender  # 发件人显示,不起实际作用,只是显示一下
    msg["To"] = ",".join(email_receiver)  # 收件人显示,不起实际作用,只是显示一下
    msg["Cc"] = ",".join(email_cc)  # 抄送人显示,不起实际作用,只是显示一下

    with smtplib.SMTP_SSL(email_host, email_port) as smtp:  # 指定邮箱服务器
        smtp.login(email_sender, password)  # 登录邮箱
        smtp.sendmail(email_sender, email_receiver,
                      msg.as_string())  # 分别是发件人、收件人、格式
        smtp.quit()
    print("发送邮件成功!")
