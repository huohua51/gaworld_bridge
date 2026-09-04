# EXP-HF-H1H4-02认知访谈材料包

本目录把四类非代码任务的12张角色卡整理为6份彼此隔离的离线HTML。它只用于检查说明理解、信息边界、角色动作和H1候选题措辞，不是正式Human Reference，也不能产生Human–Agent比较结果。

## 1. 生成与核验

在仓库根目录运行：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m human_validity.h1_h4_v2.cognitive_interview_kit.generate

F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m human_validity.h1_h4_v2.cognitive_interview_kit.audit
```

生成器会重建`dist/`，并输出：

- `participant_packets/CI01.html`至`CI06.html`：六个只读、自包含、无脚本的参与者文件；
- `admin/facilitator_record.html`：主持人离线记录页，绝不能发给参与者；
- `admin/ASSIGNMENT_TABLE.csv`：包含后台表面与条件的主持人分配表；
- `admin/INTERVIEW_RECORD_TEMPLATE.json`：空白机器可读记录模板；
- `MANIFEST.json`：输入文件、输出文件和材料版本SHA-256；
- `LEAK_AUDIT.json`：生成时的逐包泄漏检查结果。

生成是确定性的。相同输入应产生相同`material_sha256`和参与者文件哈希；任一任务YAML、分配、生成或审计逻辑变化都会形成新材料版本。

## 2. 六人分配

| 代号 | 第一张角色卡 | 第二张角色卡 | 只发送 |
|---|---|---|---|
| CI01 | 修订：起草人 | 核验：核验员 | `CI01.html` |
| CI02 | 修订：审核员 | 交接：第二执行者 | `CI02.html` |
| CI03 | 修订：发布人 | 排序：安全与照顾代表 | `CI03.html` |
| CI04 | 核验：信息整理员 | 交接：协调员 | `CI04.html` |
| CI05 | 核验：决策协调员 | 排序：执行代表 | `CI05.html` |
| CI06 | 交接：第一执行者 | 排序：协调记录员 | `CI06.html` |

不要发送整个`dist`目录、ZIP整个目录、`admin`目录或GitHub链接。应只把对应HTML作为单独文件发给对应代号，并在访谈开始时再请参与者打开。静态文件无法阻止收件人主动转发，所以主持人仍要提醒不要分享材料。

## 3. 每场访谈怎么做

1. 仅使用匿名代号CI01–CI06，不建立姓名、学校、学号或联系方式到代号的公开映射。
2. 逐字阅读[`COGNITIVE_INTERVIEW.md`](../COGNITIVE_INTERVIEW.md)中的开场白；不同意则立即结束。
3. 参与者依次阅读两张卡。每张卡先无提示复述，再做两题知识检查，然后进行微型情境推演和专项追问。
4. 第一次知识检查错误时只让其重读；第二次仍错误才解释，并记录为`fail`，不能改记成无提示通过。
5. 两张角色卡结束后，再做匿名轨迹和H1候选量表认知检查。
6. 使用`admin/facilitator_record.html`记录；页面不联网、不自动保存，必须点击“导出匿名JSON”。
7. 每人结束后提醒不要向后来参与者透露材料。

共同排序卡只做离线理解检查。C1或等价协调路径通过规则校准前，不得把它用于实时多人试采。

## 4. 原始记录的保存边界

浏览器导出的JSON应立即移到仓库之外的受控目录，例如`F:\private_h1h4_ci_records`。不要放进`dist/`、`output/`或公开Git仓库；本仓库也显式忽略`cognitive_interview_kit/private_records/`，但仓库外目录仍是首选。

对私有目录运行：

```powershell
F:\proj\.venv_gaworld_eval\Scripts\python.exe `
  -m human_validity.h1_h4_v2.cognitive_interview_kit.audit `
  --records F:\private_h1h4_ci_records
```

自动检查会发现身份字段、邮箱、手机号、身份证号、长数字标识和显式联系方式，但无法可靠识别所有中文姓名或上下文线索。检查通过后仍须人工复核；工具只报告文件和风险类别，不回显疑似身份内容。

若参与者不同意，记录页只导出代号、材料版本、同意状态和时间，不保存行为回答。

## 5. 进入Wave 1的门

至少5人完成且12张卡均被覆盖后，按认知访谈协议聚合问题。私有信息泄漏、系统性角色越界误解、高频含糊词或知识检查持续失败都要求修订并生成新版本。仓库只提交聚合问题、修改理由、版本哈希和放行决定；不提交原始文本。

认知访谈通过仍不等于正式采集放行。还必须完成三角色一次性令牌、私有视图、追加式事件日志、断线/退出路径和功能正负控，才能启动12人、4队、8条轨迹的Wave 1内部试采。
