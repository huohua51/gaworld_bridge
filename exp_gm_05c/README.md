# EXP-GM-05c Equal-budget full workflow on L1

共同 v1 初稿分叉到 Single / Multi / Drop。v2 在初稿生成后才发布。L1 题来自已冻结的 05b，不要改。

```bash
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05c.rule_controls
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05c.freeze
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05c.run --repeat-id 0
```

只有 repeat 0 脱离地板和天花板才补 54 格。不建留出题，不开 04f。
