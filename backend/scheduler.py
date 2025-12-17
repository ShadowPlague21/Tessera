import asyncio
import logging
import httpx
from datetime import datetime
from backend.database import AsyncDatabase

class WorkerProxy:
    def __init__(self, worker_id, base_url, capabilities):
        self.id = worker_id
        self.base_url = base_url
        self.capabilities = capabilities
        self.status = "idle"
        self.loaded_models = []
        self.last_heartbeat = datetime.utcnow()

    def is_healthy(self):
        # Check if heartbeat is recent (e.g. < 1 min)
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() < 60

    async def run_job(self, payload: dict, timeout: int = 300):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/worker/run_job",
                json=payload,
                timeout=timeout + 10
            )
            resp.raise_for_status()
            return resp.json()

class WorkerManager:
    def __init__(self):
        self.workers = {} # id -> WorkerProxy

    def register_worker(self, worker_id, url, capabilities):
        self.workers[worker_id] = WorkerProxy(worker_id, url, capabilities)

    def all(self):
        return self.workers.values()

class Scheduler:
    def __init__(self, db: AsyncDatabase, worker_manager: WorkerManager):
        self.db = db
        self.workers = worker_manager
        self.dispatch_running = False

    async def start_dispatch_loop(self):
        """Main loop that dispatches jobs to workers."""
        logging.info("Starting dispatch loop...")
        self.dispatch_running = True
        
        while self.dispatch_running:
            try:
                # 1. Find idle worker
                worker = await self.find_idle_worker()
                if not worker:
                    await asyncio.sleep(1)
                    continue
                
                # 2. Select next job (priority + affinity)
                job = await self.select_next_job(worker)
                if not job:
                    await asyncio.sleep(1)
                    continue
                
                # 3. Dispatch
                logging.info(f"Dispatching job {job['id']} to worker {worker.id}")
                asyncio.create_task(self.dispatch_job(worker, job))
                
            except Exception as e:
                logging.error(f"Dispatch error: {e}")
                await asyncio.sleep(2)

    async def find_idle_worker(self) -> WorkerProxy | None:
        """Find a healthy worker not currently executing."""
        for worker in self.workers.all():
            if worker.status == "idle" and worker.is_healthy():
                return worker
        return None

    async def select_next_job(self, worker: WorkerProxy) -> dict | None:
        """Select highest priority job that this worker can handle."""
        # Simplified: just check priority
        for priority in [3, 2, 1, 0]:
            job = await self.db.get_next_queued_job(priority=priority, capability=worker.capabilities)
            if job:
                return job
        return None

    async def dispatch_job(self, worker: WorkerProxy, job: dict):
        """Send job to worker for execution."""
        
        # 1. Update job status
        worker.status = "busy"
        await self.db.update_job(
            job['id'],
            status="RUNNING",
            started_at=datetime.utcnow().isoformat(),
            worker_id=worker.id
        )
        
        # 2. Prepare payload
        payload = {
            "job_id": str(job['id']),
            "params": job['params'],
            "timeout_seconds": 300
        }
        
        # 3. Send to worker
        try:
            response = await worker.run_job(payload, timeout=310)
            await self.handle_job_completion(job, response)
            
        except Exception as e:
            logging.error(f"Job dispatch failed: {e}")
            await self.handle_job_failure(job, "DISPATCH_ERROR", str(e))
        finally:
            worker.status = "idle"

    async def handle_job_completion(self, job: dict, response: dict):
        """Handle successful job completion."""
        artifacts_data = response.get("artifacts", [])
        execution_time = response.get("execution_time_seconds", 0)
        
        # 1. Save artifacts
        artifact_ids = []
        for artifact in artifacts_data:
            # Need to fix up artifact data to match DB expectation
            art_record = await self.db.create_artifact({
                "job_id": job['id'],
                "type": artifact.get("type", "image"),
                "path": artifact.get("path"),
                "url": artifact.get("url"),
                "metadata": artifact.get("metadata", {})
            })
            artifact_ids.append(art_record.id)
        
        # 2. Update job
        await self.db.update_job(
            job['id'],
            status="COMPLETED",
            ended_at=datetime.utcnow().isoformat(),
            execution_time_seconds=execution_time,
            metadata={"artifact_ids": artifact_ids}
        )
        
        # 3. Deduct tokens
        user = await self.db.get_user(job['user_id'])
        await self.db.update_usage(
            user_id=user['id'],
            date=datetime.utcnow().date(),
            tokens_used_increment=job['cost_tokens'],
            jobs_completed_increment=1
        )

    async def handle_job_failure(self, job: dict, error_code: str, message: str):
        """Handle job failure."""
        await self.db.update_job(
            job['id'],
            status="FAILED",
            ended_at=datetime.utcnow().isoformat(),
            error={"code": error_code, "message": message}
        )
