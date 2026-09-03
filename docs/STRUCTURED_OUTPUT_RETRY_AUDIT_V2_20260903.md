# 结构化输出与重试审计 v2 实施记录

日期：2026-09-03
状态：代码完成；离线测试通过；完成三次小额工程探测；尚未启动新的正式 Benchmark 复跑

## 1. 为什么要做这次修改

T3 非代码双平台先导原本想比较 GAWorld 与 YuLan-OneSim 的审核链，但真实 GLM-5.2 运行出现了两个会混淆结论的问题。

第一，36 个模型响应中有 14 个把本来正确的 JSON 包在完整 Markdown `json` 围栏里。冻结的严格解析器必须把它们判为无效，因此主结果只有 GAWorld 0/6、YuLan 1/6；事后只去除完整围栏后，14/14 个响应都能解析，三类审核核心判断为 12/12 正确。由此可以排除“模型完全不会审核”，并把首要问题定位到模型输出与解析契约的接口缝隙。这个诊断不能用于事后改写原分数，因为那会改变已经冻结的评分规则。

第二，运行控制台出现过 TLS EOF 后的自动重试，但旧证据只记录一个 Benchmark 逻辑调用，看不到底层究竟发出了几个 HTTP 请求。这样既不能准确解释费用，也不能判断两个平台是否经历了相同的网络扰动。

因此，本次目标不是让旧结果变好看，而是让下一版实验能够回答三个不同问题：模型是否按业务要求作答、响应是否满足机器契约、一次逻辑调用实际经历了多少物理请求。

## 2. 通过什么办法确定问题位置

诊断采用了四层交叉核验，而不是只看最终分数。

1. 保留原始响应和严格解析结果，确认失败首先发生在 JSON 解析层。
2. 使用固定、保守的事后规则，只对“整个响应恰好是一个 `json` 围栏”的样本去围栏，确认 14/14 可恢复。
3. 恢复后重新核验 reviewer 的结构化决策，三类任务 12/12 与核验证据方向一致，说明业务审核能力和格式服从不能混成同一个指标。
4. 对照控制台的 TLS EOF 与证据文件，确认旧记录无法重建物理重试次数。

这组证据支持“接口与审计不足”这一较窄结论，但不支持事后宣称两个平台已经完成公平排名。因为独立抽样会让 reviewer 输出不同，进而造成 executor 提示分叉；下一轮还必须改用同一 payload 双平台重放。

## 3. 实现了什么

### 3.1 Provider-native 结构化请求

新增的 GAWorld 评测适配器接受 `response_format`，并原样放入 OpenAI-compatible 请求。既支持简单的 `{"type": "json_object"}`，也为以后使用网关支持的 JSON Schema 保留了透传能力。

这一步解决的是“尽量让提供方在生成阶段遵守结构”，但它不是验证器的替代品。返回内容仍然必须经过 JSON 解析和任务级字段校验。

### 3.2 保守且可审计的围栏规范化

新 runner 提供两个显式模式：

- `strict`：默认值；不做任何围栏修复，保持旧实验语义。
- `single_json_fence`：只接受整个去除首尾空白后的响应恰好由一个带 `json` 标签的围栏包裹；拒绝前缀、后缀、无类型围栏和多个围栏。

启用规范化时，同时保存原始文本、原始 SHA-256、规范化文本、规范化 SHA-256、规则版本和是否实际应用。研究者可以重建变化，而不是只看到清洗后的答案。

### 3.3 逻辑调用与物理尝试分开计数

每次底层请求都生成 `model_transport_attempt` 事件，记录：

- 它属于哪个 `call_id` 和 `evidence_id`；
- 第几次尝试及最大尝试数；
- 成功与否、是否可重试、是否实际继续重试；
- 起止时间、延迟、错误类型、Provider 和 fallback 位置。

`ModelCallBudget.calls_used` 仍只计算 Benchmark 逻辑调用；新增的 `transport_attempts_observed` 和 `transport_retries_observed` 单独描述实际网络请求。这样不会把一次 TLS 重试误算成两个独立样本，也不会再隐去额外请求。

### 3.4 失败和凭证安全

写证据前采用字段白名单。未知字段即使名为 `api_key` 也会被丢弃；第三方异常的原始文本不进入持久化证据，只保留异常类型和重试判断，避免异常消息意外回显请求头或凭证。集成测试使用一个专门的假 Key，并断言它没有出现在 JSONL 中。

### 3.5 版本隔离

旧 T5-v3 预注册对 `benchmark_core/model_runner.py`、GAWorld `config.py` 和 `llm_providers.py` 做了哈希密封。开发中曾直接修改这些文件，完整测试随即正确报告 4 个哈希不匹配。没有更新旧注册哈希来掩盖变化，而是恢复三份密封输入并采用 add-only 版本：

- GAWorld：`llm_providers_audited.py`，提交 `bfcd2a6`；
- Bridge：`benchmark_core/model_runner_v2.py`。

旧实验继续引用原模块；新实验必须显式导入 v2。这样历史结果可复现，新能力也可以继续发展。

## 4. 工程探测结果

三次探测都不是正式 Benchmark 单元，不进入任何模型得分。

| 探测 | 实际模型 | 设置 | 观察 |
|---|---|---|---|
| A | GLM-4-Flash | JSON object；1 次物理尝试；64 tokens | 严格 JSON 通过；事件顺序为 request → attempt → response |
| B | GLM-5.2 | JSON object；1 次物理尝试；64 tokens | TLS EOF；记录 1 个失败 attempt；没有暗中重试 |
| C | GLM-5.2 | JSON object；最多 2 次物理尝试；64 tokens | 第一次 TLS EOF、第二次传输成功；记录 2 个 attempts 和 1 次 retry；正文为空，严格 JSON 失败 |

探测 A 还发现，本机未显式覆盖模型时，当前配置解析成 GLM-4-Flash。因此以后不能只写“使用 `paratera_glm`”，必须在运行清单和证据中同时锁定解析后的模型名。

探测 C 证明物理重试链能够完整进入证据。第二次请求没有被网关以参数错误拒绝，但空正文不能证明 GLM-5.2 已稳定实现结构化输出；它与 Thinking 开启且仅给 64 tokens 的设置相容，但本次探测不能唯一确定空正文原因。正式预注册前应显式设置 `GAWORLD_LLM_MODEL=GLM-5.2`、`GAWORLD_LLM_THINKING=disabled`，并先用不计分的校准请求确认响应上限。

## 5. 测试证据

- GAWorld 新适配器：13 项定向测试通过，覆盖 response format 透传、首次失败后成功、禁用重试和 fallback 元数据。
- Bridge v2：覆盖严格模式、单围栏规范化的接受/拒绝边界、逻辑调用与物理尝试关联、失败证据和凭证不落盘。
- 真实模块链集成测试不访问网络，但完整经过 `GAWorldModelClient → LLMRouter → OpenAIProvider → RecordedModelRunner`，验证请求参数、事件顺序和 Key 隔离。
- Bridge 全部正式单元测试在版本隔离后通过；旧 T5-v3 密封校验恢复通过。
- GAWorld 全套旧测试仍有两个与本次改动无关的 Windows 问题：日志文件句柄导致临时目录清理失败，以及 avatar 路径使用反斜杠。这两项没有在本任务中顺手修改。

## 6. 下一轮实验怎么启用

新实验代码必须显式使用 v2，并在预注册中冻结下列设置：

```python
from benchmark_core.model_runner_v2 import (
    GAWorldModelClient,
    ModelCallBudget,
    RecordedModelRunner,
)

client = GAWorldModelClient(
    "paratera_glm",
    temperature=0,
    max_tokens=256,
    response_format={"type": "json_object"},
    retry_attempts=1,
)

runner = RecordedModelRunner(
    trace_path,
    client,
    ModelCallBudget(max_calls),
    temperature=0,
    allow_live_model=True,
    run_id=run_id,
    json_normalization="strict",
)
```

推荐主分析使用 provider-native JSON 加 `strict`，并把 `retry_attempts=1` 作为跨平台公平性的默认设置。如果研究问题允许传输重试，可以预注册大于 1 的值，但必须报告物理尝试数。`single_json_fence` 只能作为事前声明的协议模式或敏感性分析，不能在看到结果后临时开启。

## 7. 还没有解决什么

1. 本次没有重算或覆盖 T3 非代码先导的冻结主结果。
2. 尚未完成 GLM-5.2 在 Thinking 关闭、正常 token 上限下的 provider-native JSON 稳定性重复测试。
3. 尚未执行同一 reviewer payload 在两个平台上的 executor 重放，因此平台效应仍不能估计。
4. 当前逐尝试证据会在 Provider 调用返回后批量写入；如果进程在网络调用中被强制终止，最后一次尝试可能来不及落盘。正式长任务可进一步改成实时 attempt sink。
5. 该适配器只服务新评测协议，不改变 GAWorld 普通模拟运行的默认 Provider 行为。

## 8. 可以得到的启发

结构化输出失败不是单一的“模型错了”。至少要区分四层：传输有没有成功、Provider 是否接受结构化约束、文本是否满足解析契约、解析后的业务决策是否正确。只保留最后一个 0/1，会把网络、接口和能力混在一起。

同样，自动重试既不是免费的实现细节，也不是新的独立样本。它会影响费用、延迟和跨平台公平性，应当和逻辑调用分别计数。最后，预注册哈希真的在开发中阻止了无声漂移：当修复触碰旧输入时，正确做法是新建版本和新实验编号，而不是更新哈希让旧测试重新变绿。
