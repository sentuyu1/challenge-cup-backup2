"""main.py — 本地批处理入口（含 PaperPacer 全卷预算）。

读 JSONL 输入，并发求解，写每题的 JSON 输出。PaperPacer 按
「剩余全卷时间 ÷ 剩余题数」动态收紧每题软预算，保证 6h 内 112 题全部完成。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Dict, List

from config import CONFIG
from llm_client import InternChatClient
from user_agent import ReasoningAgent

LOCAL_MAX_CONCURRENCY = int(__import__("os").environ.get("LOCAL_MAX_CONCURRENCY", "3"))


class PaperPacer:
    """全卷预算池：目标 5h 完成 112 题（留 1h 余量给 API 波动）。"""

    def __init__(self, total_seconds: float, total_problems: int):
        self._lock = threading.Lock()
        self.remaining_seconds = float(total_seconds)
        self.remaining_problems = int(total_problems)
        self._start = time.monotonic()

    def next_cap(self) -> float:
        with self._lock:
            if self.remaining_problems <= 0:
                return float(CONFIG["problem_time_budget_s"])
            return max(300.0, self.remaining_seconds / self.remaining_problems)

    def record(self) -> None:
        with self._lock:
            self.remaining_problems = max(0, self.remaining_problems - 1)


def load_jsonl(path: Path) -> List[Dict]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f):
            if not line.strip():
                continue
            item = json.loads(line)
            item.setdefault("idx", line_number)
            items.append(item)
    return items


def is_processed(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def write_json(path: Path, record: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def solve_item(agent: ReasoningAgent, item: Dict, pacer: PaperPacer) -> Dict:
    metadata = {"idx": item["idx"]}
    for key in ("type", "question_mode", "question_type", "subject", "category"):
        if key in item:
            metadata[key] = item[key]
    cap = pacer.next_cap()
    result = agent.solve(problem=item["problem"], metadata=metadata, paper_cap=cap)
    pacer.record()
    final_response = result.get("final_response", "")
    if not isinstance(final_response, str) or not final_response.strip():
        raise ValueError("solve 必须返回非空 final_response 字符串")
    return {
        "idx": item["idx"],
        "status": "success",
        "final_response": final_response,
        "trace": result.get("trace", []),
    }


async def process_item(agent, item, output_dir, pacer, semaphore) -> None:
    path = output_dir / f"{item['idx']}.json"
    if is_processed(path):
        print(f"跳过 idx={item['idx']}（已存在）")
        pacer.record()
        return
    async with semaphore:
        try:
            record = await asyncio.to_thread(solve_item, agent, item, pacer)
        except Exception as exc:  # noqa: BLE001
            record = {"idx": item["idx"], "status": "error", "final_response": "",
                      "error": {"type": type(exc).__name__, "message": str(exc)}}
        await asyncio.to_thread(write_json, path, record)
        print(f"完成 idx={item['idx']}")


async def run(args) -> None:
    items = load_jsonl(Path(args.input_file))
    client = InternChatClient()
    agent = ReasoningAgent(client=client)
    pacer = PaperPacer(CONFIG["paper_total_seconds"], len(items))
    semaphore = asyncio.Semaphore(LOCAL_MAX_CONCURRENCY)

    print(f"加载 {len(items)} 题，并发 {LOCAL_MAX_CONCURRENCY}")
    tasks = [process_item(agent, item, Path(args.output_dir), pacer, semaphore)
             for item in items]
    await asyncio.gather(*tasks)
    print(f"完成，输出到 {args.output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="数学智能体本地批处理")
    parser.add_argument("--input_file", required=True, help="JSONL 输入路径")
    parser.add_argument("--output_dir", required=True, help="输出目录")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
