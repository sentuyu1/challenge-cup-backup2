"""nodes/python_agent_node.py — Python/SymPy 独立计算路径。

生成并执行验证代码，独立算出答案，供交叉验证与推理路对比。
"""

from __future__ import annotations

import re

from config import CONFIG
from utils.deps import get_deps
from utils.llm_retry import chat_with_retry, thinking_mode_flag
from utils.prompt_templates import PYTHON_PROMPT
from utils.python_executor import PythonExecutor


def extract_code(text: str) -> str:
    """提取第一个 ```python ... ``` 代码块。"""
    m = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_answer(stdout: str) -> str:
    """从执行输出解析「最终答案:」。"""
    m = re.search(r"最终答案\s*[:：]\s*(.+)", stdout)
    return m.group(1).strip() if m else ""


def _parse_verification(stdout: str) -> str:
    """从执行输出解析「验证状态:」。"""
    m = re.search(r"验证状态\s*[:：]\s*(PASS|FAIL|INCONCLUSIVE)", stdout, re.IGNORECASE)
    return m.group(1).upper() if m else "INCONCLUSIVE"


def python_agent_node(state: dict, config) -> dict:
    deps = get_deps(config)
    client = deps.client
    problem = state.get("problem", "")
    category = state.get("category", "数学")
    hint = state.get("branch_hint")

    trace = []
    attempts = 0
    python_code = ""
    output = {"success": False, "stdout": "", "stderr": "", "answer": ""}

    # 验证知识提示（skill 文档的核验部分，阶段5补全）
    loader = getattr(deps, "skills_loader", None)
    validation_script = ""
    if loader is not None and callable(getattr(loader, "get_validation_script", None)):
        validation_script = loader.get_validation_script(category)[:3000]

    prompt = PYTHON_PROMPT.format(
        validation_script=validation_script, problem=problem, category=category)
    if hint:
        prompt += f"\n\n[复核提示] {hint}"

    executor = PythonExecutor(timeout=CONFIG["node_timeouts"]["python_execute"])

    max_attempts = 1 if (deps.time_budget and deps.time_budget.fast_path()) else 2
    for _ in range(max_attempts):
        attempts += 1
        try:
            resp = chat_with_retry(
                client, messages=[{"role": "user", "content": prompt}],
                temperature=CONFIG["temperatures"]["python"],
                max_tokens=CONFIG["max_tokens"]["python"],
                logger=deps.logger, time_budget=deps.time_budget,
                label="python_agent", thinking_mode=thinking_mode_flag(),
            )
        except Exception as exc:  # noqa: BLE001
            trace.append({"attempt": attempts, "status": "failed", "error": str(exc)[:200]})
            break

        python_code = extract_code(resp)
        if not python_code:
            trace.append({"attempt": attempts, "status": "no_code"})
            # 无代码块，带提醒重试
            prompt += "\n\n注意：必须只输出一个 ```python``` 代码块。"
            continue

        result = executor.execute(python_code)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        answer = _parse_answer(stdout)
        verification = _parse_verification(stdout)

        output = {
            "success": result.get("success", False),
            "stdout": stdout,
            "stderr": stderr,
            "answer": answer,
            "execution_time": result.get("execution_time", 0.0),
            "verification_status": verification,
        }
        if answer or result.get("success"):
            break
        # 执行失败，带错误反馈重试
        prompt += f"\n\n上次代码执行出错：{stderr[:200]}\n请修正代码。"
        trace.append({"attempt": attempts, "status": "exec_error", "stderr": stderr[:200]})

    return {
        "python_code": python_code,
        "python_output": output,
        "python_trace": trace,
        "python_attempts": attempts,
    }
