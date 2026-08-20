"""utils/python_executor.py — Python 代码执行器（沙箱）。

在独立子进程执行生成的验证代码，超时 + 危险模块黑名单拦截。
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Dict

# 危险模块黑名单（防代码注入/系统破坏）
_FORBIDDEN = {
    "os", "subprocess", "shutil", "socket", "requests", "http", "urllib",
    "ctypes", "multiprocessing", "threading", "pathlib", "open(", "importlib",
}


class PythonExecutor:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def execute(self, code: str, timeout: int | None = None) -> Dict:
        """执行代码，返回 {"success", "stdout", "stderr", "execution_time"}。"""
        code = (code or "").strip()
        if not code:
            return {"success": False, "stdout": "", "stderr": "空代码", "execution_time": 0.0}

        # 黑名单拦截
        for word in _FORBIDDEN:
            if re.search(r"\b" + re.escape(word), code):
                return {"success": False, "stdout": "",
                        "stderr": f"[安全拦截] 代码含禁止调用: {word}", "execution_time": 0.0}

        import time
        t0 = time.time()
        try:
            r = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True,
                timeout=timeout or self.timeout,
            )
            return {
                "success": r.returncode == 0,
                "stdout": r.stdout.strip(),
                "stderr": r.stderr.strip(),
                "execution_time": round(time.time() - t0, 2),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "代码执行超时",
                    "execution_time": round(time.time() - t0, 2)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "stdout": "", "stderr": str(exc),
                    "execution_time": round(time.time() - t0, 2)}
