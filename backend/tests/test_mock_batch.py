from app.batch import JobState
from app.batch.mock import LOST_JOB_ERROR
from tests.conftest import make_mock


async def test_progress_and_completion(clock):
    mock = make_mock(clock)
    job = await mock.submit("task-1", "echo hi")

    clock.advance(5)
    status = (await mock.status([job]))[job]
    assert status.state == JobState.RUNNING
    assert status.progress == 50.0

    clock.advance(5)
    status = (await mock.status([job]))[job]
    assert status.state == JobState.SUCCEEDED
    assert status.progress == 100.0


async def test_concurrency_limit_queues_extra_jobs(clock):
    mock = make_mock(clock, max_concurrent=2)
    jobs = [await mock.submit(f"t{i}", "x") for i in range(3)]

    clock.advance(1)
    states = {j: s.state for j, s in (await mock.status(jobs)).items()}
    assert [states[j] for j in jobs] == [JobState.RUNNING, JobState.RUNNING, JobState.QUEUED]

    # First two finish at t=10, third starts then and finishes at t=20.
    clock.advance(14)
    s = await mock.status(jobs)
    assert s[jobs[0]].state == JobState.SUCCEEDED
    assert s[jobs[2]].state == JobState.RUNNING
    assert s[jobs[2]].progress == 50.0


async def test_fail_marker_fails_partway(clock):
    mock = make_mock(clock)
    job = await mock.submit("t", "python load.py --fail")
    clock.advance(6)  # failing jobs die at 50% of duration
    status = (await mock.status([job]))[job]
    assert status.state == JobState.FAILED
    assert status.progress == 50.0
    assert status.error


async def test_cancel_frees_slot(clock):
    mock = make_mock(clock, max_concurrent=1)
    a = await mock.submit("a", "x")
    b = await mock.submit("b", "x")
    clock.advance(1)
    await mock.cancel(a)
    clock.advance(1)
    s = await mock.status([a, b])
    assert s[a].state == JobState.CANCELLED
    assert s[b].state == JobState.RUNNING


async def test_unknown_job_reports_lost(clock):
    mock = make_mock(clock)
    s = (await mock.status(["missing"]))["missing"]
    assert s.state == JobState.FAILED
    assert s.error == LOST_JOB_ERROR
