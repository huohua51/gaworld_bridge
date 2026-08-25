# CAL-GM-L1-RESUME-01

只回答：给定有序步骤和已完成步骤，Coordinator 能否稳定选择第一个尚未完成的步骤，既不重复，也不跳步。

不覆盖 L1-01b，不用 L1 原题。Coordinator 不能代执行。环境不能改输出。

```json
{
  "completed_steps": ["step_1"],
  "resume_step": "step_2",
  "remaining_steps": ["step_2", "step_3"]
}
```

control：检查点 outputs 只含已完成步骤。
intervention：completed_steps 仍只有第一步，但 outputs 带有后续步骤键（离心转子实测干扰）。续做位置必须仍是第二步。
