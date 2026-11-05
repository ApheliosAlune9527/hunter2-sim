# HUNTER 2.0 个人科研仿真项目

目标是在个人电脑上建立可重复的导航与强化学习实验平台，再根据实验结果决定后续研究和实车验证。

- [当前阶段、实际结果与六阶段路线](outputs/hunter_research_platform_20261031/README.md)
- [台式机恢复与环境验证](outputs/hunter_desktop_restore_20261031/README.md)
- [默认暂停的完整模型入口](sim/README.md)
- [原笔记本交接与历史边界](outputs/hunter_sim_handover_20261031/仿真进度与台式机交接.md)

当前项目路径为 `D:\rob-memory`，WSL 路径为 `/mnt/d/rob-memory`，Ubuntu 用户为 `aphelios`。已完成恢复、基础虚拟运动与传感器子测试，并确认采用个人 `155236` 地图制作实验室场景候选。完整实验室导航基线和强化学习尚未验收。

实车运动必须由用户明确下令，并在执行前提醒并等待授权；小车共用工作区只读。

## 跨机器同步（GitHub 作为中转）

版本库只含**代码 / 配置 / 文档 / 小型证据**（约 18 MB）；
点云、WSL 虚拟磁盘、历史知识库、构建缓存全部由 `.gitignore` 排除，留在这台机器上。
磁盘上的 13 GB 仍然是完整工作区，不进 git 不等于删除。

- **台式机（仿真调试）**：`git pull --rebase` → 改 → commit → `git push`
- **笔记本（实验室）**：开工前 `git pull --rebase`；联调通过后把参数改动提交上去
- **小车（实车验证）**：从笔记本 `rsync`，或车端有网时直接 `git pull`；只读部署
- **每次上车验证**：先 push，再 `git tag -a v<x.y>-robot-ok`，并记一行 [docs/validation-log.md](docs/validation-log.md)

换行统一为 LF（见 `.gitattributes`），Windows 上的 `core.autocrlf=true` 不会污染 Linux 侧脚本。

### Windows 上必须先设的两项（否则 pull 会失败）

仓库里有超过 300 字符的深层路径（`outputs/hunter_increment_since_20261021_20261031/...`），Windows 默认 260 字符上限会让 `git pull` 直接报 `Filename too long` 并中止：

```powershell
git config --global core.longpaths true
```

GitHub 在本机直连不稳定（实测会 `Connection was reset` 或 21 秒后超时），走本地代理可用：

```powershell
git config --global http.https://github.com.proxy http://127.0.0.1:7897
# 代理没开时改走直连：
# git -c http.proxy= -c https.proxy= pull
```

## 提交前体积闸门（`.githooks/pre-commit`）

git 不会同步 `.git/hooks`，所以钩子**不会自动生效**——每台机器克隆后执行一次：

```bash
git config core.hooksPath .githooks
```

规则：单文件 **>5 MB 拒绝提交**，>1 MB 只警告；`*.vhdx / *.vdi / *.vmdk / *.iso` 不论大小一律拒绝。
阈值可用 `HOOK_MAX_BYTES` / `HOOK_WARN_BYTES` 覆盖，确需强行提交用 `git commit --no-verify`。

