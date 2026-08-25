# 上传到 GitHub（协作者）

本机没有 GitHub 登录态，不能代替你点授权。本地仓库已经准备好，按下面做即可。

## 应该上传什么

| 上传 | 不上传 |
|---|---|
| `gaworld_eval_bridge/`（本仓库） | `GAWorld/.env`（API Key） |
| `GAWorld/` 里评测相关源码改动 | `AgentSociety/`、`YuLan-OneSim/` |
| `registry.yaml`、`output/*/REPORT.md`、实验代码 | 根目录汇报 ppt/pdf |

两个独立仓库最合适：仿真平台一份，评测台一份。不要把整个 `~/projects` 打成一个包。

## 1. 评测桥（新仓库）

浏览器打开 https://github.com/new ，仓库名建议 `gaworld_eval_bridge`，**不要**勾选 Add README。然后：

```bash
cd ~/projects/gaworld_eval_bridge
git remote add origin https://github.com/<你的用户名>/gaworld_eval_bridge.git
git push -u origin main
```

## 2. GAWorld 评测改动（不要直接推到 wuchaozju/GAWorld）

上游已是 https://github.com/wuchaozju/GAWorld 。请先 Fork 到自己的账号，再推送本地 `eval-harness` 分支：

```bash
cd ~/projects/GAWorld
git remote add fork https://github.com/<你的用户名>/GAWorld.git
git push -u fork eval-harness
```

然后在 GitHub 上把协作者加成 Collaborator，或开 Organization。

## 3. 协作者克隆

```bash
git clone https://github.com/<你的用户名>/GAWorld.git
cd GAWorld && git checkout eval-harness
cd ..
git clone https://github.com/<你的用户名>/gaworld_eval_bridge.git
cp GAWorld/.env.example GAWorld/.env   # 各自填 key
export PYTHONPATH=$PWD/gaworld_eval_bridge:$PWD/GAWorld
```
