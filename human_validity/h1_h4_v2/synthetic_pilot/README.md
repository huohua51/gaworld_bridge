# H1/H4-v2合成试采演练

本目录用于在真实远程采集系统完成前，演练`EXP-HF-H1H4-02` Wave 1的数据分母、评分出口、双人编码门和报告措辞。

它不是伪造真人数据。生成结果会同时声明：

- `synthetic=true`；
- 真实参与者、真实模型调用和API费用均为0；
- 不得作为Human Reference、模型比较或论文实证证据；
- Wave 2因协调依赖未解除而不运行。

默认演练包含4个合成团队的8条Human占位轨迹、8条匹配Agent占位轨迹，以及6名合成评委对16个刺激的96份评分。失败和分歧是有意注入的，用于确认`N/A`、固定分母、功能失败、H4过程指标和编码修订门不会被混在一起。

所有来源差异和错误模式都是生成器预先设定的测试输入，不是对未来真人或模型结果的估计。

运行：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe human_validity\h1_h4_v2\synthetic_pilot\simulate.py
```

输出写入`result_20260903/`。每次运行使用固定种子`20260903`，应产生完全相同的结果。

可直接阅读[合成试采报告](result_20260903/REPORT.md)。
