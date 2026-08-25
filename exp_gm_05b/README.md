# EXP-GM-05b F5 identifiability calibration

L2 复合题已冻结。本实验找中间难度 L1：先 Direct，再固定初稿审核。

```bash
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05b.rule_controls
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05b.freeze
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05b.run_direct
# Direct 过门后再：
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05b.run_review --repeat-id 0
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05b.run_review --repeat-id 1
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05b.run_review --repeat-id 2
```

正式报告：`output/exp_gm_05b_20260824/REPORT.md`。不要改 L2 任务。不要因为看到过 Executor 出错就开 04f。
