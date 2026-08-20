# 数学智能体（LangGraph 图架构版）

挑战杯 XH-202627「基于 Intern-S1 的数学智能体」——用 LangGraph 图编排重建求解流程，对齐高分方案的架构思想（原创实现）。

## 架构

```
input → classifier（题型/领域/难度）→ solving 子图（双路并行）→ 路由
                                        ├─ reasoning_agent（LLM 推理）
                                        └─ python_agent（SymPy 计算）→ cross_validator
路由：
  match    → substitute（代回核验）→ critic（审计）→ coordinator
  mismatch  → playoff（确定性复算）→ critic / reconciliation
  uncertain → semantic_arbiter → coordinator
  reconciliation → solving（换方法重算，限轮次）
```

## 核心机制

| 机制 | 说明 |
|------|------|
| 双路并行验证 | LLM 推理 vs SymPy 计算独立生成答案 |
| 符号等价匹配 | sympy 判 `πie` 与 `E*I*pi` 等价（含 LaTeX/矩阵/采样）|
| 确定性代回核验 | match 后把答案代回题面验残差，戳穿同源同错 |
| 冲突复算裁决 | 两路冲突时代回原题，确定性证据替代投票 |
| 过程审计 | 定稿前查多问漏答、契约缺项、推导矛盾 |
| prefill 预填充 | assistant seed 跳过 CoT（分类/仲裁 ~1s）|
| 墙钟预算 | 20min 硬限 + 难度软预算 + 请求硬上限 |
| 全卷完成率 | PaperPacer 动态收紧单题预算，保证 6h 完成 112 题 |

## 运行

```bash
# 本地批处理（需 INTERN_API_KEY 环境变量）
python main.py --input_file data.jsonl --output_dir out/

# 竞赛接口
from user_agent import ReasoningAgent
agent = ReasoningAgent(client=platform_client)
result = agent.solve(problem, metadata)
```

## 目录

- `user_agent.py` — 竞赛入口
- `langgraph_math_agent.py` — 主图
- `graph/solving_subgraph.py` — 双路并行子图
- `nodes/` — 10 个图节点
- `utils/` — 答案匹配/提取/prefill/预算等
- `skills/` — 18 领域原创精简 skill 文档
