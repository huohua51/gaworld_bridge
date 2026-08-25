# CAL-GM-APPLY-01

只测完整落实修改。Reviewer / 决策由 Rule 提供，模型只做 Executor。

三道新题：主阈值与备用阈值、工作日时限与周末时限、普通容量与应急容量。不使用 T3 原题。

Rule 过门后才跑 seed0（3×2×1=6 格）。Scorer 读取真实文件。

## 结果

`status: development_pass`。18 格 FieldAdoptionRate / CompleteChangeAdoptionRate / HiddenTestPass = 1.0，PartialChangeRate / UnregisteredChangeRate / AcknowledgementExecutionGap = 0。报告：`output/cal_gm_apply_01_20260825/REPORT.md`。

与 CHANGE-01 联合：单组件均能做。T3-02 未建。
