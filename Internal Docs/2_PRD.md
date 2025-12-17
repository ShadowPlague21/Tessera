# Tessera - Product Requirements Document (PRD)

**Version**: 1.0  
**Date**: December 2025  
**Status**: Approved for Development

---

## Executive Summary

Tessera is a multi-modal AI inference platform designed to serve image generation, video creation, text generation, and audio synthesis to users via Telegram bots, Discord bots, and a web interface. The platform operates on a freemium model with token-based billing and is optimized for efficient single-GPU utilization with horizontal scaling capability.

---

## 1. Product Vision

### 1.1 Mission
Provide affordable, reliable, and scalable AI generation services to creators, developers, and casual users through accessible frontends.

### 1.2 Target Users

**Primary Audience:**
- Content creators (artists, writers, YouTubers)
- Small indie game developers
- TTRPG enthusiasts
- Discord/Telegram community admins
- Students and hobbyists

**Secondary Audience:**
- Small agencies needing bulk generation
- Developers building on top of API
- Power users wanting self-hosted alternatives

### 1.3 Value Proposition
- **Accessibility**: Available via popular platforms (Telegram/Discord)
- **Affordability**: Freemium model starting at $0
- **Reliability**: Production-grade architecture
- **Transparency**: Token-based pricing, no hidden costs
- **Scalability**: Service grows with demand

---

## 2. Functional Requirements

### 2.1 Frontend Requirements

#### 2.1.1 Telegram Bots
- **Count**: 6 bots total (3 for image, 3 for video)
- **Purpose**: Bypass per-bot platform rate limits

**Core Commands:**
- `/start` - Welcome message, plan info
- `/generate <prompt>` - Create image/video
- `/status <job_id>` - Check job status
- `/cancel <job_id>` - Cancel pending job
- `/plan` - View current plan and usage
- `/upgrade` - Upgrade plan information

**Features:**
- Natural language parsing (e.g., "generate a cat at 1024x1024")
- Reply to original message with output
- Progress updates for long jobs
- Error messages with retry options
- Rate limit self-awareness

#### 2.1.2 Discord Bots
- **Count**: 6 bots total (3 for image, 3 for video)
- **Purpose**: Same as Telegram

**Core Commands:**
- `/generate prompt:<text>` - Slash command generation
- `/status job_id:<id>` - Check status
- `/cancel job_id:<id>` - Cancel job
- `/my-plan` - View plan info

#### 2.1.3 Website Frontend
- **Type**: Single scalable web application
- **Framework**: Next.js

**Pages:**
- Landing page with examples
- User dashboard (login required)
- Generation interface (all modalities)
- Job history and management
- Plan management and billing
- API key management

### 2.2 Control Plane Requirements

#### 2.2.1 Job Management
- **Job Creation**: Accept requests from any frontend
- **Job Validation**: Sanitize inputs, enforce plan limits
- **Job Lifecycle**: CREATED → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED
- **Job Persistence**: All jobs stored in database
- **Job Cancellation**: User-initiated or timeout-based

#### 2.2.2 Scheduling & Queueing
- **Queue Types**: Free tier queue, paid tier queue
- **Priority System**: Admin > Pro > Starter > Free
- **FIFO Within Priority**: Fair queueing within each tier
- **Model Affinity**: Group jobs by model to reduce loading time
- **Batching**: Optional, only when GPU idle and batch keys match

**Batch Key Components:**
- Engine (ComfyUI, KoboldCPP, etc.)
- Model ID
- Resolution (for images)
- Steps
- Precision

#### 2.2.3 Worker Coordination
- **Worker Registration**: Workers announce capabilities on startup
- **Health Checks**: 30-second heartbeats
- **Worker Selection**: Based on capability, model affinity, availability
- **Failure Handling**: Mark worker offline, requeue jobs
- **Load Balancing**: (Future) distribute across multiple workers

#### 2.2.4 Billing & Quotas
- **Token System**: 1 token = 1 image @1024x1024
- **Cost Calculation**: Dynamic based on resolution, steps, model
- **Quota Enforcement**: Hard daily limits per plan
- **Usage Tracking**: Per-user, per-day statistics
- **Overage Handling**: Block requests when quota exhausted

**Token Cost Examples:**
- 512x512 image = 0.25 tokens
- 1024x1024 image = 1 token
- 2048x2048 image = 4 tokens
- 5-second video @720p = 3 tokens
- LLM response (500 tokens) = 0.5 tokens

#### 2.2.5 Rate Limiting
- **Per-User Limits**: Based on plan (requests per minute)
- **Per-Bot Limits**: Tracked internally to respect platform limits
- **Global Limits**: Protect system from overload
- **Backpressure**: Queue depth limits, reject when full

### 2.3 Worker Requirements

#### 2.3.1 Execution Model
- **One Job at a Time**: Serial execution per GPU
- **Engine Isolation**: Only one engine running per GPU
- **Model Management**: Load/unload based on job requirements
- **Output Storage**: Generate artifacts, notify scheduler

#### 2.3.2 Supported Engines

**ComfyUI Worker:**
- Image generation (SDXL, Flux, etc.)
- Video generation (AnimateDiff, SVD)
- Headless API mode
- Custom workflow support

**KoboldCPP Worker:**
- LLM text generation
- Context management
- Streaming support

**Whisper Worker:**
- Speech-to-text
- Multiple languages
- Timestamp support

**Audio Worker:**
- Text-to-speech
- Music generation
- Voice cloning (future)

#### 2.3.3 Health & Monitoring
- **Health Endpoint**: `/health` - returns status
- **Capabilities Endpoint**: `/capabilities` - lists supported models
- **Metrics Endpoint**: `/metrics` - Prometheus format
- **Logs**: Structured JSON logs per job

### 2.4 API Requirements

#### 2.4.1 Public API
- **Authentication**: API keys with rate limits
- **Endpoints**: Job creation, status, cancellation
- **Rate Limits**: Based on plan
- **Documentation**: OpenAPI/Swagger

#### 2.4.2 Internal API
- **Scheduler ↔ Worker**: Job dispatch, status updates
- **Authentication**: Internal tokens, no public access
- **Reliability**: Retry logic, timeout handling

---

## 3. Non-Functional Requirements

### 3.1 Performance
- **Job Latency**: <5 seconds from submission to execution start (idle GPU)
- **Image Generation**: 15-30 seconds per 1024x1024 image
- **Model Loading**: <60 seconds for cold start
- **API Response Time**: <200ms for status checks
- **Database Queries**: <50ms for simple queries

### 3.2 Reliability
- **Uptime Target**: 95% (initial), 99% (post-scaling)
- **Job Completion Rate**: >98% for valid jobs
- **Data Durability**: All jobs persisted, no data loss
- **Failure Recovery**: Automatic worker restart, job requeue

### 3.3 Scalability
- **Horizontal Scaling**: Add workers without code changes
- **Frontend Scaling**: Add bots without scheduler changes
- **Database**: Supports 100K+ jobs per day
- **Concurrent Users**: 100+ simultaneous users (initial target)

### 3.4 Security
- **Input Validation**: All user inputs sanitized
- **Authentication**: OAuth for web, platform IDs for bots
- **Authorization**: Plan-based access control
- **Secrets Management**: Never expose API keys, model paths
- **Rate Limiting**: Prevent abuse and DoS
- **Audit Logging**: Track all user actions

### 3.5 Observability
- **Logging**: Structured logs for all components
- **Metrics**: Prometheus metrics (queue depth, job times, errors)
- **Alerting**: Telegram alerts for critical failures
- **Dashboards**: Grafana dashboards for ops monitoring

---

## 4. User Journeys

### 4.1 Free User Journey
1. User discovers bot via Discord server
2. Sends `/start` command
3. Bot explains free tier (20 tokens/day)
4. User sends `/generate a sunset over mountains`
5. Bot replies with image in 20 seconds
6. User loves it, uses remaining daily tokens
7. Hits limit, bot prompts upgrade

### 4.2 Paid User Journey
1. User hits free tier limit
2. Clicks upgrade link from bot
3. Redirects to website payment page
4. Selects Starter plan ($5/month)
5. Payment processed, plan activated
6. Returns to bot, generates with priority queue
7. Jobs complete faster, higher daily limit

### 4.3 Power User Journey
1. Developer signs up for API access
2. Generates API key from website dashboard
3. Integrates API into their application
4. Submits batch jobs programmatically
5. Monitors usage via dashboard
6. Scales up to Pro plan for higher limits

---

## 5. Success Metrics

### 5.1 Launch Metrics (Month 1-3)
- **Users**: 100+ active users
- **Jobs**: 1,000+ completed jobs
- **Conversion**: 5% free → paid
- **Uptime**: >90%
- **Churn**: <20%

### 5.2 Growth Metrics (Month 4-6)
- **Users**: 500+ active users
- **Jobs**: 10,000+ completed jobs/month
- **Revenue**: $500+ MRR
- **Conversion**: 10% free → paid
- **Uptime**: >95%

### 5.3 Maturity Metrics (Month 7-12)
- **Users**: 2,000+ active users
- **Jobs**: 50,000+ completed jobs/month
- **Revenue**: $2,000+ MRR
- **Conversion**: 15% free → paid
- **Uptime**: >99%

---

## 6. Pricing & Plans

| Feature | Free | Starter | Pro |
|---------|------|---------|-----|
| **Price** | $0/month | $5/month | $12/month |
| **Daily Tokens** | 20 | 120 | 300 |
| **Priority** | Best-effort | Medium | High |
| **Max Resolution** | 1024x1024 | 1536x1536 | 2048x2048 |
| **Models** | Basic SDXL | All image models | All models + video |
| **Queue** | Slow | Fast | Fastest |
| **API Access** | No | Yes (limited) | Yes (full) |
| **Support** | Community | Email | Priority |

---

## 7. Timeline

### Phase 1: Foundation (Weeks 1-2)
- Database schema
- Scheduler API
- 1 worker container
- Basic bot

### Phase 2: Core Features (Weeks 3-4)
- Full billing system
- Multiple bots
- Queue prioritization
- Website MVP

### Phase 3: Polish (Weeks 5-6)
- Monitoring
- Error handling
- Documentation
- Testing

### Phase 4: Launch (Week 7)
- Soft launch to friends
- Bug fixes
- Public launch

---

## 8. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| GPU failure | High | Low | Backup GPU, quick replacement plan |
| Platform bans | High | Medium | Multiple bots, follow ToS strictly |
| WSL instability | Medium | Medium | Migration plan to bare Linux ready |
| User abuse | Medium | High | Strong rate limiting, monitoring |
| No user growth | High | Medium | Marketing, community building |
| Model updates | Low | High | Abstraction layer for easy swaps |

---

## 9. Open Questions

1. Should we support custom workflows initially? **Decision: No, preset workflows only**
2. How to handle NSFW content? **Decision: Block initially, consider later**
3. Public gallery opt-in or opt-out? **Decision: Opt-in for privacy**
4. Refund policy? **Decision: No refunds, pause instead**
5. Multi-language support? **Decision: English only initially**

---

## 10. Approval

**Product Owner**: Aritra Das (Addy)  
**Technical Lead**: [Engineer Friend Name]  
**Status**: ✅ Approved for Development  
**Date**: December 2025

---

**Next Steps**: Proceed to architecture and technical design documents.