# Tessera - Component Logic & Implementation Guide

**Version**: 1.0  
**Last Updated**: December 2025

---

## 1. Scheduler Core Logic (FastAPI)

### 1.1 Job Creation Endpoint

```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
from decimal import Decimal

app = FastAPI()

class JobRequest(BaseModel):
    frontend: str  # "telegram", "discord", "web"
    bot_id: str | None
    capability: str  # "image", "video", "text", "audio"
    user_ref: str  # "telegram:123456" or "web:user_id"
    params: dict
    reply_context: dict | None

class JobResponse(BaseModel):
    job_id: str
    status: str
    estimated_time_seconds: int
    cost_tokens: Decimal
    queue_position: int

@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(
    request: JobRequest,
    db: AsyncDatabase = Depends(get_db)
):
    # 1. Get or create user
    user = await db.get_or_create_user(
        platform=request.frontend,
        platform_uid=extract_user_id(request.user_ref),
        ip_address=request.client.host
    )
    
    # 2. Check quota
    usage_today = await db.get_usage(
        user_id=user.id,
        date=datetime.utcnow().date()
    )
    
    plan = user.plan
    tokens_used = usage_today.tokens_used
    tokens_remaining = plan.daily_token_limit - tokens_used
    
    # 3. Calculate cost
    cost = calculate_token_cost(request.params)
    
    if cost > tokens_remaining:
        raise HTTPException(
            status_code=402,
            detail="Insufficient quota. Upgrade plan or wait for reset."
        )
    
    # 4. Validate params
    try:
        validate_params(request.params, request.capability)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 5. Create job record (CREATED state)
    job = await db.create_job({
        "user_id": user.id,
        "frontend": request.frontend,
        "bot_id": request.bot_id,
        "capability": request.capability,
        "status": "CREATED",
        "priority": user.plan.priority,
        "params": request.params,
        "cost_tokens": cost,
        "reply_context": request.reply_context,
        "created_at": datetime.utcnow()
    })
    
    # 6. Enqueue (QUEUED state)
    await db.update_job(job.id, status="QUEUED", queued_at=datetime.utcnow())
    
    # 7. Calculate queue position
    queue_position = await db.count_queued_jobs_before(
        job_id=job.id,
        priority=user.plan.priority
    )
    
    # 8. Estimate time
    estimated_time = estimate_job_time(job, queue_position)
    
    return JobResponse(
        job_id=str(job.id),
        status="QUEUED",
        estimated_time_seconds=estimated_time,
        cost_tokens=cost,
        queue_position=queue_position
    )

def calculate_token_cost(params: dict) -> Decimal:
    """
    Calculate token cost based on parameters.
    1 token = 1 image @ 1024x1024
    """
    capability = params.get("capability")
    
    if capability == "image":
        resolution = params.get("resolution", "1024x1024")
        width, height = map(int, resolution.split("x"))
        pixels = width * height
        base_tokens = Decimal(pixels) / Decimal(1024 * 1024)
        
        # Adjust for steps (more steps = more cost)
        steps = params.get("steps", 20)
        step_multiplier = Decimal(steps) / Decimal(20)
        
        return base_tokens * step_multiplier
    
    elif capability == "video":
        duration_seconds = params.get("duration", 5)
        fps = params.get("fps", 24)
        resolution = params.get("resolution", "720p")
        
        # Rough estimate: 3 tokens for 5-second 720p video
        return Decimal(duration_seconds) * Decimal(3) / Decimal(5)
    
    elif capability == "text":
        # LLM tokens: 1 token = 1000 output tokens
        output_tokens = params.get("max_tokens", 100)
        return Decimal(output_tokens) / Decimal(1000)
    
    return Decimal("0.5")  # Default

def estimate_job_time(job: Job, queue_position: int) -> int:
    """Estimate how long until job completes (in seconds)."""
    
    # Average job time: 20 seconds for image, 30 for video
    avg_job_time = 20 if job.capability == "image" else 30
    
    # Queue wait time
    queue_wait = queue_position * avg_job_time
    
    # Add model loading time if needed (rough estimate)
    model_load_time = 30 if queue_position > 5 else 5
    
    return queue_wait + model_load_time
```

### 1.2 Dispatch Loop

```python
class Scheduler:
    def __init__(self, db, worker_manager):
        self.db = db
        self.workers = worker_manager
        self.dispatch_running = False
    
    async def start_dispatch_loop(self):
        """Main loop that dispatches jobs to workers."""
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
                
                # 3. Try to batch jobs
                batch = await self.try_assemble_batch(job, worker)
                
                # 4. Dispatch
                if batch:
                    await self.dispatch_batch(worker, batch)
                else:
                    await self.dispatch_job(worker, job)
                    
            except Exception as e:
                logging.error(f"Dispatch error: {e}")
                await asyncio.sleep(2)
    
    async def find_idle_worker(self) -> Worker | None:
        """Find a healthy worker not currently executing."""
        for worker in self.workers.all():
            if worker.status == "idle" and worker.is_healthy():
                return worker
        return None
    
    async def select_next_job(self, worker: Worker) -> Job | None:
        """Select highest priority job that this worker can handle."""
        
        # Check for model affinity (job for already-loaded model)
        loaded_models = worker.loaded_models
        if loaded_models:
            affinity_job = await self.db.get_job_with_model(
                models=loaded_models,
                statuses=["QUEUED"],
                limit=1
            )
            if affinity_job:
                return affinity_job
        
        # Otherwise, select by priority
        for priority in [3, 2, 1, 0]:  # Admin, Pro, Starter, Free
            job = await self.db.get_next_queued_job(
                priority=priority,
                capability=worker.capabilities
            )
            if job:
                return job
        
        return None
    
    async def try_assemble_batch(self, first_job: Job, worker: Worker) -> list[Job] | None:
        """Try to batch multiple jobs with same parameters."""
        
        # Batching conditions:
        # - GPU idle initially
        # - Same model, resolution, steps, etc.
        # - At least 2 jobs available
        
        batch_key = {
            "engine": first_job.params.get("engine"),
            "model": first_job.params.get("model"),
            "resolution": first_job.params.get("resolution"),
            "steps": first_job.params.get("steps"),
        }
        
        # Find similar jobs in queue
        similar_jobs = await self.db.find_jobs_with_params(
            batch_key=batch_key,
            status="QUEUED",
            limit=4
        )
        
        if len(similar_jobs) < 2:
            return None  # Not enough for batch
        
        return similar_jobs
    
    async def dispatch_job(self, worker: Worker, job: Job):
        """Send job to worker for execution."""
        
        # 1. Update job status
        await self.db.update_job(
            job.id,
            status="RUNNING",
            started_at=datetime.utcnow(),
            worker_id=worker.id
        )
        
        # 2. Prepare payload
        payload = {
            "job_id": str(job.id),
            "engine": job.params.get("engine"),
            "model_id": job.params.get("model"),
            "params": job.params,
            "timeout_seconds": 300
        }
        
        # 3. Send to worker
        try:
            response = await worker.run_job(payload, timeout=310)
            
            # 4. Job completed
            await self.handle_job_completion(job, response)
            
        except asyncio.TimeoutError:
            await self.handle_job_failure(
                job,
                error_code="TIMEOUT",
                message="Worker didn't respond within 5 minutes"
            )
        except Exception as e:
            await self.handle_job_failure(
                job,
                error_code="DISPATCH_ERROR",
                message=str(e)
            )
    
    async def handle_job_completion(self, job: Job, response: dict):
        """Handle successful job completion."""
        
        artifacts_data = response.get("artifacts", [])
        execution_time = response.get("execution_time_seconds", 0)
        
        # 1. Save artifacts
        artifact_ids = []
        for artifact in artifacts_data:
            artifact_record = await self.db.create_artifact({
                "job_id": job.id,
                "type": artifact.get("type"),
                "path": artifact.get("path"),
                "url": artifact.get("url"),
                "metadata": artifact.get("metadata", {})
            })
            artifact_ids.append(artifact_record.id)
        
        # 2. Update job
        await self.db.update_job(
            job.id,
            status="COMPLETED",
            ended_at=datetime.utcnow(),
            execution_time_seconds=execution_time,
            metadata={"artifact_ids": artifact_ids}
        )
        
        # 3. Deduct tokens from user
        user = await self.db.get_user(job.user_id)
        await self.db.update_usage(
            user_id=user.id,
            date=datetime.utcnow().date(),
            tokens_used_increment=job.cost_tokens,
            jobs_completed_increment=1
        )
        
        # 4. Notify frontend (webhook or polling)
        await self.notify_completion(job, artifact_ids)
    
    async def handle_job_failure(self, job: Job, error_code: str, message: str):
        """Handle job failure."""
        
        await self.db.update_job(
            job.id,
            status="FAILED",
            ended_at=datetime.utcnow(),
            error={
                "code": error_code,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Retry logic (optional)
        retry_count = job.metadata.get("retry_count", 0)
        if retry_count < 2 and error_code in ["TIMEOUT", "WORKER_ERROR"]:
            await self.db.update_job(
                job.id,
                status="QUEUED",
                metadata={"retry_count": retry_count + 1}
            )
```

---

## 2. Bot Implementation (Telegram Example)

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import httpx
from decimal import Decimal

class TelegramBot:
    def __init__(self, token: str, scheduler_url: str, bot_id: str):
        self.token = token
        self.scheduler_url = scheduler_url
        self.bot_id = bot_id
        self.rate_limiter = RateLimiter(max_requests_per_minute=30)
        self.pending_jobs = {}  # job_id → (chat_id, message_id)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command."""
        message = """
🎨 **Welcome to Tessera!**

I'm an AI image/video generator. Here's what I can do:

**/generate** `<prompt>` - Generate an image or video
**/status** `<job_id>` - Check a job's status
**/cancel** `<job_id>` - Cancel a pending job
**/plan** - View your current plan
**/upgrade** - Upgrade to paid plan

**Free Tier:** 20 tokens/day (best-effort queue)
**Starter:** $5/month, 120 tokens/day
**Pro:** $12/month, 300 tokens/day

Try: `/generate a sunset over mountains`
        """
        await update.message.reply_text(message)
    
    async def generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /generate command."""
        
        # 1. Rate limit check
        user_id = str(update.effective_user.id)
        if not self.rate_limiter.allow(user_id):
            await update.message.reply_text("⚠️ Too many requests. Please slow down!")
            return
        
        # 2. Parse prompt
        prompt = " ".join(context.args)
        if not prompt:
            await update.message.reply_text("❌ Please provide a prompt!\n\nExample: `/generate a cat sitting on a laptop`")
            return
        
        # 3. Create job request
        job_request = {
            "frontend": "telegram",
            "bot_id": self.bot_id,
            "capability": "image",
            "user_ref": f"telegram:{user_id}",
            "reply_context": {
                "chat_id": update.effective_chat.id,
                "message_id": update.message.message_id,
                "user_id": user_id
            },
            "params": {
                "prompt": prompt,
                "resolution": "1024x1024",
                "steps": 20,
                "model": "sdxl"
            }
        }
        
        # 4. Submit to scheduler
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.scheduler_url}/api/v1/jobs",
                    json=job_request,
                    headers={"Authorization": f"Bearer {FRONTEND_API_KEY}"},
                    timeout=10
                )
                
                if response.status_code != 201:
                    error = response.json()
                    if response.status_code == 402:
                        await update.message.reply_text(
                            "💰 You've run out of daily tokens!\n\nUpgrade to get more: /upgrade"
                        )
                    else:
                        await update.message.reply_text(f"❌ Error: {error.get('detail')}")
                    return
                
                data = response.json()
                job_id = data["job_id"]
                queue_position = data["queue_position"]
                estimated_time = data["estimated_time_seconds"]
                
        except Exception as e:
            await update.message.reply_text(f"❌ Service error: {str(e)}")
            return
        
        # 5. Store job context
        self.pending_jobs[job_id] = {
            "chat_id": update.effective_chat.id,
            "message_id": update.message.message_id,
            "user_id": user_id
        }
        
        # 6. Send acknowledgment
        keyboard = [
            [InlineKeyboardButton("Check Status", callback_data=f"status_{job_id}"),
             InlineKeyboardButton("Cancel", callback_data=f"cancel_{job_id}")]
        ]
        await update.message.reply_text(
            f"✅ Job created: `{job_id}`\n"
            f"📊 Queue position: {queue_position}\n"
            f"⏱️  Estimated time: {estimated_time}s\n\n"
            f"Your image will appear here soon...",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # 7. Start polling (async task)
        asyncio.create_task(self.poll_job(job_id))
    
    async def poll_job(self, job_id: str):
        """Poll job status and deliver result when ready."""
        
        context = self.pending_jobs.get(job_id)
        if not context:
            return
        
        chat_id = context["chat_id"]
        max_polls = 120  # 2 minutes max
        poll_count = 0
        
        while poll_count < max_polls:
            try:
                # Get job status
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.scheduler_url}/api/v1/jobs/{job_id}",
                        headers={"Authorization": f"Bearer {FRONTEND_API_KEY}"},
                        timeout=10
                    )
                    
                    if response.status_code != 200:
                        poll_count += 1
                        await asyncio.sleep(2)
                        continue
                    
                    job_data = response.json()
                    status = job_data["status"]
                    
                    if status == "RUNNING":
                        progress = job_data.get("progress", 0)
                        # Could update message with progress here
                    
                    elif status == "COMPLETED":
                        # Download and send artifact
                        artifact_url = job_data["artifacts"][0]["url"]
                        await self.send_photo(
                            chat_id=chat_id,
                            photo_url=artifact_url,
                            caption=f"✅ Generated!\n\nJob: `{job_id}`"
                        )
                        del self.pending_jobs[job_id]
                        return
                    
                    elif status == "FAILED":
                        error = job_data.get("error", {})
                        await self.send_message(
                            chat_id=chat_id,
                            text=f"❌ Job failed: {error.get('message')}\n\nRetry: /generate {context['prompt']}"
                        )
                        del self.pending_jobs[job_id]
                        return
                    
            except Exception as e:
                logging.error(f"Poll error for {job_id}: {e}")
            
            poll_count += 1
            await asyncio.sleep(2)
        
        # Timeout
        await self.send_message(
            chat_id=chat_id,
            text="⏱️ Job is still processing. Check status: /status " + job_id
        )
```

---

## 3. Worker Implementation (ComfyUI)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import psutil
import GPUtil
import subprocess
import json
import os

app = FastAPI()

class ComfyUIWorker:
    def __init__(self, worker_id: str, scheduler_url: str):
        self.worker_id = worker_id
        self.scheduler_url = scheduler_url
        self.gpu_device = "0"
        self.loaded_model = None
        self.current_job = None
        self.comfyui_process = None
    
    async def start(self):
        """Start ComfyUI server."""
        cmd = [
            "python", "main.py",
            "--listen", "127.0.0.1",
            "--port", "8188",
            f"--device-id", self.gpu_device
        ]
        
        self.comfyui_process = subprocess.Popen(
            cmd,
            cwd="/opt/ComfyUI",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for startup
        await asyncio.sleep(5)
        logging.info("ComfyUI started")
    
    async def health_check(self) -> dict:
        """Perform health check."""
        
        # Check process alive
        if self.comfyui_process.poll() is not None:
            raise Exception("ComfyUI process died")
        
        gpu_info = GPUtil.getGPUs()[int(self.gpu_device)]
        
        return {
            "status": "healthy",
            "worker_id": self.worker_id,
            "current_job": self.current_job,
            "loaded_model": self.loaded_model,
            "gpu": {
                "name": gpu_info.name,
                "temperature": gpu_info.temperature,
                "utilization": gpu_info.load * 100,
                "memory_used_mb": gpu_info.memoryUsed,
                "memory_total_mb": gpu_info.memoryTotal
            }
        }

@app.post("/worker/run_job")
async def run_job(request: dict):
    """Execute a job."""
    
    job_id = request["job_id"]
    model_id = request.get("model_id", "sdxl")
    params = request["params"]
    timeout = request.get("timeout_seconds", 300)
    
    worker = get_worker()
    
    # 1. Load model if needed
    if worker.loaded_model != model_id:
        logging.info(f"Loading model: {model_id}")
        await load_model(model_id)
        worker.loaded_model = model_id
    
    # 2. Prepare ComfyUI workflow
    workflow = prepare_comfyui_workflow(model_id, params)
    
    # 3. Execute
    try:
        worker.current_job = job_id
        start_time = time.time()
        
        output_images = await run_comfyui_workflow(workflow, timeout=timeout)
        
        execution_time = time.time() - start_time
        
        # 4. Save outputs
        output_paths = []
        output_dir = f"/outputs/{job_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        for idx, image_data in enumerate(output_images):
            path = f"{output_dir}/output_{idx}.png"
            with open(path, "wb") as f:
                f.write(image_data)
            output_paths.append(path)
        
        worker.current_job = None
        
        return {
            "status": "completed",
            "job_id": job_id,
            "execution_time_seconds": execution_time,
            "artifacts": [{
                "type": "image",
                "path": path,
                "format": "png"
            } for path in output_paths]
        }
    
    except asyncio.TimeoutError:
        worker.current_job = None
        return {
            "status": "failed",
            "job_id": job_id,
            "error": {
                "code": "TIMEOUT",
                "message": "Job exceeded timeout"
            }
        }
    
    except Exception as e:
        worker.current_job = None
        logging.error(f"Job {job_id} failed: {e}")
        return {
            "status": "failed",
            "job_id": job_id,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e)
            }
        }

@app.get("/worker/health")
async def get_health():
    """Health check endpoint."""
    worker = get_worker()
    return await worker.health_check()

@app.get("/worker/capabilities")
async def get_capabilities():
    """Return worker capabilities."""
    return {
        "worker_id": "worker-gpu-0",
        "engine": "comfyui",
        "capabilities": ["image", "video"],
        "supported_models": [
            {"id": "sdxl", "name": "Stable Diffusion XL", "size_gb": 6.5},
            {"id": "flux-schnell", "name": "Flux Schnell", "size_gb": 12.0}
        ]
    }
```

---

## 4. Rate Limiter Implementation

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests_per_minute: int = 30, window_minutes: int = 1):
        self.max_requests = max_requests_per_minute
        self.window = timedelta(minutes=window_minutes)
        self.requests = defaultdict(list)
    
    def allow(self, user_id: str) -> bool:
        """Check if user is allowed to make request."""
        now = datetime.utcnow()
        cutoff = now - self.window
        
        # Clean old requests
        self.requests[user_id] = [
            t for t in self.requests[user_id]
            if t > cutoff
        ]
        
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # Record request
        self.requests[user_id].append(now)
        return True
    
    def remaining(self, user_id: str) -> int:
        """Get remaining requests in window."""
        now = datetime.utcnow()
        cutoff = now - self.window
        
        valid_requests = [
            t for t in self.requests[user_id]
            if t > cutoff
        ]
        
        return max(0, self.max_requests - len(valid_requests))
```

---

**End of Component Logic**

These examples provide the core logic for all major components. Your engineer friend can use these as templates to implement the full system.