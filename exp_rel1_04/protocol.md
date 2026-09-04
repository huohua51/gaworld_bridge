# EXP-GM-REL1-04 协议

本轮固定复用 REL1-03 的 `gaworld-benchmark-rel1-phase-separated-v3`
提示协议和 v3 判分含义，只替换为三个新任务表面。每个表面各跑 control 与
intervention，一共 6 格；每格严格 5 个逻辑模型调用，总分母 30。

Observer 必须原样转发两条当前信号；形成阶段必须统计完整历史、保留两来源计数
与证据行；更新阶段只能使用最后一条 binding outcome。两个阶段的业务值由模型
选择，但 `message_id`、信任版本、动作名和证据绑定由平台生成，只有已采用消息可
驱动动作。

严格 JSON，不做 Markdown 清洗，不补跑失败格，Provider 的一次物理尝试即为一次
注册逻辑调用。
