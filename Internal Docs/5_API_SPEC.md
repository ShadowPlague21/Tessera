# Tessera - Complete API Specification

**Version**: 1.0  
**Status**: Production-Ready  
**Last Updated**: December 2025

---

## 1. Public API Endpoints

### Base URL
```
Production: https://api.tessera.ai
Development: http://localhost:8000
```

### Authentication
All requests require Bearer token:
```
Authorization: Bearer YOUR_API_KEY
```

---

## 2. Jobs Endpoints

### POST /api/v1/jobs - Create Job

**Request:**
```json
{
  "capability": "image",
  "params": {
    "prompt": "a beautiful sunset over mountains",
    "negative_prompt": "ugly, blurry",
    "resolution": "1024x1024",
    "steps": 20,
    "model": "sdxl",
    "seed": 42
  },
  "priority": "normal",
  "webhook_url": "https://your-app.com/webhook"
}
```

**Response (201 Created):**
```json
{
  "job_id": "job_abc123def456",
  "status": "QUEUED",
  "estimated_time_seconds": 30,
  "cost_tokens": 1.0,
  "queue_position": 5,
  "created_at": "2025-12-17T20:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid parameters
- `402 Payment Required` - Insufficient quota
- `429 Too Many Requests` - Rate limit exceeded

---

### GET /api/v1/jobs/{job_id} - Get Job Status

**Response (Queued):**
```json
{
  "job_id": "job_abc123def456",
  "status": "QUEUED",
  "queue_position": 3,
  "estimated_time_seconds": 20,
  "created_at": "2025-12-17T20:00:00Z"
}
```

**Response (Running):**
```json
{
  "job_id": "job_abc123def456",
  "status": "RUNNING",
  "progress": 45,
  "started_at": "2025-12-17T20:00:15Z"
}
```

**Response (Completed):**
```json
{
  "job_id": "job_abc123def456",
  "status": "COMPLETED",
  "created_at": "2025-12-17T20:00:00Z",
  "started_at": "2025-12-17T20:00:15Z",
  "completed_at": "2025-12-17T20:00:33Z",
  "execution_time_seconds": 18,
  "artifacts": [
    {
      "id": "artifact_xyz789",
      "type": "image",
      "url": "https://cdn.tessera.ai/outputs/job_abc123/output.png",
      "thumbnail_url": "https://cdn.tessera.ai/outputs/job_abc123/thumb.jpg",
      "format": "png",
      "width": 1024,
      "height": 1024,
      "file_size_bytes": 2048576,
      "expires_at": "2025-12-24T20:00:33Z"
    }
  ],
  "metadata": {
    "seed": 42,
    "model_used": "sdxl-1.0",
    "actual_steps": 20
  }
}
```

**Response (Failed):**
```json
{
  "job_id": "job_abc123def456",
  "status": "FAILED",
  "error": {
    "code": "WORKER_TIMEOUT",
    "message": "Worker became unresponsive during execution",
    "details": "GPU hang detected, job will be retried"
  },
  "created_at": "2025-12-17T20:00:00Z",
  "failed_at": "2025-12-17T20:02:30Z",
  "retry_available": true
}
```

---

### DELETE /api/v1/jobs/{job_id} - Cancel Job

**Response:**
```json
{
  "job_id": "job_abc123def456",
  "status": "CANCELLED",
  "cancelled_at": "2025-12-17T20:00:45Z",
  "refund_tokens": 1.0
}
```

---

### GET /api/v1/jobs - List Jobs

**Query Parameters:**
- `status` - Filter by status (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED)
- `capability` - Filter by type (image, video, text, audio)
- `limit` - Results per page (default: 20, max: 100)
- `offset` - Pagination offset
- `since` - ISO 8601 timestamp, only return jobs after this time

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "job_abc123",
      "capability": "image",
      "status": "COMPLETED",
      "created_at": "2025-12-17T20:00:00Z",
      "completed_at": "2025-12-17T20:00:33Z"
    }
  ],
  "pagination": {
    "total": 145,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

---

## 3. User Endpoints

### GET /api/v1/user/me - Get Current User

**Response:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "plan": {
    "name": "Pro",
    "tier": "pro",
    "daily_token_limit": 300,
    "priority": 2
  },
  "usage": {
    "tokens_used_today": 45,
    "tokens_remaining_today": 255,
    "reset_at": "2025-12-18T00:00:00Z"
  },
  "created_at": "2025-11-01T12:00:00Z"
}
```

---

### GET /api/v1/user/usage - Get Usage History

**Query Parameters:**
- `start_date` - ISO 8601 date
- `end_date` - ISO 8601 date

**Response:**
```json
{
  "usage": [
    {
      "date": "2025-12-17",
      "tokens_used": 45,
      "jobs_completed": 42,
      "jobs_failed": 3,
      "breakdown": {
        "image": 30,
        "video": 10,
        "text": 5
      }
    }
  ],
  "total": {
    "tokens_used": 850,
    "jobs_completed": 812,
    "average_tokens_per_day": 42.5
  }
}
```

---

## 4. Models Endpoint

### GET /api/v1/models - List Available Models

**Query Parameters:**
- `capability` - Filter by type (image, video, text, audio)

**Response:**
```json
{
  "models": [
    {
      "id": "sdxl",
      "name": "Stable Diffusion XL",
      "version": "1.0",
      "capability": "image",
      "description": "High quality image generation",
      "max_resolution": "2048x2048",
      "available_on_plan": ["free", "starter", "pro"],
      "estimated_time_seconds": 20,
      "cost_multiplier": 1.0
    },
    {
      "id": "flux-schnell",
      "name": "Flux Schnell",
      "version": "1.0",
      "capability": "image",
      "description": "Fast image generation",
      "max_resolution": "1024x1024",
      "available_on_plan": ["pro"],
      "estimated_time_seconds": 8,
      "cost_multiplier": 0.5
    }
  ]
}
```

---

## 5. Rate Limiting

### Rate Limits by Plan

| Plan | Requests/Minute | Concurrent Jobs |
|------|-----------------|-----------------|
| Free | 5 | 1 |
| Starter | 10 | 2 |
| Pro | 30 | 5 |

### Rate Limit Headers

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1702857600
```

### Rate Limit Response

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded",
    "details": "You can make 10 requests per minute. Retry after 45 seconds.",
    "retry_after": 45
  }
}
```

---

## 6. Webhooks

### Webhook Events

When you register a webhook URL, we'll POST to it when job completes.

**Webhook Payload:**
```json
{
  "event": "job.completed",
  "job_id": "job_abc123",
  "status": "COMPLETED",
  "timestamp": "2025-12-17T20:00:33Z",
  "data": {
    "job": { },
    "artifacts": [ ]
  }
}
```

**Webhook Events:**
- `job.completed` - Job finished successfully
- `job.failed` - Job failed
- `job.cancelled` - Job was cancelled

**Webhook Security:**
- We sign webhooks with HMAC-SHA256
- Verify using: `X-Tessera-Signature` header

---

## 7. Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `INVALID_PARAMS` | 400 | Invalid parameters |
| `QUOTA_EXCEEDED` | 402 | User out of tokens |
| `RATE_LIMITED` | 429 | Too many requests |
| `WORKER_TIMEOUT` | 500 | Worker didn't respond |
| `OOM` | 500 | Out of memory |
| `MODEL_NOT_FOUND` | 404 | Requested model unavailable |
| `INVALID_PROMPT` | 400 | Prompt violates content policy |

---

## 8. Internal API (Scheduler ↔ Workers)

### POST /api/internal/jobs - Create Job (Internal)

**Used by frontends to create jobs**

```json
{
  "frontend": "telegram",
  "bot_id": "tg-img-1",
  "capability": "image",
  "user_ref": "telegram:123456789",
  "reply_context": {
    "platform": "telegram",
    "chat_id": "123456789",
    "message_id": "987654321"
  },
  "params": {
    "prompt": "a beautiful sunset",
    "resolution": "1024x1024",
    "steps": 20
  }
}
```

---

### POST /api/internal/heartbeat - Worker Heartbeat

**Workers send periodic heartbeats (every 30 seconds)**

```json
{
  "worker_id": "worker-gpu-0",
  "status": "idle",
  "capabilities": ["image", "video"],
  "loaded_models": ["sdxl-1.0"],
  "gpu_memory_used_mb": 8000,
  "gpu_memory_total_mb": 16000,
  "uptime_seconds": 3600,
  "jobs_completed": 42
}
```

---

### POST /worker/run_job - Execute Job

**Scheduler dispatches a job to worker**

```json
{
  "job_id": "job_abc123",
  "engine": "comfyui",
  "workflow_id": "txt2img_sdxl",
  "model_id": "sdxl-1.0",
  "params": {
    "prompt": "a beautiful sunset over mountains",
    "negative_prompt": "ugly, blurry",
    "width": 1024,
    "height": 1024,
    "steps": 20,
    "cfg_scale": 7.0,
    "seed": 42
  },
  "timeout_seconds": 300
}
```

**Response (Success):**
```json
{
  "status": "completed",
  "job_id": "job_abc123",
  "execution_time_seconds": 18.5,
  "artifacts": [
    {
      "type": "image",
      "path": "/outputs/job_abc123/output.png",
      "format": "png",
      "width": 1024,
      "height": 1024,
      "file_size_bytes": 2048576
    }
  ]
}
```

---

### GET /worker/health - Worker Health Check

**Response:**
```json
{
  "status": "healthy",
  "worker_id": "worker-gpu-0",
  "capabilities": ["image", "video"],
  "loaded_models": ["sdxl-1.0"],
  "current_job": null,
  "gpu_status": {
    "temperature": 65,
    "utilization": 0,
    "memory_used_mb": 8000,
    "memory_total_mb": 16000
  },
  "uptime_seconds": 3600
}
```

---

### GET /worker/capabilities - Worker Capabilities

**Response:**
```json
{
  "worker_id": "worker-gpu-0",
  "engine": "comfyui",
  "version": "1.0.0",
  "capabilities": ["image", "video"],
  "supported_models": [
    {
      "id": "sdxl",
      "name": "Stable Diffusion XL",
      "type": "checkpoint",
      "size_gb": 6.5,
      "max_resolution": "2048x2048"
    }
  ],
  "hardware": {
    "gpu_name": "NVIDIA GeForce RTX 5060 Ti",
    "vram_gb": 16,
    "cuda_version": "11.8"
  }
}
```

---

**End of API Specification**