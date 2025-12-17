import asyncpg
import os
import json
from datetime import datetime, date
from typing import Optional, List, Any
from decimal import Decimal

class AsyncDatabase:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.database_url)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def get_or_create_user(self, platform: str, platform_uid: str, ip_address: str = None):
        async with self.pool.acquire() as conn:
            # Try to get user
            row = await conn.fetchrow(
                "SELECT u.*, p.daily_token_limit, p.priority FROM users u JOIN plans p ON u.plan_id = p.id WHERE platform = $1 AND platform_user_id = $2",
                platform, platform_uid
            )
            if row:
                return row
            
            # Create if not exists (default plan_id=1 is Free)
            user_id = await conn.fetchval(
                "INSERT INTO users (platform, platform_user_id, ip_address, plan_id) VALUES ($1, $2, $3, 1) RETURNING id",
                platform, platform_uid, ip_address
            )
            
            # Fetch again to get plan details
            return await conn.fetchrow(
                "SELECT u.*, p.daily_token_limit, p.priority FROM users u JOIN plans p ON u.plan_id = p.id WHERE u.id = $1",
                user_id
            )

    async def get_usage(self, user_id: int, date: date):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM usage_daily WHERE user_id = $1 AND date = $2",
                user_id, date
            )
            if not row:
                # Return a dummy object or create a row. Let's return a simple object wrapper.
                class Usage:
                    tokens_used = 0
                return Usage()
            return row

    async def create_job(self, job_data: dict):
        async with self.pool.acquire() as conn:
            job_id = await conn.fetchval(
                """
                INSERT INTO jobs (
                    user_id, frontend, bot_id, capability, status, priority, 
                    params, cost_tokens, created_at, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                job_data["user_id"], job_data["frontend"], job_data["bot_id"],
                job_data["capability"], job_data["status"], job_data["priority"],
                json.dumps(job_data["params"]), job_data["cost_tokens"], 
                job_data["created_at"], json.dumps(job_data.get("reply_context", {}))
            )
            
            # Return a simple object with id
            class Job:
                def __init__(self, id): self.id = id
            return Job(job_id)

    async def update_job(self, job_id, **kwargs):
        set_clauses = []
        values = []
        for i, (k, v) in enumerate(kwargs.items(), start=2):
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            set_clauses.append(f"{k} = ${i}")
            values.append(v)
        
        query = f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = $1"
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, job_id, *values)

    async def count_queued_jobs_before(self, job_id, priority: int):
        async with self.pool.acquire() as conn:
            # Count jobs with higher priority OR same priority but created earlier
            # Note: This is a simplification.
            return await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs 
                WHERE status = 'QUEUED' 
                AND (priority > $1 OR (priority = $1 AND created_at < (SELECT created_at FROM jobs WHERE id = $2)))
                """,
                priority, job_id
            )

    async def get_next_queued_job(self, priority: int, capability: list):
        async with self.pool.acquire() as conn:
            # Select oldest job with specific priority and capability
            # Capabilities matching is simplified here.
            row = await conn.fetchrow(
                """
                SELECT * FROM jobs 
                WHERE status = 'QUEUED' AND priority = $1 
                ORDER BY created_at ASC 
                LIMIT 1
                """,
                priority
            )
            if row:
                # Parse params from JSON string
                row = dict(row)
                row['params'] = json.loads(row['params'])
                return row
            return None

    async def create_artifact(self, artifact_data: dict):
        async with self.pool.acquire() as conn:
             id = await conn.fetchval(
                """
                INSERT INTO artifacts (job_id, type, local_path, public_url, metadata, format)
                VALUES ($1, $2, $3, $4, $5, 'png') RETURNING id
                """,
                artifact_data["job_id"], artifact_data["type"], artifact_data["path"],
                artifact_data["url"], json.dumps(artifact_data["metadata"])
             )
             class Artifact:
                 def __init__(self, id): self.id = id
             return Artifact(id)

    async def update_usage(self, user_id, date, tokens_used_increment, jobs_completed_increment):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO usage_daily (user_id, date, tokens_used, jobs_completed)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, date) DO UPDATE SET
                    tokens_used = usage_daily.tokens_used + $3,
                    jobs_completed = usage_daily.jobs_completed + $4
                """,
                user_id, date, tokens_used_increment, jobs_completed_increment
            )

    async def get_user(self, user_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    # Missing methods from logic, implementing placeholders
    async def get_job_with_model(self, models, statuses, limit):
        return None # Simplification

    async def find_jobs_with_params(self, batch_key, status, limit):
        return [] # Simplification

