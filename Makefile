.PHONY: help build clean publish publish-test dry-run install dev test lint

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

clean:  ## 清理构建文件
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build: clean  ## 构建源码包和 wheel
	python3 -m build
	@echo "构建完成:"
	@ls -lh dist/

publish: build  ## 发布到 PyPI
	./scripts/publish.sh

publish-test: build  ## 发布到 TestPyPI
	./scripts/publish.sh --test

dry-run: build  ## 仅构建，不上传
	./scripts/publish.sh --dry-run

install:  ## 安装到当前环境
	pip install -e .

dev:  ## 安装开发依赖
	pip install -e ".[dev]"

test:  ## 运行测试
	python3 -m pytest tests/ -v

test-cov:  ## 运行测试（带覆盖率）
	python3 -m pytest tests/ -v --cov=jcli --cov-report=term-missing

lint:  ## 代码检查
	python3 -m py_compile jcli/cli.py
	python3 -m py_compile jcli/plugins/*.py
	@echo "✅ 代码检查通过"
