---
name: jcli-config
version: 1.0.0
description: |
  jcli 配置管理 - 管理 Jenkins 连接配置，支持多实例管理。
allowed-tools:
  - Bash
  - Read
---

# jcli-config

管理 jcli 的连接配置，支持多 Jenkins 实例。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 初始化配置

```bash
jcli config init
```

## 配置文件位置

`~/.jcli/config.yaml`

## 配置结构

```yaml
active_profile: default
profiles:
  default:
    url: https://jenkins.example.com
    username: admin
    api_token: your-api-token-here
    description: Default Jenkins instance
```

## 多实例管理

```bash
# 添加新 profile
jcli config add dev --url https://jenkins-dev.example.com --username admin

# 修改配置
jcli config set dev api_token your-token
jcli config set dev description "Development Jenkins"

# 切换 profile
jcli config use dev

# 查看配置
jcli config show
jcli config list
```

## 环境变量覆盖

| 变量 | 覆盖字段 |
|------|---------|
| `JCLI_URL` | url |
| `JCLI_USERNAME` | username |
| `JCLI_API_TOKEN` | api_token |
| `JCLI_PROFILE` | active_profile |

## 命令参考

```bash
jcli config init                           # 初始化配置文件
jcli config show                           # 查看当前配置
jcli config show --profile dev             # 查看指定 profile
jcli config list                           # 列出所有 profiles
jcli config add <name> --url URL           # 添加新 profile
jcli config set <name> <field> <value>     # 修改配置
jcli config use <name>                     # 切换 active profile
jcli config delete <name>                  # 删除 profile
```
