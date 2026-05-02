# Multi-Agent Code Review System

多 Agent 协作代码审查 + 自动修复系统。4 个 AI Agent 形成链式推理闭环：**PR 解析 → 规则检测 → 修复生成 → 测试验证**。

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Chain Reasoning Pipeline                    │
│  问题定位 → 原因分析 → 修复建议 → 测试验证 → 回归检测            │
├─────────────┬──────────────┬──────────────┬────────────────────┤
│  Agent 1    │  Agent 2     │  Agent 3     │  Agent 4           │
│  PR Parser  │  Rule Checker│  Fix Gen     │  Test Runner       │
├─────────────┼──────────────┼──────────────┼────────────────────┤
│ 语言识别    │ 安全扫描(7)  │ 知识库匹配   │ 测试发现           │
│ 变更分类    │ 性能检测(5)  │ LLM 修复合   │ 已有用例执行       │
│ 风险评级    │ 规范检查(7)  │ Patch 生成   │ 自动用例生成       │
│ Diff 结构化 │ LLM 深度扫描 │ 置信度评分   │ 回归检测           │
└─────────────┴──────────────┴──────────────┴────────────────────┘
```

## 快速开始

```bash
git clone https://github.com/hcw040810/multi-agent-code-review.git
cd multi-agent-code-review
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env` 填入 LLM API Key：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

支持任何 OpenAI 兼容 API（OpenAI / Azure / 本地模型）。

### 使用

```bash
# 审查当前未提交的改动
python main.py --repo /path/to/your/project

# 审查 PR（对比 main 分支）
python main.py --repo /path/to/your/project --base main

# 启用 LLM 深度扫描 + 自动修复
python main.py --repo /path/to/your/project --llm --auto-fix

# 交互模式：逐条审查
python main.py --repo /path/to/your/project --interactive --detail

# 保存 JSON 报告
python main.py --repo /path/to/your/project --output ./reports
```

## 内置规则 (19 条)

### 安全 (7 条)

| 规则 ID | 名称 | 严重度 | CWE |
|---------|------|--------|-----|
| SEC-001 | SQL 注入 | CRITICAL | CWE-89 |
| SEC-002 | XSS 跨站脚本 | HIGH | CWE-79 |
| SEC-003 | 命令注入 | CRITICAL | CWE-78 |
| SEC-004 | 硬编码密钥 | CRITICAL | CWE-798 |
| SEC-005 | 不安全反序列化 | HIGH | CWE-502 |
| SEC-006 | 弱加密算法 | MEDIUM | CWE-327 |
| SEC-007 | 路径穿越 | HIGH | CWE-22 |

### 性能 (5 条)

| 规则 ID | 名称 | 严重度 |
|---------|------|--------|
| PERF-001 | N+1 查询 | HIGH |
| PERF-002 | 潜在无索引查询 | MEDIUM |
| PERF-003 | 低效集合操作 | LOW |
| PERF-004 | 无限制查询 | HIGH |
| PERF-005 | 同步阻塞 I/O | MEDIUM |

### 规范 (7 条)

| 规则 ID | 名称 | 严重度 |
|---------|------|--------|
| STD-001 | 函数过长 | MEDIUM |
| STD-002 | 参数过多 | LOW |
| STD-003 | 嵌套过深 | MEDIUM |
| STD-004 | 命名不规范 | LOW |
| STD-005 | 缺少 Docstring | INFO |
| STD-006 | 裸 except | HIGH |
| STD-007 | 吞异常 (pass) | MEDIUM |

## 项目结构

```
code-review-system/
├── main.py                   # CLI 入口
├── config.py                 # 配置中心
├── pipeline.py               # 4-Agent 编排引擎
├── agents/
│   ├── pr_parser.py          # Agent 1: PR 结构解析
│   ├── rule_checker.py       # Agent 2: 安全/性能/规范检测
│   ├── fix_generator.py      # Agent 3: 修复方案 + Patch
│   └── test_runner.py        # Agent 4: 测试执行 + 回归
├── rules/
│   ├── base.py               # Finding / Severity 数据模型
│   ├── security.py           # 7 条安全规则
│   ├── performance.py        # 5 条性能规则
│   └── standards.py          # 7 条规范规则
├── utils/
│   ├── llm.py                # LLM 接口层
│   ├── git_ops.py            # Git diff / patch 操作
│   └── report.py             # Rich 终端 + JSON 报告
└── knowledge_base/
    ├── patterns.json         # 已知问题模式 + 工具链
    └── __init__.py           # 知识库检索
```

## 核心亮点

- **链式推理**：每个 Agent 产出 `chain_context`，全局可追溯推理路径
- **LLM 深度扫描**：三维度独立 prompt（安全/性能/规范） + JSON structured output
- **自动修复**：知识库匹配 → LLM 生成 → unified diff patch → `git apply`
- **回归检测**：修复前后测试失败数对比，负向变化即时告警
- **质量评分**：A-F 评分，Critical/High/Medium/Low/Info 五级分类
- **多语言**：Python / JavaScript / TypeScript / Go / Java / Rust 工具链参考

## 依赖

```
openai>=1.0.0        # LLM 接口
click>=8.0.0         # CLI
rich>=13.0.0         # 终端渲染
gitpython>=3.1.0     # Git 操作
pydantic>=2.0.0      # 数据模型
pyyaml>=6.0          # 配置解析
tiktoken>=0.5.0      # Token 计数
python-dotenv>=1.0.0 # 环境变量
```


