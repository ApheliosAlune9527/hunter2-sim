# outputs 目录盘点（2026-11-18）

范围：`D:\rob-memory\outputs` 下全部 74 个目录、4 个 tar.gz。只做识别，不删除任何东西。

## 怎么扫的

| 脚本 | 作用 |
|---|---|
| `tmp/scan_outputs.py` | 每个目录的顶层条目、空目录、0 字节文件、精确重复文件（≤2 MB） |
| `tmp/refcheck_outputs.py` | 每个目录名在仓库 3,695 个文本文件里被引用多少次（跳过增量快照、`.git`、`tmp`） |
| `tmp/dir_sizes.py` | 按长路径统计真实体积（`Get-ChildItem` 会静默漏掉 node_modules 的深层路径） |
| `tmp/dup_summary.py` | 排除增量快照后的重复文件汇总 |

**总量 1,111.3 MiB / 19,721 个文件。** 其中 716.34 MiB（64%）是两份逐字节相同的 npm 工具链。

## 结论先说

- 真正「过时不用」的很少：2 份重复的 `node_modules`、5 个没有产出的空跑轮次、1 个已作废的补丁包。
- 其余旧目录都是**历史证据或运行依赖**，按 2026-11-05 那次审计的立场，不按日期删除。
- 文档层面有 11 份明确过时，需要补一句「已被谁取代」。

---

## A. 建议删除（作废或无产出，共约 716.6 MiB）

| 目标 | 体积 | 依据 |
|---|---|---|
| `weekly_mapping_ppt_20261014/.build/node_modules` | 358.17 MiB / 8,529 文件 | 与下面那份逐字节相同；`.gitignore` 已忽略 `**/.build/`，不在 git 里；PPT 成品在 `deliverables/`，`create_deck.mjs` 仍在同级，重做时 `npm install` 即可 |
| `group_meeting_20261020/.build/node_modules` | 358.17 MiB / 8,529 文件 | 同上，`export_pptx.mjs` + `presentation.json` 仍在同级 |
| `agentvln_reverse_dock_20261110_013316_amcl` | 0.05 MiB / 26 文件 | 无 `report.json`、无观测图；`sim/experiments/agentvln_reverse_dock/README.md` 记录的调试轮从 01:33:48 开始，没提这一轮；0 引用 |
| `agentvln_reverse_record_20261110_015644` | 0.03 MiB / 8 文件 | 无 `report.json`、无观测图，只有启动日志；0 引用 |
| `agentvln_reverse_record_20261110_022642` | 0.03 MiB / 7 文件 | 同上 |
| `agentvln_reverse_record_20261110_040254` | 0.05 MiB / 26 文件 | 同上（逐节点日志齐全，但没有结果） |
| `agentvln_reverse_record_20261110_040825` | 0.38 MiB / 13 文件 | 无 `report.json`，只有 `gui_check_*.png` |
| `car_nav_fix_20261108/` | 0.01 MiB / 2 文件 | 用户 m07362 明令不改共用小车配置，该参数补丁已作废；0 引用 |
| `car_params_patch_20261108.tar.gz` | 3.5 KiB | 同一个补丁包 |

删完 outputs 约剩 **394 MiB**。剩余 41 MiB 重复几乎都在 `agentvln_*` 的观测帧（`depth.npy`、连续 `observation_*.png`）和建图 PNG 里，属于数据集内部重复，不建议动。

## B. 过时但属于历史证据（保留，最多在文件头加一句「已被谁取代」）

| 目录 | 体积 | 说明 |
|---|---|---|
| `hunter_nav2_recovery_20261029` | 0.02 MiB | 10-29 重启恢复命令，被 11-08 验证过的 `Nav2导航命令.txt` 取代 |
| `car_nav_fix_20261107` | 0.14 MiB | 11-07 参数包（含已撤回的 footprint/allow_unknown 改动）；`实车导航命令清单.txt` 被 11-08 版取代，`lab_odom_06_fix.yaml` 等仍可查 |
| `hz_nav_preparation_20261018` / `hz_nav_reference_adaptation_20261019` | 0.05 / 0.07 MiB | 实车导航准备早期版本，被 `hunter_nav2_personal_launch_20261109` 取代 |
| `hunter_nav2_shortcuts_20261108` | 0.03 MiB | `Nav2导航命令_简版.txt` + `hznav.bash` 被 11-09 打包入口取代；**同目录的 `Nav2导航命令.txt` 是验证过的完整参考，整个目录保留** |
| `hunter_nav2_append_20261027` | 36.57 MiB（`.build` 33.77） | 10-27 组会 PPT；`.build/source.json` 18.8 MB + `combined.json` 16.6 MB 是中间产物，可再回收 33.77 MiB，但会失去重建该 PPT 的能力 |
| `hunter_nav2_refined_20261028` / `group_meeting_20261020` / `weekly_mapping_ppt_20261014` | 2.40 / 3.51 / 8.03 MiB（删 node_modules 后） | 10 月组会成品（`.pptx`），属于历史交付 |
| `hunter_sim_execution_20261012` | 62.31 MiB | 含 `references/hunter_reference_20261013.urdf`，是运行依赖 |
| `map_inspection_lab_155236_20261011`、`map_inspection_20261011`、`mapping_evidence_20261012`、`raw_pcd_preview_lab155236_20261013`、`cloudcompare_guide_20261011`、`senior_mapping_method_20261016`、`hz_mapping_handover_20261015` | 33.51 / 15.47 / 14.21 / 17.89 / 0.03 / 0.25 / 0.28 MiB | 建图阶段证据；`raw_pcd_preview_lab155236_20261013` 被 `weekly_mapping_ppt` 的 `create_deck.mjs` 读取，属依赖 |
| `floral-ring-v01` | 12.52 MiB | 3D 打印花环，另一个项目；建议**移到仓库外**，不要删 |
| `hunter_increment_since_20261021_20261031` | 9.28 MiB | `docs/evidence-index.md` 登记过，保留 |
| `storage_audit_20261105` | 0.47 MiB | 上一轮清理的审计记录 |

## C. 当前在用，不要动

- 仿真主线：`lab_nav_fix_20261106`（169 次引用）、`lab_nav_20261105`（65 次，旧基线，部分场景与文档仍指向）
- AgentVLN 主线：`agentvln_hunter_20261108_step1`–`step5`、`step5_unblock`、`vlm_deploy`、`agentvln_hunter_20261109_{contention,repro_check,slides,meeting,spl}`、`agentvln_hunter_handoff_20261111`
- 倒车停靠：`agentvln_reverse_dock_20261110_014756_amcl`（通过轮）与 5 个失败轮（`README.md` 各引 1 次，是失败模式的唯一证据）；`agentvln_reverse_record_20261110_{042000,043800,045651,050133,055500,060500}`（`050133` 被 `collect_slide_assets.sh` 取图，`045651`/`060500` 是通过轮）
- 实车入口：`hunter_nav2_personal_launch_20261109`、`car_map_20261108`
- 其他项目与依赖：`go2_edu_research_20261109`、`hunter_agent_handoff_20261105`、`hunter_model_upgrade_20261030`（`references/ament` 是运行依赖）、`hunter_research_platform_20261031`、`hunter_desktop_restore_20261031`、`hunter_sim_handover_20261031`、`hunter_sensor_parameters_20261030`、`hunter_imu_frequency_20261105`、`hunter_pcd_to_2d_20261029`、`hunter_model_update_20261030`、`hunter_sim_research_plan_20261012`、`rustdesk_direct_20261030`、`lab_map_compare_20261105`、`lab_scene_2d_20261105`、`lab_scene_odom06_20261105`

## D. 空目录与空文件

7 个空目录（可以直接删）：
`floral-ring-v01/__pycache__`、`hunter_nav2_append_20261027/.build/{append-render,final-render,source-render}`、`weekly_mapping_ppt_20261014/.build/{final-preview,preview,preview-v2}`

0 字节文件：`floral-ring-v01/preview-server.log`、`preview-server.pid`、`hunter_research_platform_20261031/motion_trials/*/transport.stderr.log`。
其余 572 个 `.log` 是各轮次的排查证据，不是缓存；另有 125 个 0 字节文件（多为失败的 `transport.stderr.log` 与占位文件），可以随空目录一起清掉。

---

## E. 文档层面：11 份明确过时

| 文件 | 现状 | 建议 |
|---|---|---|
| `README.md`（根） | 第 10 行仍写「完整实验室导航基线和强化学习尚未验收」，且指向的「当前阶段」文档停在 10-31 | 改写第 10 行，把入口换成当前主线（`lab_nav_fix_20261106` / `agentvln_hunter_handoff_20261111`） |
| `outputs/hunter_research_platform_20261031/README.md` | 阶段表写「4. 导航基线：未开始验收」「5. 强化学习：未开始」，实际 11-05 已跑完导航批量、11-06 已跑完 RL | 表头标注「本表停在 2026-10-31」，或补两行结果 |
| `outputs/lab_nav_20261105/README.md` | 没说明已被 `lab_nav_fix_20261106` 取代；里面的 9/9、6/9 是补丁前数字 | 顶部加一句「已被修正轮取代，数字仅作历史」 |
| `outputs/lab_nav_fix_20261106/NEXT_SESSION.md` | 「Start here tomorrow」停在 11-07，那次 run-through 已经做完 | 标为历史，或合并进 `STATUS.md` |
| `outputs/car_nav_fix_20261107/实车导航命令清单.txt` | 11-07 版，配合已撤回的参数补丁；11-08 的 `Nav2导航命令.txt` 与 11-09 的 `hz_nav_launch` 已取代 | 文件头加「已被取代」 |
| `outputs/hunter_nav2_recovery_20261029/Hunter_Nav2_本轮测试与重启恢复命令.txt` | 10-29 恢复流程 | 加「已被 11-08 验证版取代」 |
| `outputs/hunter_nav2_shortcuts_20261108/Nav2导航命令_简版.txt` + `hznav.bash` | 被 11-09 打包入口 `hz_nav_launch` 取代 | 简版文件头指向 `hz_nav_launch` |
| `docs/validation-log.md` | 只有 2026-11-05「首次入库」一行；10-28 低速到点、11-08 定位/规划/取消都没记 | 补两行（这是仓库自己定的规矩） |
| `outputs/hunter_agent_handoff_20261105/README.md` | 写「每轮只给当前一步、一条必要命令」，用户后来改成 1–2 条；也没指向 11-11 的 AgentVLN handoff | 补一句以最新要求为准 + 指向新的 handoff |
| `outputs/agentvln_hunter_handoff_20261111/AgentVLN_HUNTER复现要求与进度汇总.md` | 「截至 2026-11-09」，未包含 11-10 的倒车停靠验收 | 追加 11-10 一节 |
| `sim/experiments/agentvln_reverse_dock/README.md` | 末尾「2026-11-10 追记」断在「按」 | 补完最后一段 |

## 建议动作

1. 删 A 表九项（716.6 MiB）+ D 的空目录空文件——确认后我执行，删前再算一次 SHA256 清单留档。
2. 改 E 表里前六份的过时表述（只改说明，不改历史数字）。
3. `floral-ring-v01` 移到仓库外（`D:\projects\` 之类），不进 git 也不占 outputs。
