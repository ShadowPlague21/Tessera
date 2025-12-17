from fastapi import FastAPI, BackgroundTasks
import asyncio
import os
import httpx
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://localhost:8000")
WORKER_ID = os.getenv("WORKER_ID", "worker-gpu-2")
MY_URL = os.getenv("WORKER_URL", "http://localhost:9002")

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
                    "capabilities": ["audio"]
                })
        except Exception as e:
            logging.error(f"Heartbeat failed: {e}")
        await asyncio.sleep(30)

@app.post("/worker/run_job")
async def run_job(request: dict, background_tasks: BackgroundTasks):
    logging.info(f"Received audio job: {request['job_id']}")
    
    # Simulate Whisper or TTS
    await asyncio.sleep(3)
    
    return {
        "status": "completed",
        "job_id": request['job_id'],
        "execution_time_seconds": 3.0,
        "artifacts": [
            {
                "type": "text", # e.g. transcription
                "metadata": {"transcription": "Simulated transcription text."},
                "path": None,
                "url": None
            }
        ]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
