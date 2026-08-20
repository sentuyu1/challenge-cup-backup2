"""test_e2e.py — 端到端 mock 测试（验证图结构能跑通）。"""

import sys

sys.path.insert(0, ".")

from user_agent import ReasoningAgent


class MockClient:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.2, max_tokens=4096, thinking_mode=None):
        self.calls += 1
        text = " ".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
        if "只输出 JSON" in text and "category" in text:
            return '{"category": "数学分析", "question_mode": "computation", "difficulty": "medium", "confidence": 0.9}'
        if "验证状态" in text or "PLAYOFF_RESULT" in text:
            return '```python\nprint("验证状态: PASS")\nprint("最终答案: 2*pi")\n```'
        if "核验结果" in text:
            return '```python\nprint("核验结果: PASS")\n```'
        if "## 问题分析" in text or "严格按以下格式" in text:
            return "## 问题分析\n计算圆的面积\n\n## 详细解题步骤\n步骤1：计算 r=1\n\n## 最终答案\n2*pi\n\n## 关键验证点\n- 验证"
        if "仲裁" in text:
            return "SELECT:A"
        if "verdict" in text:
            return '{"verdict": "pass", "missing": [], "calc_checks": []}'
        if "教学专家" in text:
            return "最终答案：2π"
        return "2*pi"


def main():
    client = MockClient()
    agent = ReasoningAgent(client=client)
    result = agent.solve("求半径为 1 的圆的面积", {"idx": 0})

    print("=== final_response ===")
    print(result["final_response"][:300])
    print()
    print("=== trace 步骤 ===")
    for t in result["trace"]:
        detail = t.get("status") or t.get("category") or t.get("answer") or t.get("response_length", "")
        print(f"  {t.get('step')}: {str(detail)[:40]}")
    print()
    print("=== 总 LLM 调用次数 ===", client.calls)

    assert result["final_response"].strip(), "final_response 不能为空"
    assert len(result["trace"]) > 0, "trace 不能为空"
    print("\n✅ 端到端测试通过")


if __name__ == "__main__":
    main()
