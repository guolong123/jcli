#!/usr/bin/env bash
set -euo pipefail

# ==================================================================
# jcli 发布脚本
# ==================================================================
# 用法:
#   ./scripts/publish.sh              # 发布到 PyPI
#   ./scripts/publish.sh --test       # 发布到 TestPyPI
#   ./scripts/publish.sh --dry-run    # 仅构建，不上传
# ==================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 默认配置
PYPI_REPO="pypi"
DRY_RUN=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --test)
            PYPI_REPO="testpypi"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [OPTIONS]"
            echo ""
            echo "选项:"
            echo "  --test       发布到 TestPyPI"
            echo "  --dry-run    仅构建，不上传"
            echo "  -h, --help   显示帮助"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

cd "$PROJECT_DIR"

echo "=========================================="
echo "jcli 发布脚本"
echo "=========================================="
echo "项目目录: $PROJECT_DIR"
echo "目标仓库: $PYPI_REPO"
echo "Dry Run:  $DRY_RUN"
echo ""

# 检查是否在 git 仓库中
if git rev-parse --git-dir > /dev/null  twofull 2>&1; then
    # 检查是否有未提交的更改
    if ! git diff --quiet; then
        echo "⚠️  警告: 有未提交的更改"
        read -p "是否继续? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # 显示当前版本
    CURRENT_VERSION=$(python -c "import jcli; print(jcli.__version__)" 2>/dev/null || grep 'version' pyproject.toml | head -1 | cut -d'"' -f2)
    echo "当前版本: $CURRENT_VERSION"
    echo ""
fi

# 清理旧的构建文件
echo "🧹 清理旧的构建文件..."
rm -rf dist/ build/ *.egg-info/
echo "✅ 清理完成"
echo ""

# 构建
echo "📦 构建源码包和 wheel..."
python3 -m build
echo "✅ 构建完成"
echo ""

# 显示构建结果
echo "📁 构建产物:"
ls -lh dist/
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "✅ Dry run 完成，未上传到 PyPI"
    echo "构建产物位于: dist/"
    exit 0
fi

# 检查 twine 是否安装
if ! command -v twine &> /dev/null; then
    echo "❌ twine 未安装，正在安装..."
    pip install twine
fi

# 上传
echo "🚀 上传到 $PYPI_REPO..."

if [ "$PYPI_REPO" = "testpypi" ]; then
    twine upload --repository testpypi dist/*
else
    twine upload dist/*
fi

echo ""
echo "✅ 发布完成!"
echo ""
echo "安装命令:"
if [ "$PYPI_REPO" = "testpypi" ]; then
    echo "  pip install -i https://test.pypi.org/simple/ jcli"
else
    echo "  pip install jcli"
fi
