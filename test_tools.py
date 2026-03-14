"""
手动集成测试：直接调用各工具函数，打印真实返回值。
运行：python test_tools.py
需要 OmniPlan 4 已打开并有至少一个文档。
"""
import asyncio
import json
import sys

sys.path.insert(0, "src")

from omniplan_mcp.tasks import query_tasks, get_task, create_task, update_task, delete_task


def pretty(label: str, result: str):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    try:
        print(json.dumps(json.loads(result), indent=2, ensure_ascii=False))
    except Exception:
        print(result)


async def main():
    # 1. 查询所有任务
    r = await query_tasks()
    pretty("query_tasks (all)", r)

    tasks = json.loads(r)
    if not tasks:
        print("\n没有找到任何任务，后续测试跳过。")
        return

    first_id = tasks[0]["id"]
    first_title = tasks[0]["title"]
    print(f"\n第一个任务: id={first_id}, title={first_title}")

    # 2. 按关键词查询
    kw = first_title[:3] if len(first_title) >= 3 else first_title
    r = await query_tasks(keyword=kw)
    pretty(f"query_tasks (keyword={kw!r})", r)

    # 3. 查询未完成任务
    r = await query_tasks(completed=False)
    pretty("query_tasks (completed=False)", r)

    # 4. 获取单个任务
    r = await get_task(first_id)
    pretty(f"get_task ({first_id})", r)

    # 5. 创建任务
    r = await create_task(title="[测试任务] auto-test", note="由 test_tools.py 创建")
    pretty("create_task", r)
    new_task = json.loads(r)
    new_id = new_task["id"]

    # 6. 更新任务
    r = await update_task(task_id=new_id, title="[测试任务] updated")
    pretty(f"update_task ({new_id})", r)

    # 7. 标记完成
    r = await update_task(task_id=new_id, completed=True)
    pretty(f"update_task completed=True ({new_id})", r)

    # 8. 删除刚创建的任务
    r = await delete_task(new_id)
    pretty(f"delete_task ({new_id})", r)

    print("\n\n全部测试完成。")


if __name__ == "__main__":
    asyncio.run(main())
