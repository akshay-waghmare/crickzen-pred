import asyncio
import time
import random
from crex_scraper_python.src.scheduler import AsyncScheduler

async def load_test_scheduler():
    """
    Simulate high load on the scheduler.
    """
    scheduler = AsyncScheduler()
    
    print("Starting load test...")
    start_time = time.time()
    
    # Enqueue 1000 tasks
    tasks = []
    for i in range(1000):
        priority = "LIVE" if i % 10 == 0 else "IMMINENT"
        tasks.append(scheduler.enqueue(f"match_{i}", f"http://example.com/{i}", priority))
        
    await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    print(f"Enqueued 1000 tasks in {duration:.4f}s")
    print(f"Queue size: {scheduler.qsize}")
    
    # Dequeue all
    dequeued = 0
    while scheduler.qsize > 0:
        task = await scheduler.next_task()
        await scheduler.task_done(task)
        dequeued += 1
        
    print(f"Dequeued {dequeued} tasks.")
    await scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(load_test_scheduler())
