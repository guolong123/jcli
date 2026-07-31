# jcli

A command-line tool for managing Jenkins servers. jcli wraps the Jenkins REST API into readable commands that work the way you'd expect, with table, JSON, and YAML output options.

[中文文档](README-zh.md)

## Features

- **8 command modules** covering jobs, builds, nodes, plugins, credentials, pipelines, views, and system management
- **Spec-driven CLI**: commands are declared as cliyard YAML specs in `specs/` and generated at runtime, no hand-written Click groups
- **Multiple output formats**: human-readable tables (default, via Rich), JSON, and YAML
- **Multi-profile support** via `~/.jcli/config.yaml` with environment variable overrides
- **Automatic CSRF (Crumb) handling** for Jenkins servers with CSRF protection enabled
- **Built on cliyard and Rich** for a polished, maintainable terminal experience

## Architecture

jcli 2.0 is driven by [cliyard](https://pypi.org/project/cliyard/) YAML specs instead of hand-written Click command groups. At startup, `jcli/cli.py` locates the spec directory (`JCLI_SPEC_DIR` env var > package-local `specs/` > repo-root `specs/`) and calls `cliyard.runtime.create_cli()` to build the whole command tree. Commands stay declarative: adding or changing a command is an edit to a YAML file, not Python plumbing.

```
specs/
  _auth.yaml          Server auth chain (basic auth + crumb, as cliyard plugins)
  resources/          One YAML spec per Jenkins domain
    job.yaml          job list/get/create/config/copy/enable/disable/delete
    build.yaml        build list/get/trigger/replay/log/stop/queue
    node.yaml         node list/get/delete/toggle
    plugin.yaml       plugin list/get/install/uninstall
    credential.yaml   credential list/get/create/delete
    pipeline.yaml     pipeline stages/log/pending/validate
    view.yaml         view list/get/create/delete
    system.yaml       system info/load/quiet-down/restart/script
  plugins/            Python method plugins for non-trivial logic
    jenkins_auth.py         Basic + crumb authentication
    jenkins_methods.py      Build trigger/replay, node create
    jenkins_pipeline_validate.py  Jenkinsfile validation
    jenkins_plugin.py       Plugin install/uninstall/update-center
    jenkins_system.py       Groovy script, quiet-down, restart
```

A resource spec maps a command name to either a plain HTTP call (method, path, params, output mapping) or a `plugin:` reference. The auth chain in `_auth.yaml` injects `Authorization` and crumb headers into every request.

## Requirements

- Python 3.10 or later
- A Jenkins server running Jenkins 2.x or later

## Installation

Install from source with pip:

```bash
pip install .
```

Or in editable mode for development:

```bash
pip install -e ".[dev]"
```

After installation, `jcli` is available as a console script.

## Quick Start

### 1. Configure your Jenkins connection

Create a configuration file at `~/.jcli/config.yaml`:

```yaml
active_profile: default
profiles:
  default:
    url: https://jenkins.example.com
    username: admin
    api_token: "11abcdef0123456789abcdef0123456789ab"
    description: "Production Jenkins"
```

If the file doesn't exist, jcli creates it with a template on first run.

To generate an API token, go to your Jenkins user page: **Your Username > Configure > API Token > Add new Token**.

### 2. Run your first command

```bash
jcli job list
```

If your server is configured correctly, this prints a table of all Jenkins jobs.

## Configuration

### Config file

jcli stores profiles in `~/.jcli/config.yaml`. Each profile has four fields:

| Field        | Description                |
|-------------|----------------------------|
| `url`       | Jenkins server URL          |
| `username`  | Jenkins username            |
| `api_token` | Jenkins API token           |
| `description` | Human-readable description |

The `active_profile` key selects which profile to use.

To add another server profile, edit the file and add a new entry under `profiles`:

```yaml
active_profile: prod
profiles:
  prod:
    url: https://jenkins.prod.example.com
    username: admin
    api_token: "..."
    description: "Production"
  staging:
    url: https://jenkins.staging.example.com
    username: admin
    api_token: "..."
    description: "Staging"
```

### Environment variables

Environment variables override config file values. This is useful in CI pipelines.

| Variable          | Overrides           |
|-------------------|---------------------|
| `JCLI_URL`        | `url`               |
| `JCLI_USERNAME`   | `username`          |
| `JCLI_API_TOKEN`  | `api_token`         |
| `JCLI_PROFILE`    | `active_profile`    |

Set `JCLI_PROFILE` to select a profile without editing the config file.

### CLI options

Profile and server can also be set with command-line flags:

```bash
jcli -p staging job list          # use the "staging" profile
jcli -s https://ci.example.com job list   # override server URL
jcli -d job list                  # enable debug logging
```

Run `jcli --help` for the full option list.

## Command Reference

### Global options

Every command accepts these global flags before the subcommand:

```
-d, --debug                     Enable debug output
-f, --format [table|json|yaml]  Output format (default: table)
-p, --profile TEXT              Configuration profile name
-s, --server TEXT               Jenkins server URL
```

### job — Manage Jenkins jobs

```
jcli job list                               List all jobs
jcli job get JOB_NAME                       Show details for a specific job
jcli job create JOB_NAME -f job-config.xml  Create a new job from XML config file
jcli job config JOB_NAME                    Print the XML configuration of a job
jcli job copy SOURCE_JOB NEW_NAME           Copy a job to a new name
jcli job enable JOB_NAME                    Enable a disabled job
jcli job disable JOB_NAME                   Disable a job
jcli job delete JOB_NAME                    Delete a job
```

### build — Manage Jenkins builds

```
jcli build list JOB_NAME                    List recent builds for a job
jcli build get JOB_NAME BUILD_NUMBER        Show details for a specific build
jcli build trigger JOB_NAME                 Trigger a new build
jcli build replay JOB_NAME BUILD_NUMBER     Replay a build reusing its parameters
jcli build replay JOB_NAME BUILD_NUMBER --set KEY=VAL   ... and override values (repeatable)
jcli build log JOB_NAME BUILD_NUMBER        Show console log for a build
jcli build stop JOB_NAME BUILD_NUMBER       Stop a running build
jcli build queue                            Show the current build queue
```

### node — Manage Jenkins nodes (agents)

```
jcli node list                              List all nodes
jcli node get NODE_NAME                     Get details of a specific node
jcli node delete NODE_NAME                  Delete a node
jcli node toggle NODE_NAME --offline        Take a node offline
jcli node toggle NODE_NAME --online         Bring a node back online
```

### plugin — Manage Jenkins plugins

```
jcli plugin list                            List installed plugins
jcli plugin get PLUGIN_NAME                 Show details for a single plugin
jcli plugin install PLUGIN_NAME             Install a plugin
jcli plugin uninstall PLUGIN_NAME           Uninstall a plugin
```

### credential — Manage Jenkins credentials

```
jcli credential list                        List credentials
jcli credential get CREDENTIAL_NAME         Get credential details
jcli credential create -f cred-config.xml   Create a credential from XML config
jcli credential delete CREDENTIAL_NAME      Delete a credential
```

### pipeline — Manage Jenkins pipelines

```
jcli pipeline stages JOB_NAME BUILD_NUMBER  List stages for a Pipeline build
jcli pipeline log JOB_NAME BUILD_NUMBER     Get log output for a Pipeline step
jcli pipeline pending JOB_NAME BUILD_NUMBER Show pending input actions
jcli pipeline validate -f Jenkinsfile       Validate a Jenkinsfile against the server
```

### view — Manage Jenkins views

```
jcli view list                              List all views
jcli view get VIEW_NAME                     Get details for a view
jcli view create -f view-config.xml         Create a view from XML config
jcli view delete VIEW_NAME                  Delete a view
```

### system — Jenkins system information and management

```
jcli system info                            Show system version and stats
jcli system load                            Show queue length and executor counts
jcli system quiet-down                      Put Jenkins into quiet-down mode
jcli system cancel-quiet-down               Cancel quiet-down mode
jcli system restart                         Trigger a safe restart
jcli system script "println('hello')"       Execute a Groovy script on the server
```

## Output Formats

jcli supports three output formats, selectable with `-f` / `--format`:

```bash
jcli -f table job list    # Rich-formatted table (default)
jcli -f json  job list    # JSON output
jcli -f yaml  job list    # YAML output
```

Table mode uses the [Rich](https://github.com/Textualize/rich) library with alternating row colors and auto-width columns. Pipe the output to any file or command as needed.

## Development

### Setup

```bash
git clone <repo-url> jcli
cd jcli
pip install -e ".[dev]"
```

### Running tests

The test suite uses pytest with the `responses` library for HTTP mocking:

```bash
pytest
```

For coverage:

```bash
pytest --cov=jcli --cov-report=term-missing
```

### Project structure

```
jcli/
  cli.py              Entry point: builds the Click CLI from cliyard YAML specs
  cli_helpers.py      Global option injection and profile/format plumbing
  __init__.py         Version
  plugins/            Legacy hand-written command modules (kept for SDK compatibility)
  sdk/                Shared libraries
    client.py         Jenkins REST API client (HTTP, auth, crumb)
    config.py         Configuration management (YAML, env vars)
    output/
      formatter.py    Table/JSON/YAML output formatting
    exceptions.py     Typed exceptions
specs/                cliyard YAML specs (command definitions)
  _auth.yaml          Auth chain: basic + crumb plugins
  resources/          One YAML per Jenkins domain (job, build, node, ...)
  plugins/            Python method plugins for non-trivial logic
tests/                pytest test suite
```

### Dependencies

| Package          | Purpose                     |
|-----------------|-----------------------------|
| click >= 8.1.0   | CLI framework               |
| cliyard >= 0.6.0 | Spec-driven CLI engine (YAML command generation) |
| requests ~= 2.31 | HTTP client                 |
| pyyaml ~= 6.0.1  | YAML config parsing         |
| rich >= 13.7.1   | Terminal formatting (tables) |
| argcomplete >= 3.3 | Shell tab completion       |

Dev dependencies (optional `[dev]` extra):

| Package          | Purpose                     |
|-----------------|-----------------------------|
| pytest >= 7.0    | Test runner                 |
| pytest-cov >= 4.0 | Coverage reporting         |
| responses >= 0.23 | HTTP response mocking      |

## License

MIT
