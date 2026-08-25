# EXP-GM-05 Equal-budget multi-agent value

评测的是 GAWorld 的多 Agent 组织方式，不是给 GLM 排名。

不使用 typed-patch、04e 三道开发题、或 04d/04e 留出题。审核契约是已经能改真实产物的 `required_change`。

## 运行顺序

```bash
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05.rule_controls
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05.freeze
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05.run --repeat-id 0
```

repeat 0 的预注册门：

- A：R0/Coverage 失败 → 修 harness，不解释模型
- B：Single 与 Multi 全满分 → 冻结为正控，换更难题，不补重复
- C：两轨都很低 → 先看共同首错
- D：出现差异且 R0 有效 → 补 repeat 1 和 2

```bash
PYTHONPATH=gaworld_eval_bridge:GAWorld python -m exp_gm_05.run --repeat-id 0 --fill-repeats
```

报告写 `repeat_id=0/1/2`，不声称 token 级种子复现。
