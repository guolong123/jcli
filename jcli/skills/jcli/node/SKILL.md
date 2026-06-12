---
name: jcli-node
version: 1.0.0
description: |
  jcli 节点管理 - 管理 Jenkins Agent 节点的上线、下线、删除等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-node

管理 Jenkins Agent 节点的上线、下线、删除等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli node list                             # 列出所有节点
jcli node get <name>                       # 查看节点详情
jcli node delete <name>                    # 删除节点
jcli node toggle <name> --message "维护"   # 节点离线
jcli node toggle <name>                    # 节点上线
```

## 常见用例

### 节点维护

```bash
# 节点离线（带维护原因）
jcli node toggle agent-01 --message "系统升级维护"

# 节点恢复上线
jcli node toggle agent-01
```

### 查看节点状态

```bash
# 查看所有节点状态
jcli node list

# 查看特定节点详情
jcli node get agent-01
```
