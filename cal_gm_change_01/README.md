# CAL-GM-CHANGE-01

跨任务协议校准：当前值已满足时能否 keep，冲突时能否 update。

不使用 N1 / T3 / OA-02 / GM-01/02/05 原题。无通信、Reviewer、文件生成。

Rule 过门后才跑 seed0（3×2×1=6 格）。预注册门：Coverage / KeepAccuracy / UpdateAccuracy / EvidenceGroundingRate = 1。全过再补 18 格。control 全部乱 update 则停止，不继续调这三道题。

## 结果

`status: development_pass`。18 格 Coverage / KeepAccuracy / UpdateAccuracy / EvidenceGroundingRate = 1.0，FalsePositiveRevisionRate = 0。报告：`output/cal_gm_change_01_20260825/REPORT.md`。

这还不等于 N1/T3 已修复，也不建留出。下一步才是把该协议接入 N1-v2 / T3-02 做同题回归。
