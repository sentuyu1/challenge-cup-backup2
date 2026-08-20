"""test_real.py — 单题真实 API 测试（key 走环境变量 INTERN_API_KEY）。"""

import os
import sys
import time

sys.path.insert(0, ".")

from llm_client import InternChatClient
from user_agent import ReasoningAgent

# 容斥原理：1~1000 中既不能被 2、3 也不能被 5 整除的数的个数 = 266
PROBLEM = "用容斥原理（Inclusion-Exclusion）求 1 到 1000 中既不能被 2、3 也不能被 5 整除的数的个数。"


def main():
    if not os.environ.get("INTERN_API_KEY"):
        print("请先设置 INTERN_API_KEY 环境变量")
        return
    client = InternChatClient(timeout=300)
    agent = ReasoningAgent(client=client)

    t0 = time.time()
    result = agent.solve(PROBLEM, {"idx": 0})
    elapsed = time.time() - t0

    print("=" * 60)
    print("final_response:")
    print(result["final_response"][:2000])
    print("=" * 60)
    print("trace 步骤：")
    for t in result["trace"]:
        detail = t.get("status") or t.get("category") or t.get("answer") or t.get("response_length", "")
        print(f"  {t.get('step')}: {str(detail)[:60]}")
    print("=" * 60)
    print(f"耗时 {elapsed:.0f}s")


if __name__ == "__main__":
    main()
