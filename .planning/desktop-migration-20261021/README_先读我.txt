rob-memory 完整迁移包（Windows -> Windows，2026-10-21）

目标电脑已由用户确认：Windows 用户目录 C:\Users\ASUS，项目目录 D:\rob-memory。
本包用于用户通过 ToDesk 自行传输。包内含私密对话、附件和个人配置，请作为个人备份保存。

1. 用 ToDesk 传什么
传送完整的 rob-memory_迁移包_20261021.zip，以及同目录的 .sha256 校验文件。
台式机建议保存到 D:\迁移接收。ZIP 里有十余 GB 的展开内容，请留足“压缩包 + 解压后文件 + 恢复副本”的空间。
在台式机右键 ZIP -> 全部解压，打开其中的 rob-memory-migration 文件夹。

2. 包里包含什么
- rob-memory：整个 F:\rob-memory 的普通文件，包括项目文档、地图、知识库、模型、全部输出、临时资料及 Ubuntu 虚拟磁盘；这些文件按源字节保存。
- user-profile\.codex：Codex 本地会话、归档会话、附件、记忆、技能、插件、配置和一致性数据库快照。
- user-profile\.agents：自定义技能和角色说明。
- app-supplement：应用画布数据、少量首选项的补充副本。
- original-codex-metadata：修改迁移路径前的原始运行元数据，便于回退核对。
- MANIFEST.json：文件尺寸、SHA256、快照时间、数据库检查结果、排除项和路径适配记录。

本包针对 rob-memory 项目。其他项目（例如 cli-progress、桌面项目）的独立源文件不属于 F:\rob-memory，未自动搬入；Codex 本地记录则统一备份。
登录凭据、Windows 沙箱、浏览器 Cookie/账号库、临时缓存、锁文件、诊断日志和待执行队列不迁移。台式机重新登录后会生成适合新电脑的环境。
两个 PPT 构建目录的 node_modules 是指向旧电脑应用依赖的目录链接，未展开打包；成品、源码和链接清单均保留，需要再次构建时由新 Codex 接入自己的依赖。
Roaming 中正在使用的浏览器 LevelDB 不作为可恢复数据库复制；Codex 主会话数据库已另做 SQLite 在线备份。

3. 恢复 Windows 项目和 Codex
先在台式机安装并运行一次 Codex，然后彻底退出 Codex/ChatGPT 桌面应用及 Codex 终端。
本包的运行元数据副本已将当前项目关联到 D:\rob-memory，并把个人状态文件路径改到 C:\Users\ASUS。
在解压后的 rob-memory-migration 文件夹空白处右键“在终端中打开”，在 PowerShell 中执行：

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Restore-Windows.ps1

脚本只针对 D:\rob-memory、C:\Users\ASUS\.codex 和 C:\Users\ASUS\.agents 恢复。
目标已有目录会先改名为 .before-migration-时间，不删除原有台式机数据；原有 auth.json 等新机身份信息会保留。
原台式机聊天会留在该备份目录，本脚本不把两台电脑的数据库合并。
应用画布补充文件只填补目标没有的文件；不覆盖台式机浏览器配置或登录状态。
脚本会检查用户名，并阻止在旧电脑 Aphelios 用户下误运行。

4. 恢复 Ubuntu / ROS 2 / Gazebo 环境
项目里带有 wsl\Ubuntu22.04\ext4.vhdx，保存了原 Ubuntu 内部的安装软件及 /home/aphelios 工作区。
如果台式机还没有 WSL，在管理员 PowerShell 先执行：

wsl --install --no-distribution

按系统提示重启后，在解压后的迁移包目录执行：

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Restore-Ubuntu.ps1

这个脚本只注册虚拟磁盘。如果已有同名 Ubuntu，会停止以保护已有环境。
进入原 Linux 用户：

wsl -d Ubuntu-22.04 -u aphelios

Ubuntu 里的 /home/aphelios 路径保持不变。Windows 项目现在对应 /mnt/d/rob-memory。
手动加载个人仿真环境时使用：

source /mnt/d/rob-memory/wsl/hz_sim_env.bash

旧仿真脚本、配置或链接里仍可能引用 /mnt/f/rob-memory，需要在台式机按实际使用范围适配后再运行。
Windows 原始项目及历史验证文件保持原字节，未进行整目录替换；不要无差别修改历史日志、聊天正文或 .sha256 证据。
新台式机 GPU 与笔记本不同，显卡驱动和 NVIDIA 选择设置需要复查。
上述恢复步骤不运行任何机器人硬件、底盘、导航或仿真程序。

5. 恢复后检查
登录原 Codex 账号，检查 rob-memory 项目、旧聊天、关键附件是否可打开，文件目录是否为 D:\rob-memory。
检查 Ubuntu 能否通过 aphelios 用户进入；先核对个人路径和图形配置，再继续此前工作。
这是本地快照恢复方案，实际聊天显示、插件登录和跨版本兼容性需在台式机上验证。
Codex 快照在打包期间生成，本次打包对话在快照完成之后产生的消息不包含在快照中；此前记录按快照保存。
确认台式机工作正常之前，保留旧电脑原件和完整 ZIP。

校验（可选，推荐传输完成后执行）：
Get-FileHash -Algorithm SHA256 -LiteralPath 'D:\迁移接收\rob-memory_迁移包_20261021.zip'
把输出与 .sha256 文件中的值对照。

参考：
https://learn.chatgpt.com/docs/config-file/config-advanced#config-and-state-locations
https://learn.microsoft.com/en-us/windows/wsl/basic-commands#import-a-distribution-in-place
