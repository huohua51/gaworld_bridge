# EXP-GM-T6-01 协议

三个模式使用完全相同的初始人口、Seed、仿真天数和仿射状态转移。
`individual`逐人逐日更新；`cohort`逐亚群逐日更新登记矩；
`fast_forward`按无冲击区间做闭式快进。

`checkpoint_resume`在中点写入带人口和转移指纹的检查点，再由新引擎实例加载并完成。
评分器独立逐人计算Oracle。当前没有Human Reference，禁止报告H5/H6/H7或进入排名。
