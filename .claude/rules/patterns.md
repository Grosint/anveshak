---
paths:
  - "**/*.py"
---
# Python Patterns

## ARQ Job Pattern (mandatory for all LLM calls)
```python
async def enqueue_report_job(topic_id: str, redis: Redis) -> str:
    job = await arq.create_pool(redis_settings).enqueue_job(
        "generate_report", topic_id
    )
    return job.job_id
```

## Content Deduplication Pattern (mandatory)
```python
# Always use ON CONFLICT(content_hash) DO NOTHING
await conn.execute(
    "INSERT INTO content_items (...) VALUES (...) ON CONFLICT(content_hash) DO NOTHING"
)
```

## Hardware Config Pattern (mandatory for all ML)
```python
# In settings.py — never in service code
class VisionSettings(BaseSettings):
    yolo_model_size: str = "nano"  # nano → xlarge on GPU upgrade
    vision_device: str = "cpu"     # cpu → cuda on GPU upgrade
```

## Report Immutability Pattern (mandatory)
```python
# generated_at is set ONCE. Never in an UPDATE.
# Always check before generating:
existing = await conn.fetchrow(
    "SELECT id FROM reports WHERE topic_id=$1 AND report_type=$2 "
    "AND generated_at > NOW() - INTERVAL '24 hours'",
    topic_id, report_type
)
if existing:
    return existing["id"]  # return cached, never regenerate within 24h
```
