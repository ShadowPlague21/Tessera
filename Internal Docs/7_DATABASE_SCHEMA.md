# Tessera - PostgreSQL Database Schema (Production-Ready)

**Version**: 1.0  
**Database**: PostgreSQL 15+  
**Last Updated**: December 2025

---

## Table of Contents

1. [Create Database](#create-database)
2. [Plans Table](#plans-table)
3. [Users Table](#users-table)
4. [Jobs Table](#jobs-table)
5. [Artifacts Table](#artifacts-table)
6. [Usage Daily Table](#usage-daily-table)
7. [Sample Data](#sample-data)
8. [Common Queries](#common-queries)

---

## Create Database

```sql
-- Create database
CREATE DATABASE tessera
  WITH ENCODING 'UTF8'
  LC_COLLATE = 'en_US.UTF-8'
  LC_CTYPE = 'en_US.UTF-8';

-- Connect to database
\c tessera

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

---

## Plans Table

```sql
CREATE TABLE plans (
  id SERIAL PRIMARY KEY,
  
  -- Plan details
  name VARCHAR(50) NOT NULL UNIQUE,
  tier VARCHAR(20) NOT NULL UNIQUE CHECK (tier IN ('free', 'starter', 'pro', 'admin')),
  
  -- Limits
  daily_token_limit INTEGER NOT NULL,
  requests_per_minute INTEGER NOT NULL DEFAULT 5,
  max_concurrent_jobs INTEGER NOT NULL DEFAULT 1,
  
  -- Features
  priority INTEGER NOT NULL CHECK (priority IN (0, 1, 2, 3)),
  max_resolution INTEGER NOT NULL,
  allowed_models TEXT[] NOT NULL,
  
  -- Pricing
  price_cents INTEGER NOT NULL DEFAULT 0,
  billing_period VARCHAR(20) DEFAULT 'monthly',
  
  -- Metadata
  description TEXT,
  
  -- Status
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_plans_tier ON plans(tier);
CREATE INDEX idx_plans_active ON plans(active) WHERE active = TRUE;

-- Insert sample plans
INSERT INTO plans (name, tier, daily_token_limit, priority, max_resolution, allowed_models, price_cents, description) VALUES
  ('Free', 'free', 20, 0, 1024, ARRAY['sdxl'], 0, 'Free tier with basic features'),
  ('Starter', 'starter', 120, 1, 1536, ARRAY['sdxl', 'flux-schnell'], 500, 'Great for casual creators'),
  ('Pro', 'pro', 300, 2, 2048, ARRAY['sdxl', 'flux-schnell', 'flux-dev'], 1200, 'For serious creators'),
  ('Admin', 'admin', 999999, 3, 4096, ARRAY['*'], 0, 'Unlimited access for admins');
```

---

## Users Table

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  
  -- Platform identification
  platform VARCHAR(20) NOT NULL CHECK (platform IN ('telegram', 'discord', 'web')),
  platform_user_id VARCHAR(100) NOT NULL,
  
  -- Plan relationship
  plan_id INTEGER REFERENCES plans(id) DEFAULT 1,
  
  -- Metadata
  email VARCHAR(255),
  display_name VARCHAR(100),
  ip_address INET,
  
  -- API access
  api_key VARCHAR(64) UNIQUE,
  api_key_created_at TIMESTAMP,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  UNIQUE(platform, platform_user_id)
);

-- Indexes
CREATE INDEX idx_users_platform_uid ON users(platform, platform_user_id);
CREATE INDEX idx_users_api_key ON users(api_key) WHERE api_key IS NOT NULL;
CREATE INDEX idx_users_plan ON users(plan_id);
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
```

---

## Jobs Table

```sql
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- User relationship
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Request metadata
  frontend VARCHAR(20) NOT NULL CHECK (frontend IN ('telegram', 'discord', 'web', 'api')),
  bot_id VARCHAR(50),
  capability VARCHAR(20) NOT NULL CHECK (capability IN ('image', 'video', 'text', 'audio')),
  
  -- Job state
  status VARCHAR(20) NOT NULL DEFAULT 'CREATED' 
    CHECK (status IN ('CREATED', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
  priority INTEGER NOT NULL,
  
  -- Job details
  params JSONB NOT NULL,
  workflow_id VARCHAR(100),
  
  -- Billing
  cost_tokens NUMERIC(10,2) NOT NULL,
  
  -- Execution tracking
  worker_id VARCHAR(50),
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  queued_at TIMESTAMP,
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  
  -- Results
  execution_time_seconds NUMERIC(6,2),
  error JSONB,
  metadata JSONB
);

-- Indexes (CRITICAL for performance)
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_status_priority ON jobs(status, priority DESC) WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX idx_jobs_worker_id ON jobs(worker_id) WHERE worker_id IS NOT NULL;
CREATE INDEX idx_jobs_user_status ON jobs(user_id, status);
-- Partial index for active jobs (most frequently queried)
CREATE INDEX idx_jobs_active ON jobs(status, priority DESC, created_at)
WHERE status IN ('QUEUED', 'RUNNING');
-- JSONB indexes for query optimization
CREATE INDEX idx_jobs_params_model ON jobs USING GIN(params) WHERE capability = 'image';
```

---

## Artifacts Table

```sql
CREATE TABLE artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Job relationship
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  
  -- Artifact details
  type VARCHAR(20) NOT NULL CHECK (type IN ('image', 'video', 'audio', 'text')),
  format VARCHAR(20) NOT NULL,
  
  -- Storage
  local_path VARCHAR(500),
  public_url VARCHAR(500),
  
  -- Metadata
  width INTEGER,
  height INTEGER,
  duration_seconds NUMERIC(6,2),
  file_size_bytes INTEGER,
  metadata JSONB,
  
  -- Access control
  expires_at TIMESTAMP,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_artifacts_job_id ON artifacts(job_id);
CREATE INDEX idx_artifacts_created_at ON artifacts(created_at DESC);
CREATE INDEX idx_artifacts_expires_at ON artifacts(expires_at) WHERE expires_at IS NOT NULL;
```

---

## Usage Daily Table

```sql
CREATE TABLE usage_daily (
  id SERIAL PRIMARY KEY,
  
  -- User relationship
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Date tracking
  date DATE NOT NULL,
  
  -- Usage metrics
  tokens_used NUMERIC(10,2) NOT NULL DEFAULT 0,
  jobs_completed INTEGER NOT NULL DEFAULT 0,
  jobs_failed INTEGER NOT NULL DEFAULT 0,
  
  -- Breakdown by capability
  tokens_image NUMERIC(10,2) DEFAULT 0,
  tokens_video NUMERIC(10,2) DEFAULT 0,
  tokens_text NUMERIC(10,2) DEFAULT 0,
  tokens_audio NUMERIC(10,2) DEFAULT 0,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Constraints
  UNIQUE(user_id, date)
);

-- Indexes
CREATE INDEX idx_usage_user_date ON usage_daily(user_id, date DESC);
CREATE INDEX idx_usage_date ON usage_daily(date DESC);
CREATE INDEX idx_usage_tokens ON usage_daily(tokens_used DESC);
```

---

## Sample Data

```sql
-- Plan data (already inserted above)

-- Sample users
INSERT INTO users (platform, platform_user_id, plan_id, display_name, email) VALUES
  ('telegram', '123456789', 1, 'John Doe', 'john@example.com'),
  ('discord', '987654321', 2, 'Jane Smith', 'jane@example.com'),
  ('web', 'google-oauth-abc123', 3, 'Pro User', 'pro@example.com');

-- Sample jobs
INSERT INTO jobs (user_id, frontend, bot_id, capability, status, priority, params, cost_tokens) VALUES
  (1, 'telegram', 'tg-img-1', 'image', 'COMPLETED', 0, 
   '{"prompt": "a sunset", "resolution": "1024x1024", "steps": 20}', 1.0),
  (2, 'discord', 'dc-img-1', 'image', 'QUEUED', 1, 
   '{"prompt": "a mountain", "resolution": "1024x1024"}', 1.0);

-- Sample usage
INSERT INTO usage_daily (user_id, date, tokens_used, jobs_completed, tokens_image) VALUES
  (1, CURRENT_DATE, 5.0, 5, 5.0),
  (2, CURRENT_DATE, 2.0, 2, 2.0);
```

---

## Common Queries

### Get User's Daily Usage

```sql
SELECT 
  u.display_name,
  p.name as plan,
  ud.tokens_used,
  p.daily_token_limit,
  (p.daily_token_limit - ud.tokens_used) as remaining,
  ud.jobs_completed
FROM users u
JOIN plans p ON u.plan_id = p.id
LEFT JOIN usage_daily ud ON u.id = ud.user_id AND ud.date = CURRENT_DATE
WHERE u.id = $1;
```

### Get Queued Jobs (High Priority First)

```sql
SELECT 
  id, user_id, capability, priority,
  EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at)) as wait_seconds
FROM jobs
WHERE status = 'QUEUED'
ORDER BY priority DESC, created_at ASC
LIMIT 10;
```

### Calculate Total Revenue

```sql
SELECT 
  DATE(u.created_at) as signup_date,
  COUNT(DISTINCT u.id) as new_users,
  SUM(p.price_cents) / 100.0 as revenue_dollars
FROM users u
JOIN plans p ON u.plan_id = p.id
WHERE p.price_cents > 0
GROUP BY DATE(u.created_at)
ORDER BY signup_date DESC;
```

### Find Failed Jobs for Analysis

```sql
SELECT 
  id, user_id, capability, error,
  EXTRACT(EPOCH FROM (ended_at - started_at)) as duration_seconds
FROM jobs
WHERE status = 'FAILED'
AND created_at > CURRENT_DATE - INTERVAL '7 days'
ORDER BY created_at DESC;
```

### Monitor Job Performance

```sql
SELECT 
  capability,
  COUNT(*) as total_jobs,
  COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
  COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'COMPLETED') / COUNT(*), 2) as success_rate,
  ROUND(AVG(EXTRACT(EPOCH FROM (ended_at - started_at))), 2) as avg_duration_seconds
FROM jobs
WHERE started_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY capability;
```

### Get Top Users by Tokens Used

```sql
SELECT 
  u.id, u.display_name, u.email,
  p.name as plan,
  SUM(ud.tokens_used) as total_tokens,
  COUNT(DISTINCT ud.date) as days_active
FROM users u
JOIN plans p ON u.plan_id = p.id
JOIN usage_daily ud ON u.id = ud.user_id
WHERE ud.date > CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.id, u.display_name, u.email, p.name
ORDER BY total_tokens DESC
LIMIT 20;
```

### Monitor Worker Activity

```sql
SELECT 
  worker_id,
  COUNT(*) as jobs_processed,
  COUNT(*) FILTER (WHERE status = 'COMPLETED') as successful,
  COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
  ROUND(AVG(EXTRACT(EPOCH FROM (ended_at - started_at))), 2) as avg_time_seconds
FROM jobs
WHERE worker_id IS NOT NULL
AND started_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY worker_id;
```

### Get Artifacts Expiring Soon

```sql
SELECT 
  id, job_id, type, format,
  expires_at,
  EXTRACT(EPOCH FROM (expires_at - CURRENT_TIMESTAMP)) / 3600.0 as hours_until_expiry
FROM artifacts
WHERE expires_at IS NOT NULL
AND expires_at < CURRENT_TIMESTAMP + INTERVAL '24 hours'
AND expires_at > CURRENT_TIMESTAMP
ORDER BY expires_at ASC;
```

---

## Maintenance Scripts

### Backup Database

```bash
#!/bin/bash
BACKUP_DIR="/backups/tessera"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

pg_dump -U tessera_user -h localhost tessera | gzip > $BACKUP_DIR/tessera_$DATE.sql.gz

echo "Backup created: $BACKUP_DIR/tessera_$DATE.sql.gz"
```

### Vacuum & Analyze

```sql
-- Run weekly for maintenance
VACUUM ANALYZE jobs;
VACUUM ANALYZE usage_daily;
VACUUM ANALYZE artifacts;

-- Reindex active jobs index
REINDEX INDEX idx_jobs_active;
```

### Archive Old Data

```sql
-- Archive jobs older than 90 days (optional)
-- First create an archive table if needed
-- Then: DELETE FROM jobs WHERE created_at < CURRENT_DATE - INTERVAL '90 days'
```

---

## Performance Tuning

### Connection Pool Settings

```python
# In your scheduler app
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,              # Base connections
    max_overflow=40,           # Additional connections
    pool_pre_ping=True,        # Check connection health
    echo=False
)
```

### Query Optimization Tips

1. **Always filter by status first** (most selective index)
2. **Use created_at for range queries** (indexed DESC)
3. **Batch updates when possible**
4. **Use JSONB indexing for complex params**
5. **Archive old data monthly**

---

## Initialization Script

```python
# scripts/init_db.py
import asyncio
import asyncpg
import os
from pathlib import Path

async def init_database():
    """Initialize database with schema and sample data."""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password=os.getenv('DB_ADMIN_PASSWORD'),
    )
    
    # Read and execute SQL files in order
    sql_files = [
        'migrations/01_create_database.sql',
        'migrations/02_create_tables.sql',
        'migrations/03_create_indexes.sql',
        'migrations/04_sample_data.sql',
    ]
    
    for sql_file in sql_files:
        path = Path(__file__).parent / '..' / sql_file
        print(f"Running {sql_file}...")
        with open(path) as f:
            await conn.execute(f.read())
    
    await conn.close()
    print("✅ Database initialized")

if __name__ == '__main__':
    asyncio.run(init_database())
```

---

**End of Database Schema**

All SQL is production-ready. Copy these table definitions and you're ready to build!