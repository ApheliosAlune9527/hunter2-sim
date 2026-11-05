# RustDesk 直连配置记录

2026-10-30，Windows 上运行 Clash Verge Rev 2.5.8，用户请求 RustDesk 不使用代理。检查时 Clash 为 `global` 模式，系统代理启用、TUN 关闭，RustDesk 路径为 `C:/Program Files/RustDesk/RustDesk.exe`。

已将 `PROCESS-NAME,RustDesk.exe,DIRECT` 写入 Clash 的全局扩展脚本 `profiles/Script.js`。原脚本备份为本目录的 `Script.js.before`。当前订阅对应的自定义规则中额外前置了同一进程规则和 `MATCH,GLOBAL`；后者用于在切换到规则模式时，让其他未匹配流量继续使用当前 GLOBAL 策略，但也意味着该订阅后续原有规则会被遮蔽。原规则文件备份为本目录的 `profile_rules.before.yaml`。

独立本机回环测试验证了：全局模式忽略进程规则；规则模式下同名测试进程匹配直连，其他测试进程继续交给 GLOBAL。测试完全使用单独的代理核心与本机回环监听，不访问小车、不修改现有连接。该测试不能证明 RustDesk 在用户网络上的连接问题已经解决。

用户打开 Clash 窗口后，已通过界面重新激活当前订阅并切换至规则模式。运行中的规则页面显示第一条 `ProcessName / RustDesk.exe / DIRECT`，第二条 `Match / GLOBAL`。使用仅连接本机 HTTP 服务、进程名为 `RustDesk.exe` 的 curl 副本测试时，Clash 活跃连接页面显示其命中 `ProcessName(RustDesk.exe)` 和 `DIRECT`；原有其他代理连接显示 `Match` 并继续使用此前的 GLOBAL 节点。测试返回成功，未控制实际 RustDesk，未连接小车。

用户随后反馈在 Clash 开启的情况下使用 RustDesk 已连接小车。当前 TUN 关闭，系统代理模式不一定接管 RustDesk 的原生 UDP 等连接，因此这一结果证明本次连接成功，不能单凭它判断原连接失败的具体原因。

恢复：将对应备份分别复制回 Clash 的 `profiles/Script.js` 和当前订阅的规则扩展文件，重新应用订阅；是否恢复全局模式由用户决定。不要修改或删除其他订阅与配置。
