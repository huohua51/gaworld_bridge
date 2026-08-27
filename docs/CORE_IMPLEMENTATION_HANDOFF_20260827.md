# C1 / REL1 核心实现问题交接（2026-08-27）

## 1. 交接范围

本文只负责把评测发现转成可实现、可验收的问题说明，不宣称已经修改或合并 GAWorld。
C1 与 REL1 的历史结果均保持冻结；后续核心代码由 GAWorld 开发同学处理，评测侧负责在新实验编号、
新任务表面和事前注册条件下验收。

| 问题 | 主要层次 | 当前证据 | 当前状态 |
| --- | --- | --- | --- |
| C1 保护优先级在 NACK 重试中丢失 | Agent 决策 + 平台不变量 | C1-02 至 C1-05 | 已定位，待核心实现 |
| C1 `plan_id/spec_version` 由模型参与握手 | 平台接口所有权 | C1-03 至 C1-05 | 已定位，待核心实现 |
| REL1 形成阶段忽略完整历史 | Agent 协议 | REL1、REL1-02、REL1-03 | 已定位，待协议实现 |
| REL1 更新阶段没有服从 `latest_is_binding` | Agent 协议 | REL1、REL1-02、REL1-03 | 已定位，待协议实现 |
| REL1 Dispatcher 证据 ID 可为空或自填 | 平台接口所有权 | REL1、REL1-02、REL1-03 | 已定位，待核心实现 |

## 2. C1：优先级重试与计划版本所有权

### 2.1 问题出在哪里

问题一是业务语义：发生资源冲突后，系统虽然会重新分配，但可能移动已被政策保护的高优先级 Agent，
而不是只重分配低优先级 Agent。这不是“完全没有协调”，而是重规划违反
`priority_preservation`。

问题二是接口所有权：模型曾在重试 JSON 中自行给出 `plan-002`，而注册允许值只有
`plan-001`。计划 ID 和规范版本属于平台状态，不应由模型生成、猜测或递增。若保护规则在首轮方案后
发生变化，旧方案还必须被视为旧规范下的审计记录，不能继续被当前规范确认。

核心实现关注以下位置和职责：

- `gaworld/work/coordination.py::JointAssignmentChannel.protect_assignment`：保护关系改变后推进权威规范版本，并清除当前可确认方案引用；
- `gaworld/work/coordination.py::JointAssignmentChannel.propose_joint_assignment`：先验证业务分配，只给通过验证的方案分配平台 `plan_id`；NACK 响应只返回违规事实和当前 `spec_version`；
- `gaworld/work/plan_registry.py::PlanRegistry`：平台单调生成 `plan_id/spec_version`；确认时拒绝旧规范方案；历史方案仍保留作审计证据；
- 模型输出契约：只允许提交 `{agent -> slot}` 业务分配，不允许提交 `plan_id` 或 `spec_version`。

平台不能替模型计算正确答案。正确行为是检查保护不变量并 NACK，给模型一次按公开违规事实重提的
机会；平台不能把 Oracle 目标时段直接塞回 Prompt，也不能静默修正 assignments。

### 2.2 是通过什么实验发现的

| 实验 | 关键结果 | 诊断贡献 |
| --- | --- | --- |
| `EXP-GM-C1-02` | 光学台 intervention 3/3 都移动受保护的 A | 首次稳定定位 `priority_preservation_violation` |
| `EXP-GM-C1-03` | NACK 3/3；语义正确重试 0/3；系统恢复 0/3；其中 2/3 使用未登记 `plan-002` | 把业务重规划错误与版本握手错误拆开 |
| `EXP-GM-C1-04` | 36/36 严格 JSON；FullPass 3/6；intervention 恢复 1/3；control 出现 1/3 伪 NACK | 平台管理 ID 后，传输问题消失，但 retry 仍会保留 A 的旧时段 |
| `EXP-GM-C1-05` | FullPass 4/6；intervention NACK 3/3、恢复 3/3；control NACK 0/3；平台所有权 5/6 | “当前规范是唯一权威”消除了本批次目标 retry 模式，但其他初始/控制错误仍使总 Gate 失败 |

对应证据：

- [`C1-04 RESULT`](../exp_gm_c1_04/RESULT.md)
- [`C1-05 RESULT`](../exp_gm_c1_05/RESULT.md)
- `output/exp_gm_c1_04_20260827/`
- `output/exp_gm_c1_05_20260827/`

因此目前只能说：“权威当前规范表述在 C1-05 的三个 intervention 中修复了已观察到的 retry
模式。”不能说 C1 已整体修复，也不能关闭 `AP-C1-D-01` 或 `AP-C1-F-01`。

### 2.3 建议怎么改与怎么验收

核心单元测试至少覆盖：

1. 未通过约束验证的 proposal 不产生可确认 `plan_id`；
2. 保护规则变化使 `spec_version` 单调前进，旧计划确认返回 `stale_plan_spec`；
3. 当前规范下通过验证的方案才可确认；
4. 高优先级 Agent 的受保护时段变化时返回结构化 NACK，不自动改方案；
5. 模型提交平台 ID 时明确拒绝；
6. 并发或重复确认不会把旧方案重新设为当前方案。

核心合并后，评测侧另建新编号和新任务表面，事前冻结模型、Prompt、评分器、调用预算与停止规则。
关闭条件不是“某个 intervention 修好了”，而是 coverage=1、所有 control/intervention 完整链均
FullPass，且平台 ID 所有权和优先级 NACK/retry 同时通过。

## 3. REL1：可靠性形成、最新绑定更新与动作证据

### 3.1 问题出在哪里

REL1 的注册语义分两个不同阶段：

- formation：统计每个来源在全部形成历史中 `report == outcome` 的次数，选择唯一较高者；
- update：当 `latest_is_binding=true` 时只看最后一条已核实结果，允许它覆盖旧多数。

原协议把两种规则混在一起，模型出现两类稳定错误：formation 默认选第一个来源或只看最后一行，
update 又继续沿用历史多数。二者是 Agent 协议问题，不应通过 GAWorld 自动选择“正确可信来源”来
掩盖；否则评测对象会被环境代做。

另一个问题是平台元数据所有权：Dispatcher 的业务职责只是依据已送达、已采用的 trust message
选择注册 value。`action`、`evidence_message_id`、`trust_version` 和 round 都应由平台从真实
delivery/adoption 状态绑定，不能让模型填写字符串 `None`、不存在的消息或旧版本。

核心实现建议围绕 `gaworld/comm/trust.py::TrustLedger`：

- 保持 TrustUpdater 私有读取历史、Dispatcher 无权读取历史、TrustUpdater 无权提交动作；
- 增加平台绑定入口，模型只传 `selected_value`；
- 平台验证 value 在注册集合中，消息已送达且已采用，round 一致，消息版本等于当前采用版本；
- 平台从私有 Dispatcher contract 和真实消息生成 action 名、证据 ID、版本与 round；
- 拒绝未送达、未采用、陈旧版本、错误 round 和非法 value；所有拒绝写入 trace。

Agent 协议侧应使用不同的 formation/update Prompt。formation 必须显式返回两个来源的计数和全部
支持 row IDs；update 必须只返回最后一行证据。Observer 必须逐项原样转发注册信号。生产系统可对
schema-invalid 响应设置有限重试，但正式 benchmark 仍应保留无替换的固定失败分母。

### 3.2 是通过什么实验发现的

| 实验 | 关键结果 | 诊断贡献 |
| --- | --- | --- |
| `EXP-GM-REL1` | 72/72 可测；FullPass 0.0833；Full 0；Focused 0.3333 | 定位旧多数不更新、默认来源 A、Dispatcher 证据 `None`；同时证明账本隔离、送达、采用和权限链可工作 |
| `EXP-GM-REL1-02` | coverage 4/6；可测 cell 中 formation 1/4、latest update 4/4、bound update action 4/4 | 证明 latest-only 更新与平台绑定方向有效；共享阶段 Prompt 污染 formation，Observer 两格漏报 |
| `EXP-GM-REL1-03` | 30/30 调用；coverage 5/6；五个可测 cell 全部 FullPass、所有注册语义率 1.0 | 分阶段 Prompt 后目标语义未再复现；唯一无效格把两个 source ID 输出为整数 `1`，属于模型 schema 失败 |

对应证据：

- [`REL1 原始报告`](../output/exp_rel1_20260824/REPORT.md)
- [`REL1-02 RESULT`](../exp_rel1_02/RESULT.md)
- [`REL1-03 RESULT`](../exp_rel1_03/RESULT.md)
- `output/exp_gm_rel1_02_20260827/`
- `output/exp_gm_rel1_03_20260827/`

REL1-v3 的五个有效 cell 是很强的修复方向证据，但预注册要求 coverage=1。由于第六格 schema
无效，`AP-REL1-01/02/03` 仍保持 open，不能用 available-case 结果替代正式 Gate。

### 3.3 建议怎么改与怎么验收

核心单元测试至少覆盖：

1. Dispatcher 不能读取 history，TrustUpdater 不能提交 action；
2. 未送达或未采用的 trust message 不能绑定动作；
3. v2 已采用后，v1 不能提交或覆盖；
4. wrong round、非法 value、空/伪造 message ID 均被拒绝；
5. 成功动作中的 action、message ID、version 和 round 全部来自平台状态；
6. 模型输出中不需要、也不接受平台绑定字段。

Agent 协议验收另用新任务表面，至少同时检查 exact Observer relay、formation 两来源完整计数、
latest-only update、两个阶段的业务 value 和两个平台绑定 action。正式关闭要求 6/6 或事前登记的
完整矩阵 coverage=1 且 FullPass=1；任何 schema-invalid cell 保留在分母内。

## 4. 交接边界与发布纪律

- 不修改、重算或覆盖 C1-02/03/04/05 与 REL1/02/03 的历史结果；
- 不把评测侧原型提交描述为 GAWorld 已合并能力；
- 核心修改必须由负责同学单独 review、测试和提交；
- 合并前先跑核心单元测试，合并后再由评测侧做新编号、事前注册的端到端回归；
- 只有新回归达到注册 Gate，才更新 action item 状态；单个场景、有效样本子集或离线 fixture 均不能关闭问题。
