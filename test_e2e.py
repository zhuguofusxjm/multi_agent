"""测试脚本 — 验证各Agent场景"""
import httpx
import json
import asyncio

BASE = "http://127.0.0.1:8000"


async def chat(message: str, session_id: str | None = None) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        resp = await client.post(f"{BASE}/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


async def main():
    print("=" * 60)
    print("测试1: 问数Agent — 广东省5G用户月均流量")
    print("=" * 60)
    r = await chat("广东省5G用户月均流量是多少")
    print(f"active_agent: {r['active_agent']}")
    print(f"reply: {r['reply'][:200]}")
    print(f"metadata: {r['metadata']}")
    sid = r["session_id"]

    print("\n" + "=" * 60)
    print("测试2: 设计Agent — 设计套餐")
    print("=" * 60)
    r = await chat("帮我设计一个面向年轻人的5G套餐", sid)
    print(f"active_agent: {r['active_agent']}")
    print(f"reply: {r['reply'][:300]}")
    print(f"side_panel type: {r['side_panel']['type'] if r['side_panel'] else None}")
    if r["side_panel"]:
        print(f"matched cases: {len(r['side_panel']['data'])}")

    print("\n" + "=" * 60)
    print("测试3: 多轮修改 — 调整设计")
    print("=" * 60)
    r = await chat("流量再多给一些，加到50GB", sid)
    print(f"active_agent: {r['active_agent']}")
    print(f"reply: {r['reply'][:300]}")

    print("\n" + "=" * 60)
    print("测试4: 配置Agent — 配置套餐")
    print("=" * 60)
    r = await chat("帮我配置一个月费99元的畅享套餐", sid)
    print(f"active_agent: {r['active_agent']}")
    print(f"reply: {r['reply'][:300]}")
    if r["side_panel"]:
        print(f"config_tree: {json.dumps(r['side_panel'], ensure_ascii=False, indent=2)[:300]}")

    print("\n" + "=" * 60)
    print("测试5: 配置Agent多轮 — 继续配置资费")
    print("=" * 60)
    r = await chat("继续", sid)
    print(f"active_agent: {r['active_agent']}")
    print(f"reply: {r['reply'][:300]}")

    print("\n全部测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
