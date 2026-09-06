"""Job registry: stage progression, error sanitisation, eviction, concurrency limit."""
import asyncio
import gc
import time

import pytest

from app.services.jobs import Busy, JobRegistry


@pytest.mark.asyncio
async def test_stage_progression():
    reg = JobRegistry(max_jobs=2, ttl_seconds=600)

    def fn(set_stage):
        set_stage("load")
        time.sleep(0.01)
        set_stage("render")

    job = await reg.start(fn)
    for _ in range(50):
        current = reg.get(job.id)
        if current.state == "done":
            break
        await asyncio.sleep(0.01)
    assert current.state == "done"
    assert current.stage == "render"


@pytest.mark.asyncio
async def test_error_state_sanitised():
    reg = JobRegistry(max_jobs=2, ttl_seconds=600)

    def fn(set_stage):
        raise RuntimeError("leaked traceback with secret path /etc/whatever")

    job = await reg.start(fn)
    for _ in range(50):
        current = reg.get(job.id)
        if current.state == "error":
            break
        await asyncio.sleep(0.01)
    assert current.state == "error"
    assert current.message == "reconstruction failed"
    assert "secret" not in current.message


@pytest.mark.asyncio
async def test_busy_limit():
    reg = JobRegistry(max_jobs=1, ttl_seconds=600)

    def fn(set_stage):
        time.sleep(0.2)

    await reg.start(fn)
    with pytest.raises(Busy):
        await reg.start(fn)


@pytest.mark.asyncio
async def test_eviction():
    reg = JobRegistry(max_jobs=2, ttl_seconds=600)

    def fn(set_stage):
        pass

    job = await reg.start(fn)
    for _ in range(50):
        if reg._jobs[job.id].state == "done":
            break
        await asyncio.sleep(0.01)

    reg._ttl_seconds = 0
    await asyncio.sleep(0.02)
    assert reg.get(job.id) is None


@pytest.mark.asyncio
async def test_task_survives_gc_and_completes():
    reg = JobRegistry(max_jobs=2, ttl_seconds=600)

    def fn(set_stage):
        time.sleep(0.01)

    job = await reg.start(fn)
    gc.collect()
    for _ in range(50):
        if reg.get(job.id).state == "done":
            break
        await asyncio.sleep(0.01)
    assert reg.get(job.id).state == "done"
