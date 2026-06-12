# jcli

通过命令行管理 Jenkins 服务器。

## 特性

- **8 个命令模块**：Job、构建、节点、插件、凭据、Pipeline、视图、系统管理
- **Skills 管理**：内置 9 个技能文档，支持安装、卸载、查看
- **多种输出格式**：表格（默认）、JSON、YAML
- **多实例管理**：通过 Profile 管理多个 Jenkins 服务器
- **CSRF 自动处理**：自动处理 Jenkins CSRF 保护

## 安装

```bash
pip install jcli
```

或从源码安装：

```bash
git clone https://github.com/guolong123/jcli.git
cd jcli
pip install -e .
```

## 快速开始

### 1. 配置 Jenkins 连接

```bash
jcli config add prod --url https://jenkins.example.com --username admin
```

或手动创建配置文件 `~/.jcli/config.yaml`：

```yaml
active_profile: default
profiles:
  default:
    url: https://jenkins.example.com
    username: admin
    api_token: your-api-token-here
```

### 2. 开始使用

```bash
jcli job list                    # 列出所有 Job
jcli build list my-job           # 查看构建历史
jcli build trigger my-job        # 触发构建
```

## 命令参考

### Job 管理

```bash
jcli job list                    # 列出所有 Job
jcli job get <name>              # 查看 Job 详情
jcli job create <name> -f config.xml  # 创建 Job
jcli job delete <name>           # 删除 Job
jcli job copy <from> <to>        # 复制 Job
jcli job enable <name>           # 启用 Job
jcli job disable <name>          # 禁用 Job
jcli job config <name>           # 查看 Job XML 配置
```

### 构建管理

```bash
jcli build list <job>            # 列出构建历史
jcli build get <job> <number>    # 查看构建详情
jcli build log <job> <number>    # 查看控制台日志
jcli build trigger <job>         # 触发构建
jcli build trigger <job> -p KEY=VAL  # 带参数触发
jcli build stop <job> <number>   # 停止构建
jcli build queue                 # 查看构建队列
```

### 节点管理

```bash
jcli node list                   # 列出所有节点
jcli node get <name>             # 查看节点详情
jcli node delete <name>          # 删除节点
jcli node toggle <name>          # 节点上线/离线
```

### 插件管理

```bash
jcli plugin list                 # 列出已安装插件
jcli plugin get <name>           # 查看插件详情
jcli plugin install <name>       # 安装插件
jcli plugin uninstall <name>     # 卸载插件
```

### 凭据管理

```bash
jcli credential list             # 列出凭据
jcli credential get <id>         # 查看凭据详情
jcli credential create <id> -f config.xml  # 创建凭据
jcli credential delete <id>      # 删除凭据
```

### Pipeline 管理

```bash
jcli pipeline stages <job> <build>  # 查看阶段信息
jcli pipeline log <job> <build> <node-id>  # 查看步骤日志
jcli pipeline validate -f Jenkinsfile  # 验证 Jenkinsfile
jcli pipeline pending <job> <build>  # 查看待处理输入
```

### 视图管理

```bash
jcli view list                   # 列出所有视图
jcli view get <name>             # 查看视图详情
jcli view create <name> -f config.xml  # 创建视图
jcli view delete <name>          # 删除视图
```

### 系统管理

```bash
jcli system info                 # 查看系统信息
jcli system load                 # 查看系统负载
jcli system restart              # 安全重启 Jenkins
jcli system quiet-down           # 进入安静模式
jcli system cancel-quiet-down    # 取消安静模式
jcli system script "..."         # 执行 Groovy 脚本
```

## Skills 管理

```bash
jcli skills list                 # 列出所有技能
jcli skills list --bundled       # 列出内置技能
jcli skills list --installed     # 列出已安装技能
jcli skills install <name>       # 安装技能
jcli skills install -a           # 安装所有技能
jcli skills uninstall <name>     # 卸载技能
jcli skills get <name>           # 查看技能详情
```

### 内置技能

| 技能 | 说明 |
|------|------|
| jcli-config | 配置管理 |
| jcli-job | Job 管理 |
| jcli-build | 构建管理 |
| jcli-node | 节点管理 |
| jcli-plugin | 插件管理 |
| jcli-credential | 凭据管理 |
| jcli-pipeline | Pipeline 管理 |
| jcli-view | 视图管理 |
| jcli-system | 系统管理 |

## 输出格式

```bash
jcli -f table job list    # 彩色表格（默认）
jcli -f json job list     # JSON 输出
jcli -f yaml job list     # YAML 输出
```

## 配置

### 配置文件

配置文件位置：`~/.jcli/config.yaml`

### 环境变量

| 变量 | 覆盖字段 |
|------|---------|
| `JCLI_URL` | url |
| `JCLI_USERNAME` | username |
| `JCLI_API_TOKEN` | api_token |
| `JCLI_PROFILE` | active_profile |

### 命令行参数

```bash
jcli -p staging job list          # 使用 staging profile
jcli -s https://ci.example.com job list   # 覆盖服务器 URL
jcli -d job list                  # 启用调试日志
```

## 开发

### 环境 setup

```bash
git clone https://github.com/guolong123/jcli.git
cd jcli
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
pytest --cov=jcli --cov-report=term-missing
```

### 项目结构

```
jcli/
  cli.py              CLI 入口
  plugins/            命令模块
    job.py            Job 管理
    build.py          构建管理
    node.py           节点管理
    plugin.py         插件管理
    credential.py     凭据管理
    pipeline.py       Pipeline 管理
    view.py           视图管理
    system.py         系统管理
    skills.py         Skills 管理
  sdk/                SDK 库
    client.py         Jenkins REST API 客户端
    config.py         配置管理
    output/           输出格式化
  skills/             内置技能文档
tests/                测试
```

## License

MIT
