---
name: jcli-view
version: 1.0.0
description: |
  jcli 视图管理 - 管理 Jenkins 视图的创建、删除、查看等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-view

管理 Jenkins 视图的创建、删除、查看等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli view list                             # 列出所有视图
jcli view get <name>                       # 查看视图详情
jcli view create <name> -f config.xml      # 从 XML 创建视图
jcli view delete <name>                    # 删除视图
```

## 常见用例

### 查看视图

```bash
# 列出所有视图
jcli view list

# 查看特定视图详情
jcli view get my-view
```

### 创建视图

```bash
# 从 XML 配置文件创建视图
jcli view create my-view -f view-config.xml
```
