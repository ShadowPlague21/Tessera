-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Plans Table
CREATE TABLE plans (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,
  tier VARCHAR(20) NOT NULL UNIQUE CHECK (tier IN ('free', 'starter', 'pro', 'admin')),
  daily_token_limit INTEGER NOT NULL,
  requests_per_minute INTEGER NOT NULL DEFAULT 5,
  max_concurrent_jobs INTEGER NOT NULL DEFAULT 1,
  priority INTEGER NOT NULL CHECK (priority IN (0, 1, 2, 3)),
  max_resolution INTEGER NOT NULL,
  allowed_models TEXT[] NOT NULL,
  price_cents INTEGER NOT NULL DEFAULT 0,
  billing_period VARCHAR(20) DEFAULT 'monthly',
  description TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_plans_tier ON plans(tier);
CREATE INDEX idx_plans_active ON plans(active) WHERE active = TRUE;

INSERT INTO plans (name, tier, daily_token_limit, priority, max_resolution, allowed_models, price_cents, description) VALUES
  ('Free', 'free', 20, 0, 1024, ARRAY['sdxl'], 0, 'Free tier with basic features'),
  ('Starter', 'starter', 120, 1, 1536, ARRAY['sdxl', 'flux-schnell'], 500, 'Great for casual creators'),
  ('Pro', 'pro', 300, 2, 2048, ARRAY['sdxl', 'flux-schnell', 'flux-dev'], 1200, 'For serious creators'),
  ('Admin', 'admin', 999999, 3, 4096, ARRAY['*'], 0, 'Unlimited access for admins');

-- Users Table
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  platform VARCHAR(20) NOT NULL CHECK (platform IN ('telegram', 'discord', 'web')),
  platform_user_id VARCHAR(100) NOT NULL,
  plan_id INTEGER REFERENCES plans(id) DEFAULT 1,
  email VARCHAR(255),
  display_name VARCHAR(100),
  ip_address INET,
  api_key VARCHAR(64) UNIQUE,
  api_key_created_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(platform, platform_user_id)
);

CREATE INDEX idx_users_platform_uid ON users(platform, platform_user_id);
CREATE INDEX idx_users_api_key ON users(api_key) WHERE api_key IS NOT NULL;
CREATE INDEX idx_users_plan ON users(plan_id);
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;

-- Jobs Table
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  frontend VARCHAR(20) NOT NULL CHECK (frontend IN ('telegram', 'discord', 'web', 'api')),
  bot_id VARCHAR(50),
  capability VARCHAR(20) NOT NULL CHECK (capability IN ('image', 'video', 'text', 'audio')),
  status VARCHAR(20) NOT NULL DEFAULT 'CREATED' 
    CHECK (status IN ('CREATED', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
  priority INTEGER NOT NULL,
  params JSONB NOT NULL,
  workflow_id VARCHAR(100),
  cost_tokens NUMERIC(10,2) NOT NULL,
  worker_id VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  queued_at TIMESTAMP,
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  execution_time_seconds NUMERIC(6,2),
  error JSONB,
  metadata JSONB
);

CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_status_priority ON jobs(status, priority DESC) WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX idx_jobs_worker_id ON jobs(worker_id) WHERE worker_id IS NOT NULL;
CREATE INDEX idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX idx_jobs_active ON jobs(status, priority DESC, created_at)
WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX idx_jobs_params_model ON jobs USING GIN(params) WHERE capability = 'image';

-- Artifacts Table
CREATE TABLE artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  type VARCHAR(20) NOT NULL CHECK (type IN ('image', 'video', 'audio', 'text')),
  format VARCHAR(20) NOT NULL,
  local_path VARCHAR(500),
  public_url VARCHAR(500),
  width INTEGER,
  height INTEGER,
  duration_seconds NUMERIC(6,2),
  file_size_bytes INTEGER,
  metadata JSONB,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_artifacts_job_id ON artifacts(job_id);
CREATE INDEX idx_artifacts_created_at ON artifacts(created_at DESC);
CREATE INDEX idx_artifacts_expires_at ON artifacts(expires_at) WHERE expires_at IS NOT NULL;

-- Usage Daily Table
CREATE TABLE usage_daily (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  tokens_used NUMERIC(10,2) NOT NULL DEFAULT 0,
  jobs_completed INTEGER NOT NULL DEFAULT 0,
  jobs_failed INTEGER NOT NULL DEFAULT 0,
  tokens_image NUMERIC(10,2) DEFAULT 0,
  tokens_video NUMERIC(10,2) DEFAULT 0,
  tokens_text NUMERIC(10,2) DEFAULT 0,
  tokens_audio NUMERIC(10,2) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, date)
);

CREATE INDEX idx_usage_user_date ON usage_daily(user_id, date DESC);
CREATE INDEX idx_usage_date ON usage_daily(date DESC);
CREATE INDEX idx_usage_tokens ON usage_daily(tokens_used DESC);
