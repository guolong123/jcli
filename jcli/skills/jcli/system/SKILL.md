---
name: jcli-system
version: 1.0.0
description: |
  jcli 系统管理 - 管理 Jenkins 系统信息查看、重启、安静模式等操作。
allowed-tools:
  - Bash
  - Read
---

# jcli-system

管理 Jenkins 系统信息查看、重启、安静模式等操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 命令参考

```bash
jcli system info                           # 查看系统信息
jcli system load                           # 查看系统负载
jcli system restart                        # 安全重启 Jenkins
jcli system quiet-down                     # 进入安静模式
jcli system quiet-down --reason "维护"     # 带原因的安静模式
jcli system cancel-quiet-down              # 取消安静模式
jcli system script <script>                # 执行 Groovy 脚本（位置参数）
jcli system users                          # 列出所有 Jenkins 用户
jcli system token <username>               # 为用户生成 API token
jcli system token <username> --token-name <name>  # 指定 token 名称
```

## 常见用例

### 查看系统状态

```bash
# 查看系统版本和统计信息
jcli system info

# 查看队列长度和执行器数量
jcli system load
```

### 维护模式

```bash
# 进入安静模式（不接受新构建）
jcli system quiet-down --reason "系统升级"

# 取消安静模式
jcli system cancel-quiet-down
```

### 重启 Jenkins

```bash
# 安全重启（等待当前构建完成）
jcli system restart
```

### 执行 Groovy 脚本

```bash
# 执行简单的 Groovy 脚本（SCRIPT 为位置参数）
jcli system script "println('Hello from jcli')"

# 获取所有节点信息
jcli system script "Jenkins.instance.computers.each { println it.name }"
```

### 用户与 Token

```bash
# 列出所有用户
jcli system users

# 为指定用户生成 API token
jcli system token admin
```
