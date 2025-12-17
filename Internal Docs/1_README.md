# Tessera - Multi-Modal AI Inference Platform

**Tessera** is a production-ready, scalable AI inference platform serving image generation, video creation, text generation, and audio synthesis through multiple frontends (Telegram bots, Discord bots, and web interface).

## 🎯 Vision

Build a freemium AI inference service that efficiently manages GPU resources while serving users through multiple rate-limited bot frontends, with proper billing, job queueing, and horizontal scalability.

## 🏗️ Architecture

Tessera uses a clean **3-layer architecture**:

```
┌─────────────────────────────────────────┐
│ Layer 1: Frontends (Stateless)         │
│  -  3x Telegram bots (image)             │
│  -  3x Telegram bots (video)             │
│  -  3x Discord bots (image)              │
│  -  3x Discord bots (video)              │
│  -  Website                              │
└─────────────┬───────────────────────────┘
              │ HTTP/JSON API
              ▼
┌─────────────────────────────────────────┐
│ Layer 2: Control Plane (Authority)     │
│  -  FastAPI Scheduler                    │
│  -  PostgreSQL Database                  │
│  -  Job Queue & Priority System          │
│  -  Billing & Quota Enforcement          │
│  -  Worker Selection & Coordination      │
└─────────────┬───────────────────────────┘
              │ Internal API
              ▼
┌─────────────────────────────────────────┐
│ Layer 3: Workers (Execution)           │
│  -  ComfyUI (Image/Video)                │
│  -  KoboldCPP (Text/LLM)                 │
│  -  Whisper (STT)                        │
│  -  AudioGen (TTS/Audio)                 │
│  (Podman containers on WSL)             │
└─────────────────────────────────────────┘
```

## 🚀 Key Features

- **Multi-Frontend Architecture**: Scale frontends independently to handle platform rate limits
- **Token-Based Billing**: Fair pricing based on outputs (1 token = 1 image @1024x1024)
- **Smart Job Scheduling**: Priority queues, model affinity optimization, optional batching
- **Single GPU Optimized**: Efficient model switching and serialized execution
- **Production-Ready**: Proper error handling, monitoring, health checks, and restart logic
- **Future-Proof**: Designed to scale horizontally (add GPUs/machines without redesign)

## 💎 Core Principles

1. **Frontends are stateless and replaceable**
2. **Control Plane is the single source of truth**
3. **Workers are dumb executors**
4. **Database represents authority, not convenience**
5. **Scalability through horizontal sharding, not architectural changes**

## 📊 Business Model

- **Freemium Tier**: 20 tokens/day, best-effort queue
- **Starter Plan**: $5/month, 120 tokens/day, priority queue
- **Pro Plan**: $12/month, 300 tokens/day, highest priority

## 🛠️ Tech Stack

**Frontend Layer:**
- Python 3.11+
- python-telegram-bot
- discord.py
- Next.js (website)

**Control Plane:**
- FastAPI
- PostgreSQL 15+
- Redis (optional, for rate limiting)
- Pydantic (validation)

**Worker Layer:**
- Podman containers (WSL)
- ComfyUI (headless)
- KoboldCPP
- Whisper / AudioGen
- NVIDIA CUDA 11.8+

**Infrastructure:**
- WSL2 (initial deployment)
- systemd (process supervision)
- nginx (reverse proxy)
- Prometheus + Grafana (monitoring)

## 📁 Project Structure

```
tessera/
├── docs/                      # Documentation
├── frontend/
│   ├── telegram-bots/         # 6 bot instances
│   ├── discord-bots/          # 6 bot instances
│   └── website/               # Next.js web app
├── control-plane/
│   ├── scheduler/             # FastAPI app
│   ├── models/                # DB models
│   ├── api/                   # API endpoints
│   └── billing/               # Quota/billing logic
├── workers/
│   ├── comfyui-worker/        # Image/video worker
│   ├── koboldcpp-worker/      # LLM worker
│   ├── whisper-worker/        # STT worker
│   ├── audio-worker/          # TTS/audio worker
│   └── common/                # Shared worker code
├── infrastructure/
│   ├── podman/                # Container configs
│   ├── postgres/              # DB migrations
│   ├── nginx/                 # Reverse proxy config
│   └── monitoring/            # Prometheus/Grafana
└── scripts/
    ├── setup/                 # Installation scripts
    └── deployment/            # Deployment automation
```

## 🏃 Quick Start

### Prerequisites

- PC1 (Worker): Windows 11 + WSL2, RTX 5060 Ti 16GB, 64GB RAM
- PC2 (Control): Linux/Windows, 16GB+ RAM
- Python 3.11+
- PostgreSQL 15+
- Podman (in WSL)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/tessera
cd tessera

# Set up Control Plane (PC2)
cd control-plane
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Edit .env with your settings

# Initialize database
python scripts/init_db.py

# Start scheduler
uvicorn scheduler.main:app --host 0.0.0.0 --port 8000

# Set up Workers (PC1 WSL)
cd workers
./scripts/setup_wsl_production.sh
./scripts/start_workers.sh

# Set up Bots (PC2)
cd frontend/telegram-bots

# Configure bot tokens in .env files
./start_all_bots.sh
```

## 📖 Documentation

- [Product Requirements Document (PRD)](./PRD.md)
- [Architecture Details](./ARCHITECTURE.md)
- [API Specification](./API_SPEC.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [Component Logic](./COMPONENT_LOGIC.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Flow Diagrams](./FLOW_DIAGRAMS.md)
- [Security Guidelines](./SECURITY.md)
- [Development Guide](./DEVELOPMENT_GUIDE.md)
- [Operations Manual](./OPERATIONS.md)
- [Disaster Recovery](./DISASTER_RECOVERY.md)

## 🤝 Contributing

1. Read the [Development Guide](./DEVELOPMENT_GUIDE.md)
2. Check component documentation
3. Follow the established architecture patterns
4. Write tests for new features
5. Update documentation

## 📝 License

MIT License - Redpill Labs

## 👥 Team

Built by Aritra Das (Addy/ShadowPlague21) and the Redpill Labs team.

---

**Status**: In active development  
**Version**: 0.1.0-alpha  
**Last Updated**: December 2025