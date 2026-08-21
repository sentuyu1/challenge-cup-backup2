"""config.py — 全局配置。

所有可调参数集中在这里。平台评测固定模型（甲方推荐 s2），
代码传 model 无效，故 model 留空表示使用平台默认。
"""

CONFIG = {
    # 模型名：空 = 用平台默认模型（零风险）；本地调试可用环境变量 INTERN_MODEL 覆盖
    "model": "",

    # ── 重试 ──
    "llm_max_retries": 2,          # LLM 调用外层重试次数
    "backoff_factor": 1.5,         # 退避系数

    # ── 温度 ──
    "temperatures": {
        "classifier": 0.1,         # 分类需确定性
        "reasoning": 0.8,          # 推理采样（多样性）
        "objective_reasoning": 0.2,# 客观题短路径
        "python": 0.6,             # 代码生成
        "reconciliation": 0.2,     # 调解重算
        "semantic_arbiter": 0.1,   # 仲裁需确定性
        "coordinator": 0.4,        # 最终整理
    },

    # ── max_tokens（按难度分级）──
    # 关 CoT 后单题 token 需求下降：easy 省 token 快，hard 给足推理空间。
    "max_tokens": {
        "classifier": 256,
        "objective_reasoning": 4096,
        "reasoning": 12288,         # 默认值，实际按难度分级覆盖
        "python": 8192,
        "reasoning_compressed": 12288,  # 压缩重试（prefill 抑制 CoT）
        "python_compressed": 8192,      # 代回核验/复算裁决的代码生成
        "reconciliation": 16384,
        "semantic_arbiter": 256,
        "coordinator": 16384,
        "emergency_answer": 1280,
    },
    "reasoning_tokens_by_difficulty": {"easy": 8192, "medium": 12288, "hard": 16384},

    # ── 节点超时上限（秒，最后防线，真实边界由 TimeBudget 收紧）──
    "node_timeouts": {
        "input": 5,
        "classifier": 200,
        "solving": 1150,
        "reasoning_agent": 1100,
        "python_agent": 1100,
        "python_execute": 60,
        "cross_validator": 15,
        "reconciliation": 10,
        "semantic_arbiter": 150,
        "coordinator": 420,
        "critic": 120,
        "playoff": 300,
        "substitute": 240,
    },

    # ── 分类 ──
    "classifier_confidence_threshold": 0.85,

    # ── 墙钟预算（单题）──
    # 平台硬限 20 分钟；reserve 保证超时前一定能输出答案而非被强杀。
    "problem_time_budget_s": 1200,
    "time_reserve_s": 300,
    "time_fast_path_threshold_s": 300,

    # ── 难度感知软预算（可选阶段的购买力，不杀进行中调用）──
    # 全卷 112 题 / 并发 3 / 6h 上限 ⇒ 平均每题约 9.6min。
    "difficulty_soft_budgets": {"easy": 600, "medium": 840, "hard": 1200},

    # ── 全卷完成率（PaperPacer）──
    # 6h 内完成 112 题：目标 5h 完成留 1h 余量。
    "paper_total_seconds": 18000,

    # ── 单题 LLM 请求硬上限（防失控，0=不限）──
    "max_llm_calls_per_problem": 24,

    # ── 机制开关 ──
    "enable_thinking_mode_off": True,   # 关 CoT（节省时间+token，简单题无正确率差异）
    "enable_diverse_reasoning": True,   # 异构双方法推理
    "enable_critic": True,              # 过程审计
    "enable_playoff": True,             # 确定性复算裁决
    "enable_substitution_check": True,  # 单候选代回核验
    "enable_objective_revote": True,    # 客观题低置信复核
    "enable_counting_guard": True,      # 计数题枚举守护
    "enable_modular_guard": True,       # 模结构守护

    # ── 高风险领域（异构第二推理路径首轮触发）──
    "high_risk_domains": ["离散数学", "数值分析", "非基础及进阶课程", "微分几何", "测度积分"],

    # ── 调解轮数 ──
    "reconciliation_max_rounds": 2,

    # ── 符号等价匹配 ──
    "computation_tolerance": 1e-6,
    "matcher_simplify_timeout_s": 8,    # simplify 限时（秒）
    "matcher_max_sample_symbols": 4,    # 采样符号数上限

    # ── 日志 ──
    "log_level": "INFO",
    "log_dir": "logs",
}
