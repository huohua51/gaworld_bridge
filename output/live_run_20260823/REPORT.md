# 真模型第三拍：eval_mode 城市日已完成，并补了 WorkAdapter 真产物

- 时间：2026-08-23T02:54:11.379730+00:00
- 通道：Paratera `GLM-4-Flash`
- 目录：`/home/wuxingye/projects/gaworld_eval_bridge/output/live_run_20260823`

## 已完成

| 轨 | 结果 | 能说什么 |
|---|---|---|
| LLM ping / 结构化 Pair × 3 | 覆盖 1.0，Mean TaskScore 0.5，FullPass Rate 0 | 能力 Oracle；保留工资三次锁死 |
| 真访谈 JSON 契约 | Agent 4，FullPass=1 | 只证明可测量，不证明诚实 |
| eval_mode 1 日 × Agent 4/5 | `measurement_valid=1 diaries+state 齐` | 城市 run 的 P0/R1，无 Oracle，不可排名 |
| 真模型 WorkAdapter R1 | `coverage=1.0 full_pass_rate=1.0` | 合法产物门，不是 Task Competence |

### eval_mode 城市日

- coverage：1.0
- FullPass Rate：1.0（本轨没有 R2 Oracle，不得当能力分）
- ranking_eligible：False
- note：Sealed eval_mode city_run. P0/R1 only. No Oracle, no attribution split, not a model leaderboard.

- instance：`live_run_20260823_agents_4_5_day1` status=`scored`
- 日记字数：{'agent_4': 726, 'agent_5': 712}
- state 行数：880
- 归因：{"agent_caused_success": "not_enabled", "environment_assisted_success": "not_enabled", "system_success": true, "reason": "override event stream not written; only disable-flags + refused fallback"}

| gate | passed | detail |
|---|---|---|
| execution_valid | True | run.log has 模拟完成 |
| run_manifest_present | True | /home/wuxingye/projects/gaworld_eval_bridge/output/live_run_20260823/sim/run_manifest.json |
| eval_mode_enabled | True | {"enabled": true, "disable_dynamic_behavior": true, "disable_routine_change": true, "disable_diary_fallback": true, "strict_interview_json": true, "write_run_manifest": true, "unique_intervention_paths": []} |
| dynamic_behavior_off | True | False |
| routine_change_off | True | False |
| diaries_nonempty | True | {"agent_4": 726, "agent_5": 712} |
| state_csv_present | True | rows=880 |
| no_diary_fallback_in_log | True | [] |

### WorkAdapter 真产物

- coverage：1.0
- FullPass Rate：1.0
- Mean TaskScore：1.0
- note：Live GLM-4-Flash WorkAdapter R1. Legal deliverable only; not Task Competence / FullPass of a work workflow.

| instance | FullPass | TaskScore | status | 产物 |
|---|---|---|---|---|
| content_md_article | 1 | 1.0 | scored | article.md |
| teaching_lesson_plan | 1 | 1.0 | scored | lesson_plan.md |
| code_py_script | 1 | 1.0 | scored | main.py |

## 仍未做（按文档验收，不要写成已完成）

- 输入层 `intervention_audit.json`（requested / applied / 未登记外生 diff）
- 七文件最小证据包（现在只有 `run_manifest.json` + 工厂 cell）
- `environment_overrides.jsonl` 与三归因量
- `compare-event` / `personal-what-if` 真模型双轨（会再开两整天仿真，本拍没开）

