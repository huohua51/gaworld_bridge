# EXP-GM-C1-02

正式评测对象是 GAWorld 多智能体系统，不是 Direct、也不是 Single。组件修复通过不等于集体协调通过。

## 角色

* Agent A / Agent B：各持私有约束，必须自己执行分配。Coordinator 不能代执行。
* Coordinator：收报告、看冲突证据、提交联合方案。

## 事件链

```text
A、B分别读取私有约束
→ 分别提交初始可行集合
→ Coordinator形成初始联合方案
→ intervention中B收到一条私有约束修订
→ B发送最新约束
→ JointAssignmentChannel检查初始方案
→ 返回duplicate_resource_claim（若最新首选冲突）
→ Coordinator调用propose_joint_assignment
→ A、B确认同一版本
→ A、B分别执行
→ Scorer根据真实占用表计算最终状态
```

## 轨道

| 轨道 | 定位 |
| --- | --- |
| Direct | 新题可做性校准，非正式结果 |
| Full Multi | 正式评测对象 |
| Drop Revision | 只丢 B 的最新约束修订；control 应成功，intervention 应失败 |
| Drop Coordinator | A/B 信息送达，最终方案不交付 |

## 题目

实验台窗口、温室灌溉阀、冷库装卸。不用 C1-01 / COMP-01 / REPAIR-01 原题。无人机起降坪因 Direct 不可做已退役，不进入正式三题。

规则：先给高优先级分配 preferred；再给低优先级按其可行集列表顺序选第一个空闲时段。禁止分配不在可行集中的时段。
