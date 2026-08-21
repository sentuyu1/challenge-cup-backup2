import sys, time
sys.path.insert(0, ".")
from llm_client import InternChatClient
from user_agent import ReasoningAgent

PROBLEM = "求 n 个不同元素的划分总数（Bell 数 B_n），写出 B_4 的递推计算过程"

def main():
    client = InternChatClient(timeout=300)
    agent = ReasoningAgent(client=client)
    t0 = time.time()
    result = agent.solve(PROBLEM, {"idx": 0})
    print(f"耗时 {time.time()-t0:.0f}s")
    print("=== final_response ===")
    print(result["final_response"][:400])
    print("=== trace 关键字段 ===")
    for t in result['trace']:
        if t.get('step') == 'reasoning':
            print(f"  reasoning answer: {t.get('answer','')[:100]!r}")
        if t.get('step') == 'python_verification':
            print(f"  python answer: {t.get('answer','')[:100]!r} success={t.get('success')}")
        if t.get('step') == 'validation':
            print(f"  validation status: {t.get('status','')}")
if __name__ == "__main__":
    main()
