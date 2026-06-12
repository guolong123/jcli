---
name: jcli-plugin
version: 1.0.0
description: |
  jcli 插件管理 - 管理 Jenkins 插件的安装、卸载、查看等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-plugin

管理 Jenkins 插件的安装、卸载、查看等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli plugin list                           # 列出已安装插件
jcli plugin get <name>                     # 查看插件详情
jcli plugin install <name>                 # 安装插件
jcli plugin install git@4.15.0             # 安装指定版本
jcli plugin uninstall <name>               # 卸载插件
```

## 常见用例

### 查看已安装插件

```bash
# 列出所有插件
jcli plugin list

# 查看特定插件详情
jcli plugin get git
```

### 安装插件

```bash
# 安装最新版本
jcli plugin install git

# 安装指定版本
jcli plugin install git@4.15.0
```
