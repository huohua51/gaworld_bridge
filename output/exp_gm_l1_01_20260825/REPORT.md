# EXP-GM-L1-01

- status：stopped_at_direct_gate
- measurement_result：pass
- Direct Coverage：1.0；FullPass：5/6；StrictPair：2/3
- 失败格：`l1_01_specimen_log_001` intervention，未删除
- Multi 未跑；interruption_recovery_result：N/A

## 失败性质

第三题 control 能生成 `checksum` / `count` / `seal`。intervention 在第一阶段已作为时间线事实给出后，没有沿用该产物继续生成后续依赖字段。

```yaml
failure: completed_stage_output_not_consumed
symptom:
  validation: {}
  archive_missing: seal
```

这把状态续接、校验计算和结构化产物生成叠在一起。直接进入 Multi 无法区分：B 没读懂检查点、读到了但不会算校验字段、还是交接上下文让输出退化。因此停止。

第三题退役为 `retired_after_direct_gate`，原因 `downstream_dependency_generation_confounds_recovery_construct`。原 L1-01 结果全部保留。下一步 `EXP-GM-L1-01b`。

**不能说：** GAWorld 中断恢复失败；Direct 5/6 四舍五入通过；可以开始解释 Multi。
