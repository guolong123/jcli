---
name: jcli-credential
version: 1.0.0
description: |
  jcli 凭据管理 - 管理 Jenkins 凭据的创建、删除、查看等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-credential

管理 Jenkins 凭据的创建、删除、查看等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli credential list [store] [domain]     # 列出凭据（默认 store=system, domain=_）
jcli credential list --depth 2            # 递归列出凭据
jcli credential get <id> [store]          # 查看凭据详情
jcli credential create <config.xml> [store] [domain]  # 从 XML 文件创建凭据
jcli credential update <config.xml> <id> [store]      # 更新凭据
jcli credential delete <id> [store] [domain]          # 删除凭据
```

## 常见用例

### 查看凭据

```bash
# 列出所有凭据
jcli credential list

# 查看特定凭据详情
jcli credential get my-credential-id
```

### 创建凭据

```bash
# 从 XML 配置文件创建凭据
jcli credential create credential-config.xml
```

### 更新凭据

```bash
# 从 XML 文件更新已有凭据
jcli credential update credential-config.xml my-credential-id
```
