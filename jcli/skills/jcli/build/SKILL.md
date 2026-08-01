---
name: jcli-build
version: 1.0.0
description: |
  jcli 构建管理 - 管理 Jenkins 构建的触发、查看、停止等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-build

管理 Jenkins 构建的触发、查看、停止等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli build list <job>                      # 列出构建历史
jcli build list <job> --limit 20           # 列出最近 20 次构建
jcli build get <job> <number>              # 查看构建详情
jcli build log <job> <number>              # 查看完整控制台日志
jcli build log <job> <number> -n 50        # 只显示末尾 50 行（tail -n）
jcli build log <job> <number> -f           # 实时跟随（tail -f）：先打印全部历史，再滚动新增，构建结束自动退出
jcli build log <job> <number> -f -n 50     # 显示末尾 50 行后实时跟随
jcli build artifacts <job> <number>        # 查看构建产物
jcli build trigger <job>                   # 触发构建
jcli build trigger <job> --params BRANCH=main  # 带参数触发构建
jcli build trigger <job> --params KEY1=VAL1 --params KEY2=VAL2  # 多个参数
jcli build rebuild <job> <number>          # 重建（复用上次构建参数）
jcli build rebuild <job> <number> --set KEY=VAL  # 重建并覆盖参数（可重复）
jcli build replay <job> <number> <jenkinsfile>  # 回放（使用修改后的 Jenkinsfile）
jcli build stop <job> <number>             # 停止构建
jcli build queue                           # 查看构建队列
```

## 常见用例

### 查看构建失败原因

```bash
# 1. 查看最近构建
jcli build list my-job

# 2. 查看失败构建的日志
jcli build log my-job 42
```

### 批量触发构建

```bash
for job in job1 job2 job3; do
  jcli build trigger $job
done
```

### 监控构建状态

```bash
# 查看队列
jcli build queue

# 实时查看最新构建状态
watch -n 5 "jcli build list my-job --limit 1"

# 实时跟随构建日志（-f，构建结束自动退出）
jcli build log my-job 42 -f
```

### 带参数触发构建

```bash
# 单个参数
jcli build trigger my-job --params BRANCH=develop

# 多个参数
jcli build trigger my-job --params BRANCH=develop --params DEPLOY=true --params ENV=staging
```

### 实时查看构建日志（tail 风格）

`jcli build log` 沿用 `tail` 命令的参数语义：

| 命令 | 效果 |
|------|------|
| `jcli build log <job> <n>` | 输出完整日志 |
| `jcli build log <job> <n> -n 50` | 只显示末尾 50 行 |
| `jcli build log <job> <n> -f` | 实时跟随：先输出全部历史，再滚动显示新日志 |
| `jcli build log <job> <n> -f -n 50` | 先看末尾 50 行，再实时跟随 |

- `-f` / `--follow`：实时输出，新日志逐行滚动（tail -f）
- `-n N` / `--lines N`：只显示末尾 N 行，默认全部
- 跟随模式在**构建结束后自动退出**，也可随时 `Ctrl+C` 中断

```bash
# 构建失败排查：看末尾日志定位错误
jcli build log my-job 42 -n 100

# 实时观察正在构建的日志
jcli build log my-job 42 -f

# 触发构建后直接跟随
jcli build trigger my-job
jcli build log my-job 43 -f
```

### 重建与回放

```bash
# 重建：复用上次构建的参数
jcli build rebuild my-job 42

# 重建并覆盖部分参数（--set 可重复）
jcli build rebuild my-job 42 --set DEPLOY=false

# 回放：使用修改后的 Jenkinsfile 文件重新运行 Pipeline
jcli build replay my-job 42 Jenkinsfile
```
