---
name: jcli-auth
version: 1.0.0
description: |
  jcli 认证配置管理 - 管理 Jenkins 连接 profile 的添加、切换、查看、删除等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-auth

管理 jcli 的认证配置 profile，支持多 Jenkins 实例。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

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

## 命令参考

```bash
jcli auth add -n <name> -u <user> -p <token> -e <url>   # 添加（或更新）配置
jcli auth add -n <name> ... --default                   # 添加并设为 active profile
jcli auth status                                        # 列出所有配置（token 掩码）
jcli auth use <name>                                    # 切换 active profile
jcli auth set <name> <field> <value>                    # 修改字段（url/username/api_token/description）
jcli auth show [name]                                   # 查看单个配置详情（默认 active）
jcli auth rm <name>                                     # 删除配置
jcli auth rm --all                                      # 删除所有配置（重置为模板）
```

## 常见用例

### 添加新 profile

```bash
jcli auth add -n dev -u admin -p your-api-token -e https://jenkins-dev.example.com
```

### 修改配置

```bash
jcli auth set dev api_token your-token
jcli auth set dev description "Development Jenkins"
```

### 切换 profile

```bash
jcli auth use dev
```

### 查看配置

```bash
jcli auth status
jcli auth show
jcli auth show dev
```

## 环境变量覆盖

| 变量 | 覆盖字段 |
|------|---------|
| `JCLI_URL` | url |
| `JCLI_USERNAME` | username |
| `JCLI_API_TOKEN` | api_token |
| `JCLI_PROFILE` | active_profile |
