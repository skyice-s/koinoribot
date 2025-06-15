# KoinoriBot（维护版）
![Python Version](https://img.shields.io/badge/python-3.8+-blue)
[![试用群](https://img.shields.io/badge/试用/一群-冰祈杂谈总铺-brightgreen)](https://jq.qq.com/?_wv=1027&k=o3WzKAfn)
[![试用群](https://img.shields.io/badge/试用/二群-冰祈杂谈分铺-brightgreen)](https://jq.qq.com/?_wv=1027&k=fdFbP60u)


## 部署方法

> - 下载HoshinoBot仓库
> - 下载本仓库，将koinoribot文件夹解压至 `hoshino/modules` 里。
> - 安装python3.8.0
> - pip安装 `requirements.txt` 内的所有依赖（直接装koinoribot里的就行，已涵盖HoshinoBot/requirements.txt中的所有依赖）。
> - 将`hoshinobot/hoshino/config_example`文件夹更名为`hoshinobot/hoshino/config`
> - 在 `hoshino/config/__bot__.py` 中的 `MODULES_ON` 里新增一行 `"koinoribot",`。

<details>
 <summary> 注意事项 </summary> 

 - 如果在安装依赖的过程中出现错误，请务必及时解决，通常都可在百度上找到解决方案。
 
 
 - 关于部分插件需要用到的静态图片资源文件与字体文件，恕不在此公开。如有需要可以移步[![插件试用群](https://img.shields.io/badge/插件试用-冰祈杂谈分铺-brightgreen)](https://jq.qq.com/?_wv=1027&k=fdFbP60u)。
 
 
 - 部分功能需要申请api，请将相应的api填进 `koinoribot/config.py` 里以正常使用插件。
 
 
 - 部分功能如 `语音版网易云点歌` 需要用到`ffmpeg`，在[官网](https://ffmpeg.org/download.html)下载后解压至任意位置，并在环境变量`Path`中添加`ffmpeg.exe`所在路径。
 
 
 - 部分插件在下载图片时需要走代理，可以在 `koinoribot/config.py` 的 `proxies` 栏内进行配置。推荐使用 [clash](https://github.com/Fndroid/clash_for_windows_pkg)
</details>



<details>
 <summary> 关于如何安装hoshino </summary> 

- 仓库传送门 [Hoshinobot](https://github.com/Ice9Coffee/HoshinoBot) (作者： [Ice9Coffee](https://github.com/Ice9Coffee))

</details>


## 个人部署环境参考
 - 服务器：Windows Server 2019
 - Python版本：3.8.0
