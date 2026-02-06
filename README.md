# AI MidLayer

> 大模型上下文中间层 - 将杂乱的项目资料转化为高质量 LLM 上下文

## 快速开始

```bash
# 安装
pip install -e .

# 初始化项目知识库
midlayer init

# 添加文件
midlayer add docs/

# 搜索
midlayer search "关键问题"
```

## 开发

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## 文档

- [架构说明](memory-bank/@architecture.md)
- [技术栈](memory-bank/@tech-stack.md)
- [实施计划](memory-bank/@implementation-plan.md)
