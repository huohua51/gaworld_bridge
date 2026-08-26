# EXP-GM-T4-01 protocol

每个任务使用四节点注册路径。源节点注入带版本的不可变消息；中间节点必须先收到并采用，之后才
能转发。目标节点的非默认动作必须绑定已经采用的`message_id`。

- `full`：完整路径可用；control与intervention都应通过。
- `remove_bridge`：注入前移除登记桥边；control默认保持，intervention因收不到消息而失败。
- `drop_bridge`：桥边仍存在，只丢该边本次消息；control默认保持，intervention失败。

Rule校准只证明平台通道、干预和Scorer能够形成预期正负控，不形成模型排名结果。
