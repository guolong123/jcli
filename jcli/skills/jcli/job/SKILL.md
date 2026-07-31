---
name: jcli-job
version: 1.0.0
description: |
  jcli Job 管理 - 管理 Jenkins Job 的创建、删除、复制、启用/禁用等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-job

管理 Jenkins Job 的创建、删除、复制、启用/禁用等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli job list                              # 列出所有 Job
jcli job get <name>                        # 查看 Job 详情
jcli job create <name> --config-file config.xml  # 从 XML 创建 Job
jcli job delete <name>                     # 删除 Job
jcli job copy <from> <to>                  # 复制 Job
jcli job rename <old> <new>                # 重命名 Job
jcli job enable <name>                     # 启用 Job
jcli job disable <name>                    # 禁用 Job
jcli job config <name>                     # 查看 Job XML 配置
jcli job update <config.xml> <name>        # 用 XML 更新 Job 配置
jcli job create-folder <name>              # 创建文件夹
jcli job delete-folder <name>              # 删除文件夹（含内容）
```

## 常见用例

### 导出 Job 配置

```bash
jcli job config my-job > job-config.xml
```

### 批量导出所有 Job 配置

```bash
jcli -f json job list | jq -r '.[].name' | while read job; do
  jcli job config "$job" > "${job}.xml"
done
```

### 从 XML 创建 Job

```bash
jcli job create my-new-job --config-file job-config.xml
```

### 参数化创建 Job

```bash
# 从 git 仓库创建 freestyle 构建
jcli job create my-freestyle --job-type freestyle --git-url git@github.com:org/repo.git --git-branch main

# 创建 Pipeline 构建（使用仓库根目录的 Jenkinsfile）
jcli job create my-pipeline --job-type pipeline --git-url git@github.com:org/repo.git --script "pipeline { agent any; stages { stage('Build') { steps { echo 'hi' } } } }"

# 定时构建
jcli job create my-scheduled --job-type freestyle --git-url git@github.com:org/repo.git --cron "H/15 * * * *"
```
