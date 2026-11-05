# 证据索引 / Evidence Index

大体积证据（数据包、点云、虚拟磁盘、工作区快照）**不入 git**，只在这里登记一行。
登记的每一条都必须能独立定位到实物：包名、体积、SHA256、存放位置、对应时点、对应 tag。

登记规则：

1. 冻结时点先打 tag：`git tag -a v0.x-YYYYMMDD -m "说明"` + `git push --tags`
2. 大件留在磁盘 / 移动硬盘 / 网盘，算好 SHA256
3. 在本文件末尾追加一行，四要素齐全：**包名、体积、SHA256、位置**
4. 需要取回时按“位置”一列去找，不要指望 git 里还有副本

---

## 一、已入库（历史遗留，仅此一个）

### `outputs/hunter_increment_since_20261021_20261031/`

2026-10-21 → 10-31 的“增量对账包”。笔记本侧生成，2026-11-05 随 `a8aba71` 入库。

| 项 | 值 |
|---|---|
| 仓库路径 | `outputs/hunter_increment_since_20261021_20261031/` |
| 入库提交 | `a8aba71 docs(outputs): 补充 2026-10-21→10-31 增量对账包` |
| 入库体量 | 360 文件 / 9.28 MB（台式机实测） |
| 磁盘原始体量 | 475 文件 / 250.32 MB（笔记本实测；其中 115 文件约 241 MB 被 `.gitignore` 排除，未入库） |
| 归档 SHA256 | `2778323963823f4a34439e81a00aa154d889f58a63498cd769800ce6ce85aa75`  ← `Hunter_增量_20261021至20261031.zip` |
| 生成脚本 | `build_increment.py`（17,774 B）、`verification.json`（903 B） |
| 最大单文件 | `20261021_MANIFEST.json`，4.85 MB（未触发 5 MB 闸门） |
| 最深路径 | 338 字符（`outputs/.../references/user_logs/.../ros_internal/2026-10-30-...-DESKTOP-P717CH9-440`） |

**保留理由**：它钉住了一段已无法从其他地方重建的历史，删除会削弱可追溯性。

**遗留问题**：本包本质是“整个工作区快照”，混入 `.planning/`、`references/ament/build.log`、`user_logs/`，
体积与深路径都远超需要。**不再生产同类包** —— 时点改用 tag 表达，
`.gitignore` 已屏蔽 `outputs/**/Hunter_increment_*/` 与 `outputs/**/项目增量/`，
`pre-commit` 也会拒收这两类路径与 >200 字符的路径。

如需彻底从历史中移除（会重写所有哈希，两台机器都要重新对齐）：

```bash
git filter-repo --path outputs/hunter_increment_since_20261021_20261031 --invert-paths
git push --force origin main
# 笔记本侧：git fetch origin && git reset --hard origin/main
```

当前判断：9.28 MB 不值得重写历史。若再出现第二个同类包，或仓库超过 300 MB，再执行上面的清理。

---

## 二、未入库（只登记）

| 包名 | 体积 | SHA256 | 存放位置 | 时点 / tag | 登记日期 |
|---|---|---|---|---|---|
| _（暂无）_ | | | | | |

---

## 三、相关约定

- 体积闸门：`.githooks/pre-commit`（单文件 > 5 MB 拒绝，> 1 MB 警告）
- 安装钩子：`git config core.hooksPath .githooks`（新机器克隆后执行一次）
- Windows 必备：`git config --global core.longpaths true`
- 实车验证记录：另见 [`docs/validation-log.md`](validation-log.md)
