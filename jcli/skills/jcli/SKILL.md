---
name: jcli
version: 1.0.0
description: |
  jcli — Jenkins CLI 工具，通过命令行管理 Jenkins 服务器。
allowed-tools:
  - Bash
  - Read
---

# jcli — Jenkins CLI 工具

通过命令行管理 Jenkins 服务器。支持 Job、构建、节点、插件、凭据、Pipeline、视图、系统管理等全功能操作。

## 前提条件

- Python >= 3.10
- Jenkins 2.x 或更高版本
- 已安装 jcli：`pip install -e /data/git-project/jcli`

## 输出格式

```bash
jcli -f table job list    # 彩色表格（默认）
jcli -f json job list     # JSON 输出
jcli -f yaml job list     # YAML 输出
```

## 内置技能

| 技能 | 说明 |
|------|------|
| [jcli-auth](auth/SKILL.md) | 认证配置管理 - Jenkins 连接 profile 添加、切换、查看、删除 |
| [jcli-job](job/SKILL.md) | Job 管理 - Job 创建、删除、复制、启用/禁用 |
| [jcli-build](build/SKILL.md) | 构建管理 - 构建触发、查看、停止、队列 |
| [jcli-node](node/SKILL.md) | 节点管理 - Jenkins Agent 节点管理 |
| [jcli-plugin](plugin/SKILL.md) | 插件管理 - 插件安装、卸载、查看 |
| [jcli-credential](credential/SKILL.md) | 凭据管理 - 凭据创建、删除、查看 |
| [jcli-pipeline](pipeline/SKILL.md) | Pipeline 管理 - 阶段查看、日志获取、验证 |
| [jcli-view](view/SKILL.md) | 视图管理 - 视图创建、删除、查看 |
| [jcli-system](system/SKILL.md) | 系统管理 - 系统信息、重启、安静模式 |

## 认证配置（auth）

```bash
jcli auth add -n <name> -u <user> -p <token> -e <url>   # 添加配置（token 即 Jenkins API Token）
jcli auth status                                        # 查看所有配置（token 掩码）
jcli auth use <name>                                    # 切换 active profile
jcli auth set <name> <field> <value>                    # 修改字段（url/username/api_token/description）
jcli auth show [name]                                   # 查看单个配置详情
jcli auth rm <name>                                     # 删除配置
```

详细用法见 [jcli-auth](auth/SKILL.md)。

## Skills 命令

```bash
jcli skills list                          # 列出所有可用技能
jcli skills list --installed              # 列出已安装技能
jcli skills list --bundled                # 列出内置技能
jcli skills install <name>                # 安装技能
jcli skills install <name> --force        # 强制安装（覆盖已有）
jcli skills uninstall <name>              # 卸载技能
jcli skills get <name>                    # 查看技能详情
```

## 调试

```bash
jcli -d job list                           # 启用调试日志
```

## Shell 补全

```bash
jcli completion show bash                  # Bash 补全脚本
jcli completion show zsh                   # Zsh 补全脚本
jcli completion show fish                  # Fish 补全脚本
```

## 项目路径

- 源码: `/data/git-project/jcli`
- 配置: `~/.jcli/config.yaml`
- 技能文档: `/data/git-project/jcli/jcli/skills/jcli/`
