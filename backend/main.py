from fastapi import FastAPI, HTTPException, Depends
from backend.models import JobRequest, JobResponse
from backend.database import AsyncDatabase
from backend.scheduler import Scheduler, WorkerManager
from datetime import datetime
from decimal import Decimal
import os
import asyncio
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)

# Config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/tessera")

app = FastAPI(title="Tessera Scheduler")

# Singletons
db = AsyncDatabase(DATABASE_URL)
worker_manager = WorkerManager()
scheduler = Scheduler(db, worker_manager)

@app.on_event("startup")
async def startup():
    await db.connect()
    asyncio.create_task(scheduler.start_dispatch_loop())

@app.on_event("shutdown")
async def shutdown():
    scheduler.dispatch_running = False
    await db.disconnect()

async def get_db():
    return db

def calculate_token_cost(params: dict) -> Decimal:
    # Simplified cost calculation
    capability = params.get("capability")
    if capability == "image":
        return Decimal("1.0")
    return Decimal("0.5")

def estimate_job_time(job, queue_position: int) -> int:
    return (queue_position + 1) * 20

@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(request: JobRequest, db: AsyncDatabase = Depends(get_db)):
    # 1. Get or create user
    # Simplified user_ref parsing
    platform = request.frontend
    uid = request.user_ref.split(":")[-1]
    
    user = await db.get_or_create_user(
        platform=platform,
        platform_uid=uid
    )
    
    # 2. Check quota
    usage_today = await db.get_usage(
        user_id=user['id'],
        date=datetime.utcnow().date()
    )
    
    # Check limit (simplified, assuming free plan if plan data missing)
    limit = user.get('daily_token_limit', 20)
    
    cost = calculate_token_cost(request.params)
    
    if usage_today.tokens_used + cost > limit:
         raise HTTPException(status_code=402, detail="Insufficient quota")

    # 3. Create Job
    job_data = {
        "user_id": user['id'],
        "frontend": request.frontend,
        "bot_id": request.bot_id,
        "capability": request.capability,
        "status": "CREATED",
        "priority": user.get('priority', 0),
        "params": request.params,
        "cost_tokens": float(cost), # float for json serialization
        "reply_context": request.reply_context,
        "created_at": datetime.utcnow()
    }
    
    job = await db.create_job(job_data)
    
    # 4. Enqueue
    await db.update_job(job.id, status="QUEUED", queued_at=datetime.utcnow().isoformat())
    
    # 5. Stats
    queue_pos = await db.count_queued_jobs_before(job.id, job_data['priority'])
    est_time = estimate_job_time(job, queue_pos)
    
    return JobResponse(
        job_id=str(job.id),
        status="QUEUED",
        estimated_time_seconds=est_time,
        cost_tokens=cost,
        queue_position=queue_pos
    )

@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncDatabase = Depends(get_db)):
    # Needed: implement get_job in db
    # For now, placeholder
    pass

@app.post("/api/internal/heartbeat")
async def heartbeat(worker_data: dict):
    worker_manager.register_worker(
        worker_id=worker_data['worker_id'],
        url=worker_data.get('url', 'http://localhost:8188'), # Default if not sent
        capabilities=worker_data.get('capabilities', ['image'])
    )
    return {"status": "ok"}
