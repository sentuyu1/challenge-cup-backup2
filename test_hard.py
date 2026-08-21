import os, sys, time
sys.path.insert(0, ".")
from llm_client import InternChatClient
from user_agent import ReasoningAgent

# 难题：运输问题（深度 skill 有详细的最小元素法模块）
PROBLEM = "某运输问题：三个产地 A1,A2,A3 供应量分别为 7,4,9；四个销地 B1,B2,B3,B4 需求量分别为 3,6,5,6。运价矩阵为 [[3,11,3,10],[1,9,2,8],[7,4,10,5]]。用最小元素法求初始基可行解，列出全部基变量取值和总运费。"

def main():
    client = InternChatClient(timeout=300)
    agent = ReasoningAgent(client=client)
    t0 = time.time()
    result = agent.solve(PROBLEM, {"idx": 0})
    print("final_response:")
    print(result["final_response"][:800])
    print(f"\n耗时 {time.time()-t0:.0f}s")
    steps = [t.get('step') for t in result['trace']]
    print("trace:", " → ".join(steps))

if __name__ == "__main__":
    main()
