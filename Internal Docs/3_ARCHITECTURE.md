# Tessera - Complete Architecture & System Design

**Version**: 1.0  
**Last Updated**: December 2025

---

## 1. 3-Layer Architecture Overview

```
┌──────────────────────────────────────────────┐
│           Layer 1: Frontends                 │
│              (Ingress Layer)                 │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Telegram  │  │ Discord  │  │ Website  │  │
│  │  Bots    │  │  Bots    │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│       (12 bot instances)     (Next.js)      │
└─────────────────┬────────────────────────────┘
│
│ HTTP/JSON API (Port 8000)
│
┌─────────────────▼────────────────────────────┐
│      Layer 2: Control Plane                  │
│         (Orchestration Layer)                │
│                                              │
│  ┌──────────────────────────────────────┐  │
│  │     Scheduler (FastAPI)              │  │
│  │  -  Job Creation & Lifecycle          │  │
│  │  -  Queue Management                  │  │
│  │  -  Worker Coordination               │  │
│  │  -  Billing & Quota Enforcement       │  │
│  └──────────────┬───────────────────────┘  │
│                 │                            │
│  ┌──────────────▼───────────────────────┐  │
│  │     PostgreSQL Database              │  │
│  │  (Single Source of Truth)            │  │
│  └──────────────────────────────────────┘  │
└─────────────────┬────────────────────────────┘
│
│ Internal API (Port 9000)
│
┌─────────────────▼────────────────────────────┐
│         Layer 3: Workers                     │
│        (Execution Layer)                     │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ ComfyUI  │  │ Kobold   │  │ Whisper  │  │
│  │ Worker   │  │ Worker   │  │ Worker   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│      (GPU-bound Podman containers)          │
└──────────────────────────────────────────────┘
```

---

## 2. Core Architectural Principles

### 2.1 Invariants (NEVER Violate)

1. **Frontends are stateless and replaceable**
   - No business logic
   - No direct worker communication
   - Ephemeral state only

2. **Control Plane is single source of truth**
   - Only component that writes to database
   - Makes all scheduling decisions
   - Enforces all business rules

3. **Workers are dumb executors**
   - No user awareness
   - No billing knowledge
   - No scheduling decisions

4. **Database represents authority**
   - Job state is canonical
   - No caching of critical state
   - Consistency over performance

5. **Horizontal scaling, not vertical complexity**
   - Add more bots, not smarter bots
   - Add more workers, not faster workers
   - Scale by replication, not optimization

---

## 3. Physical Deployment

### 3.1 Hardware Topology

**PC2 (Control Plane):**
- CPU: Intel i5-10400F
- RAM: 32GB
- OS: Linux/Windows
- Runs: All Frontends, Scheduler, PostgreSQL

**PC1 (Worker Node):**
- CPU: AMD Ryzen 7 5700X
- RAM: 64GB
- GPU: RTX 5060 Ti 16GB
- OS: Windows 11 + WSL2 Ubuntu
- Runs: All Workers (Podman in WSL)

**Network:** 10Gbps LAN connection

---

## 4. Component Breakdown

### 4.1 Layer 1: Frontends

**Telegram Bots (6 instances):**
- tg-image-bot-1, tg-image-bot-2, tg-image-bot-3
- tg-video-bot-1, tg-video-bot-2, tg-video-bot-3

**Discord Bots (6 instances):**
- dc-image-bot-1, dc-image-bot-2, dc-image-bot-3
- dc-video-bot-1, dc-video-bot-2, dc-video-bot-3

**Website (1 instance):**
- tessera-web (Next.js)

**Responsibilities:**
- Parse user input
- Per-bot rate limiting (in-memory)
- Create job requests
- Poll job status
- Reply with outputs

**Strictly NOT Allowed:**
- Access database directly
- Talk to workers
- Make billing decisions
- Batch jobs
- Schedule jobs

### 4.2 Layer 2: Control Plane

**Scheduler (FastAPI):**
- `/api/v1/jobs` - Create job
- `/api/v1/jobs/{job_id}` - Get job status
- `/api/v1/jobs/{job_id}` - Cancel job
- `/api/internal/heartbeat` - Worker heartbeat
- `/api/internal/jobs` - Internal job creation

**Database (PostgreSQL):**
- Users table - Platform identification
- Plans table - Plan definitions
- Jobs table - Job state (canonical)
- Artifacts table - Generated outputs
- Usage_daily table - Token tracking

**Key Functions:**
1. Job lifecycle management
2. Queue management (priority-based)
3. Worker coordination
4. Billing and quota enforcement
5. Artifact management

### 4.3 Layer 3: Workers

**Worker Types:**
- ComfyUI (Image/Video generation)
- KoboldCPP (Text/LLM)
- Whisper (Speech-to-text)
- Audio (TTS/Audio generation)

**Worker Interface:**
- `GET /health` - Health check
- `GET /capabilities` - What can this worker do
- `POST /run_job` - Execute a job
- `POST /heartbeat` - Send heartbeat

**Deployment:**
- Each worker runs as Podman container
- Named: `worker-gpu-0`, `worker-gpu-1`, etc.
- Volume mounts: `/models`, `/outputs`

---

## 5. Communication Patterns

### 5.1 Frontend → Scheduler (Public API)

**Job Creation:**
```
POST /api/v1/jobs
Authorization: Bearer FRONTEND_API_KEY

{
  "frontend": "telegram",
  "bot_id": "tg-img-1",
  "capability": "image",
  "user_ref": "telegram:123456",
  "reply_context": {...},
  "params": {
    "prompt": "a beautiful sunset",
    "resolution": "1024x1024"
  }
}

Response:
{
  "job_id": "job_abc123",
  "status": "QUEUED",
  "estimated_time_seconds": 30,
  "cost_tokens": 1
}
```

### 5.2 Scheduler → Worker (Internal API)

**Job Dispatch:**
```
POST http://worker-ip:9000/run_job
Authorization: Bearer INTERNAL_TOKEN

{
  "job_id": "job_abc123",
  "engine": "comfyui",
  "model_id": "sdxl-1.0",
  "params": {...}
}

Response:
{
  "status": "completed",
  "artifacts": [{...}]
}
```

### 5.3 Worker → Scheduler (Health)

**Heartbeat (every 30 seconds):**
```
POST http://scheduler-ip:8000/api/internal/heartbeat

{
  "worker_id": "worker-gpu-0",
  "status": "idle",
  "gpu_memory_used": 8000,
  "loaded_models": ["sdxl-1.0"]
}
```

---

## 6. Job State Machine

```
┌─────────┐
│ CREATED │ Job record created in DB
└────┬────┘
     │
     ▼
┌─────────┐
│ QUEUED  │ Waiting in priority queue
└────┬────┘
     │
     ▼
┌─────────┐
│ RUNNING │ Dispatched to worker, executing
└────┬────┘
     │
     ├────► COMPLETED (success)
     ├────► FAILED (error during execution)
     └────► CANCELLED (user/system cancelled)
```

**State Transitions:**
- `CREATED → QUEUED`: Automatically after validation
- `QUEUED → RUNNING`: When worker selected and job dispatched
- `RUNNING → COMPLETED`: Worker reports success + artifact
- `RUNNING → FAILED`: Worker reports error or timeout
- `QUEUED/RUNNING → CANCELLED`: User request or system timeout

---

## 7. Queue Management

### 7.1 Priority Levels

```
Priority 0: FREE (20 tokens/day)
Priority 1: STARTER ($5/month, 120 tokens/day)
Priority 2: PRO ($12/month, 300 tokens/day)
Priority 3: ADMIN (unlimited)
```

### 7.2 Queue Selection Algorithm

```python
def select_next_job(worker):
    # Try each queue in priority order
    for priority in [3, 2, 1, 0]:
        queue = queues[priority]
        
        # Get jobs this worker can handle
        job = queue.peek_compatible(worker.capabilities)
        if job:
            # Consider model affinity optimization
            if matches_loaded_model(job):
                return queue.pop()  # Priority: skip model loading
    
    # If no affinity match, return highest priority job
    return highest_priority_job_across_all_queues()
```

### 7.3 Model Affinity Optimization

If worker already has model loaded, prioritize jobs for that model to avoid reload overhead:

```
Same Model: 0-5 seconds overhead
Different Model: 30-60 seconds overhead
```

---

## 8. Scaling Strategy

### 8.1 Current Single GPU

```
Capacity: 200-300 images/day
Throughput: 1 image per 20-30 seconds
Concurrent Jobs: 1
Bottleneck: GPU
```

### 8.2 Add Second GPU (Same Machine)

```
PC1:
- GPU 0: ComfyUI Worker 1
- GPU 1: ComfyUI Worker 2

Capacity: 2x
No code changes needed
Scheduler automatically distributes
```

### 8.3 Add Second Machine

```
PC1: Worker 1, Worker 2
PC3: Worker 3, Worker 4

Capacity: 4x
Workers register with scheduler
Scheduler load balances
```

### 8.4 Specialized Workers

```
PC1: Image workers (2x RTX 5060 Ti)
PC3: Video workers (2x RTX 4090)
PC4: LLM workers (CPU-based)

Scheduler routes by capability
No architectural changes
```

---

## 9. Failure Modes & Recovery

| Component | Impact | Detection | Recovery |
|-----------|--------|-----------|----------|
| Bot Instance | Users of that bot can't submit | Health check fails | Restart bot, traffic routes to other bots |
| Scheduler | No new jobs accepted | Health check fails | Restart scheduler, jobs resume from DB state |
| Database | Complete system failure | Connection errors | PostgreSQL HA, manual intervention |
| Worker | Jobs fail, queue backs up | Heartbeat timeout | Restart worker, jobs requeued |
| GPU Hang | Worker unresponsive | Heartbeat timeout | Hard restart worker container |
| Network | Components can't communicate | Connection timeouts | Check network, restart affected services |

---

## 10. Monitoring & Observability

### 10.1 Key Metrics

**System Health:**
- Worker heartbeat status
- Queue depth per priority
- Database connection pool
- API response times

**Business Metrics:**
- Jobs created per hour
- Jobs completed per hour
- Completion rate (success/total)
- Average job latency
- Revenue per day

**Resource Metrics:**
- GPU utilization %
- GPU memory usage
- CPU usage
- Disk I/O

### 10.2 Critical Alerts

- Worker offline > 5 minutes
- Database unreachable
- Queue depth > 100
- Job failure rate > 20%
- GPU memory > 90%

---

## 11. Security Boundaries

```
┌─────────────────────────────────────────┐
│         UNTRUSTED ZONE                  │
│  -  User Input                           │
│  -  Platform APIs (Telegram/Discord)    │
└─────────────────┬───────────────────────┘
     │
     [Sanitization & Validation]
     │
┌────────────────▼──────────────────────┐
│      SEMI-TRUSTED ZONE                │
│  -  Frontends                          │
│  -  Rate Limiting                      │
└────────────────┬──────────────────────┘
     │
     [Authentication & Authorization]
     │
┌────────────────▼──────────────────────┐
│       TRUSTED ZONE                    │
│  -  Control Plane                      │
│  -  Database                           │
│  -  Internal APIs                      │
└────────────────┬──────────────────────┘
     │
     [Secure Internal Channel]
     │
┌────────────────▼──────────────────────┐
│      ISOLATED ZONE                    │
│  -  Workers (GPU execution)            │
│  -  No external network access         │
└────────────────────────────────────────┘
```

**Rules:**
- Untrusted data NEVER reaches workers directly
- Workers NEVER communicate with frontends
- Database NEVER accessed by frontends or workers directly

---

## 12. Data Model

### Users
```
{
  id, platform, platform_user_id, plan_id,
  email, api_key, created_at
}
```

### Plans
```
{
  id, name, daily_tokens, priority,
  max_resolution, allowed_models, price_cents
}
```

### Jobs (Canonical State)
```
{
  id, user_id, frontend, capability, status,
  params, cost_tokens, worker_id,
  created_at, started_at, ended_at
}
```

### Artifacts
```
{
  id, job_id, type, url, format,
  width, height, file_size, created_at
}
```

---

## 13. Future Considerations

### 13.1 Migration from WSL to Bare Linux

1. Backup all models and configs
2. Install Ubuntu on PC1
3. Deploy workers natively (no WSL overhead)
4. Update worker IP in scheduler config
5. Gradual migration (run both temporarily)
6. Decommission WSL once stable

**Zero downtime possible** because scheduler treats all workers uniformly.

### 13.2 Kubernetes Migration (Optional, Future)

- Convert Podman containers to Kubernetes Deployments
- Use Kubernetes for worker orchestration
- Scheduler remains largely unchanged
- Add Kubernetes service discovery
- Use persistent volumes for models

---

**End of Architecture Document**

This architecture is designed for:
- ✅ Current constraints (single GPU, WSL)
- ✅ Near-term growth (multiple GPUs, multiple machines)
- ✅ Long-term scale (cloud, Kubernetes, geo-distribution)

All without requiring a redesign.