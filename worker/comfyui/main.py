from fastapi import FastAPI, BackgroundTasks
import asyncio
import os
import httpx
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://localhost:8000")
WORKER_ID = os.getenv("WORKER_ID", "worker-gpu-0")
MY_URL = os.getenv("WORKER_URL", "http://localhost:9000")

@app.on_event("startup")
async def startup():
    asyncio.create_task(heartbeat_loop())

async def heartbeat_loop():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{SCHEDULER_URL}/api/internal/heartbeat", json={
                    "worker_id": WORKER_ID,
                    "url": MY_URL,
                    "capabilities": ["image"]
                })
        except Exception as e:
            logging.error(f"Heartbeat failed: {e}")
        await asyncio.sleep(30)

@app.post("/worker/run_job")
async def run_job(request: dict, background_tasks: BackgroundTasks):
    # Simulate processing
    logging.info(f"Received job: {request['job_id']}")
    
    # We return the result immediately in this synchronous simulation? 
    # No, the scheduler expects a response with artifacts OR it waits?
    # The Scheduler code: response = await worker.run_job(payload, timeout=310)
    # So we must block here until done.
    
    await asyncio.sleep(5) # Simulate generation
    
    return {
        "status": "completed",
        "job_id": request['job_id'],
        "execution_time_seconds": 5.0,
        "artifacts": [
            {
                "type": "image",
                "url": "https://placehold.co/1024x1024.png", # Dummy image
                "path": "/tmp/dummy.png"
            }
        ]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
