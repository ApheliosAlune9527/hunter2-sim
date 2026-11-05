# 修订依据

- 旧清单把安装前提和 Windows 查看放在另一个 Markdown 文件中，初次使用者需要来回查找。
- 主 TXT 应包含真实安装命令与 PS1 含义，使用“在解压目录地址栏输入 powershell”确定本地工作目录，避免写死某个 Windows 盘符。
- Ubuntu 命令保持每个终端两行 source + ros2 launch，实际检查继续由原有 launch 和会话工具承担。
- 新主说明必须使用本轮动态输出目录，不引用某次日期地图、特定 PNG、组会 PPT。
- 采用名称 hz_mapping_tools，仍仅新增到 /home/car/hz_ws 内。目标已存在且内容不同时仍拒绝覆盖。
- 用户已批准进行完整收尾并明确本轮离线；本次是名称与交付说明修订，不重复询问设计或连接权限。

## 2026-10-16 异地 ToDesk 实际验证与说明书修订依据

- 用户确认 Windows 在校园网、小车在实验室网络，未使用过 Tailscale；默认流程改为 ToDesk 文件传输，不要求 SSH 可达或配置 VPN。
- ToDesk 官方说明：涉及 Linux 时使用文件传输框。参考：https://todesk.com/helpcenter/questions-147.html 。不依赖 Win-Win 的拖拽或复制粘贴文件能力。
- 用户已将原始 hz_mapping_tools.zip 传入个人新目录，SHA256 为 c62919992ce9a77fb5c60d5d1c1ddb35cfabfef780121979e0a049d1dc0e0204；通过原 zipapp 安装器安装，已有工程未改写。
- 用户回传真实 doctor 输出：fast_livo、hesai_ros_driver、realsense2_camera 路径正确，helper SHA256 一致，ROS launch API 兼容；当前轮 lab_20261013_195244_610187，PCD 为 0，个人状态为空，预检通过并正常退出。
- 实车证据仅涵盖安装、source 和 doctor。尚未通过新入口验证各传感器、mapping、watch、实际采集和 ToDesk 地图回传，不将这些写成已完成。
- 第 11 节也需替换 SSH 下载前提：ToDesk 传回 pack 的 tar.gz 与 latest_export.json，然后在 Windows 使用原 pcd_export.py 校验、解包、合并。

### 用户要求重新尝试原 SSH 路径

- 在旧使用说明及 hunter_sim_execution_20261012 的历史查询记录中找到曾使用的地址 192.168.31.204；没有据此推定当时 Windows 所在网络或代理状态。
- 当前默认路由访问 192.168.31.204 与 10.13.1.166 均经过 Meta，源地址 198.18.0.1。默认连接可被接受，但没有收到有效 SSH 服务端标识。
- 使用 ssh -b 10.135.123.92 对两个候选地址做非交互只读测试，都在 TCP 连接阶段超时。
- 依据 Microsoft 官方 IP_UNICAST_IF 文档及本机 SDK 常量 31，用只影响单个测试套接字的选项指定 WLAN（ifIndex 21）再次测试，两个地址 TCP 连接仍超时；默认模式则为 Meta 接受后握手失败。没有认证或修改任何网络配置。
- 原理依据：https://learn.microsoft.com/en-us/windows/win32/winsock/ipproto-ip-socket-options 。这些结果说明直接 SSH 尚未可用，不能仅凭不同子网或代理存在就断定唯一根因。
- 用户补充：上次成功传输时也开着代理。保持代理原样，不将“开代理”本身当成根因，不执行 TUN 开关对照。
- 小车当前路由仅一条默认出口：via 192.168.31.1 dev wlp129s0f0；10.13.1.0/24 仅在 radarConnection 上有直连路由。指定源 10.13.1.166 发往 Windows 10.135.123.92 仍走 Wi-Fi。这里只能提出回程路径线索，不据此断言故障位置。
- Windows 无线事件 8001 只读查询（客户端北京时间）：2026-10-11 11:50、14:58 连接 225_5G；18:15、18:19 后转为 SXU；当前 WLAN 连接名也是 SXU。两份地图压缩包 Windows 创建时间分别为当天 14:25、16:02，合并文件创建时间与其紧接。
- 网络记录与文件时间显示成功下载时与当前无线网络有差异；下一步只读核对小车当前 Wi-Fi 名，确认 225_5G 是否为其所在实验室网络。未读取 Wi-Fi 密码或更改任一网络配置。
