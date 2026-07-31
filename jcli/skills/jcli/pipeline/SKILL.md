---
name: jcli-pipeline
version: 1.0.0
description: |
  jcli Pipeline 管理 - 管理 Jenkins Pipeline 的阶段查看、日志获取、Jenkinsfile 验证等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-pipeline

管理 Jenkins Pipeline 的阶段查看、日志获取、Jenkinsfile 验证等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli pipeline stages <job> <build>         # 查看阶段信息
jcli pipeline log <job> <build> <node-id>  # 查看步骤日志
jcli pipeline validate <Jenkinsfile>       # 验证 Jenkinsfile（位置参数，文件路径）
jcli pipeline pending <job> <build>        # 查看待处理输入
```

## 常见用例

### 查看 Pipeline 阶段

```bash
# 查看构建的各个阶段
jcli pipeline stages my-job 42
```

### 查看特定阶段日志

```bash
# 查看特定节点/阶段的日志
jcli pipeline log my-job 42 15
```

### 验证 Jenkinsfile

```bash
# 验证 Jenkinsfile 语法（传入文件路径）
jcli pipeline validate Jenkinsfile
```

### 查看待处理输入

```bash
# 查看 Pipeline 中等待人工确认的步骤
jcli pipeline pending my-job 42
```
