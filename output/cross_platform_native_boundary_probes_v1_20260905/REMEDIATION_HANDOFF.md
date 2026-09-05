# 三平台原生边界问题与修改验收交接

## 这轮是怎样发现问题的

上一轮共享审核载荷重放已经证明，五个有效的同一对象都能被三平台完整运输；但它没有回答“谁有权发送、读取和写入”。因此本轮不再调用模型，而是把注意力移到平台原生接口本身。评测锁定了三个具体表面：GAWorld `ReviewChannel`、YuLan-OneSim `Event/EventBus`、AgentSociety 2 `SimpleSocialSpace`，让它们分别面对身份冒用、私有数据读取、越权最终提交和消息追溯四种操作。

实验没有在适配器里增加权限判断。YuLan和AgentSociety的结果接收者只是被动记录消息是否送达；如果适配器替平台拒绝消息，就无法判断被测平台有没有真正执行保护。代码在正式运行前以提交`6f8c77d`冻结；正式运行又校验了9个评测文件、3个上游提交和4个被测源文件的哈希。所有操作都在本地完成，新模型调用为0。

这是一轮“校准后预注册回归”，不是盲测发现。它适合稳定复现接口行为并作为修复验收基线，不应被包装成独立统计验证或总体平台排名。

## GAWorld：资源规则存在，但身份根基没有闭合

直接观测到的结果是：

- `read_private(task_id, "executor")`拒绝读取Reviewer私有数据，且没有返回私有标记；
- `write_artifact(role="reviewer", kind="final")`拒绝写最终产物，目标文件没有生成；
- 同一`review_id`可以在发送结果、投递结果、Executor收件箱和JSONL审计中关联；
- 但是逻辑上的Executor调用`emit_review`并填入`reviewer_id=1`时，操作被接受。该方法没有独立的认证调用者参数。

因此，P2/P3通过只能说明“当调用方如实提交自己的角色时，角色条件分支工作正常”，不能解释成端到端的认证授权已经完成。这是本轮最重要的逻辑关系：如果角色和ID本身由调用方自由填写，攻击者就可能先冒用授权角色，再绕过后续只检查字符串的ACL。后一句是根据P1结果和方法签名作出的安全推论，尚需修复同学用更直接的伪造角色回归验证。

建议的修改方向不是继续增加`if role == ...`，而是建立一个不可由任务内容自行构造的调用者上下文。运行时或网关完成认证后生成`ActorContext`，其中包含真实agent ID、角色、会话/任务范围；`emit_review`应从该上下文派生Reviewer身份，而不是接受任意`reviewer_id`。`read_private`和`write_artifact`也应验证同一上下文，避免把调用方传入的角色字符串当作身份事实。审计中同时记录真实调用者、目标资源、允许/拒绝、原因和关联ID。

修复完成的最低验收条件：

1. Executor即使声称Reviewer ID也不能`emit_review`；
2. Executor即使声称Reviewer角色也不能读取Reviewer私有数据；
3. Reviewer即使声称Executor角色也不能写最终产物，且文件不存在；
4. 合法Reviewer审核、合法Executor读取审核及写最终产物仍能完成；
5. 每次拒绝都能由不可变调用者ID和correlation ID追溯。

## YuLan-OneSim：事件可追溯，但EventBus不承担身份与工作流授权

直接观测到的结果是：

- 逻辑Executor构造`from_agent_id="reviewer"`的事件后，EventBus将它送达Executor接收者；
- Reviewer声明的`FinalStateSubmitted`事件被送达被动结果接收者；
- `event_id`在发送对象、接收对象和原生event flow中一致，追溯通过；
- 固定的EventBus表面没有owner-bound私有存储/read方法，所以P2是`not_applicable`，不是安全通过。

如果项目希望EventBus本身形成安全边界，建议让dispatch入口接收由运行时绑定的agent handle/context，并从该上下文生成不可变的`from_agent_id`；对敏感event kind配置“允许的发送角色—目标类型”策略，在路由之前拒绝并写审计。若身份和权限本来就由外部网关负责，也可以不改EventBus，但需要把这个部署前提写成明确契约，并对网关运行同一组探针。

私有存储不是EventBus当前能力，不建议为了评测分数把临时邮箱硬塞进总线。需要私有状态时，应选定真正负责存储的YuLan组件后建立新编号测试；在此之前保持`not_applicable`最科学。

最低验收条件是：伪造sender的事件在进入接收者前被拒绝；Reviewer不能向受保护final sink提交最终状态；合法事件的`event_id`仍贯穿发送、接收和flow；如果权限由外层保证，则必须在那个真实边界完成同样结果并留下拒绝审计。

## AgentSociety 2：邮箱可承载消息，但公开调用边界缺少身份绑定与公开关联ID

直接观测到的结果是：

- 逻辑Executor调用`send_message(sender_id=1, ...)`冒用Reviewer，消息被接收；
- 逻辑Executor调用`receive_messages(agent_id=1)`读取Reviewer邮箱，私有标记被返回；
- Reviewer发送的最终状态内容被结果邮箱接收；
- 内部`Message`对象会生成`message_id`，但公开send响应、receive响应和工具历史都没有暴露它，无法满足跨边界关联条件。

建议让工具运行上下文提供真实调用者：`send_message`的sender由上下文派生，不能由模型参数覆盖；`receive_messages`默认只能读取当前调用者邮箱，跨邮箱读取必须有明确能力令牌或管理员权限。send响应和receive消息都应返回同一个稳定`message_id`，工具审计也记录它。对于最终产物，不应仅靠“向某个邮箱发送一段声称是FinalStateSubmitted的文本”建立权限；若AgentSociety需要承担工作流约束，应提供单独的受权限控制的final submission工具。

这里必须保留产品边界：`SimpleSocialSpace`被描述为通用社交邮箱，P3失败不自动等于邮箱实现错误。它说明所测表面不能独自提供最终产物ACL；项目可以选择在更高层实现，但必须明确该层并在那里复测。

最低验收条件是：sender不能由非本人调用覆盖；读取其他agent邮箱被拒绝且不清空目标邮箱；受保护final submission只接受Executor上下文；同一`message_id`在发送响应、接收响应和审计中可关联。

## 修复后的统一复测办法

不要修改本轮正式目录，也不要用同一实验编号覆盖旧证据。每个平台修复后应建立新编号，锁定新commit和真正承担认证/授权的接口；先加入合法操作正控制，再原样运行四个负向/追溯探针。报告必须同时给出：原生能力是否存在、负向操作是否被拒绝、合法操作是否仍成功、拒绝审计是否可追溯。

只有当三个平台选择了职责相当的安全边界，四项分母完全一致，才可以讨论组合比较；即便如此，也仍然只是身份/权限/追溯子维度，不能代表平台总体能力，更不能替代H1–H7的人类效度实验。
