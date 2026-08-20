"""test_multi.py — 多题真实 API 测试（4 道有明确答案的计算题）。"""

import os
import sys
import time

sys.path.insert(0, ".")

from llm_client import InternChatClient
from user_agent import ReasoningAgent

# (题目, 期望答案)
CASES = [
    ("用 Gauss-Legendre 2 点求积公式的节点和权重近似计算 ∫_{-1}^{1} x^4 dx", "2/5"),
    ("用幂法（Power Method）求矩阵 [[4,1],[1,3]] 的主特征值，迭代 3 步从 (1,0)^T 开始", "5"),
    ("求 n 个不同元素的划分总数（Bell 数 B_n），写出 B_4 的递推计算过程", "B_4=15"),
    ("用生成函数方法求解递推关系 a_n = 3a_{n-1} - 2a_{n-2}，其中 a_0=1, a_1=3", "a_n=2^{n+1}-1"),
]


def main():
    if not os.environ.get("INTERN_API_KEY"):
        print("请先设置 INTERN_API_KEY 环境变量")
        return
    client = InternChatClient(timeout=300)
    agent = ReasoningAgent(client=client)

    for i, (problem, expected) in enumerate(CASES):
        t0 = time.time()
        try:
            result = agent.solve(problem, {"idx": i})
            elapsed = time.time() - t0
            final = result["final_response"]
            print(f"\n{'='*60}")
            print(f"题 {i+1}: {problem[:50]}...")
            print(f"期望答案: {expected}")
            print(f"实际答案: {final[:300]}")
            print(f"耗时 {elapsed:.0f}s")
            # trace 摘要
            steps = [t.get('step') for t in result['trace']]
            print(f"trace: {' → '.join(steps)}")
        except Exception as exc:
            print(f"\n题 {i+1} 出错: {exc}")


if __name__ == "__main__":
    main()
