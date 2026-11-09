from app.models import TaskStatus, Workflow, WorkflowStatus


def load(session_factory, wf_id) -> Workflow:
    with session_factory() as s:
        wf = s.get(Workflow, wf_id)
        _ = wf.tasks
        return wf


def statuses(wf: Workflow) -> dict[str, TaskStatus]:
    return {t.name: t.status for t in wf.tasks}


async def run_until_done(orch, clock, session_factory, wf_id, step=1.0, max_ticks=500):
    for _ in range(max_ticks):
        await orch.tick()
        wf = load(session_factory, wf_id)
        if wf.status not in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING):
            return wf
        clock.advance(step)
    raise AssertionError("workflow did not finish")


async def test_linear_chain_runs_in_order(
    make_orchestrator, create_workflow, session_factory, clock
):
    orch = make_orchestrator()
    wf_id = create_workflow({"a": [], "b": ["a"], "c": ["b"]})

    await orch.tick()
    assert statuses(load(session_factory, wf_id)) == {
        "a": TaskStatus.SUBMITTED,
        "b": TaskStatus.PENDING,
        "c": TaskStatus.PENDING,
    }
    assert load(session_factory, wf_id).status == WorkflowStatus.RUNNING

    wf = await run_until_done(orch, clock, session_factory, wf_id)
    assert wf.status == WorkflowStatus.SUCCEEDED
    tasks = {t.name: t for t in wf.tasks}
    assert all(t.progress == 100.0 for t in tasks.values())
    assert tasks["a"].finished_at <= tasks["b"].submitted_at
    assert tasks["b"].finished_at <= tasks["c"].submitted_at


async def test_diamond_runs_branches_in_parallel(
    make_orchestrator, create_workflow, session_factory, clock
):
    orch = make_orchestrator()
    wf_id = create_workflow({"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]})

    await orch.tick()
    clock.advance(10)
    await orch.tick()  # a succeeds, b and c submitted together
    s = statuses(load(session_factory, wf_id))
    assert s["a"] == TaskStatus.SUCCEEDED
    assert s["b"] == s["c"] == TaskStatus.SUBMITTED
    assert s["d"] == TaskStatus.PENDING

    clock.advance(1)
    await orch.tick()
    s = statuses(load(session_factory, wf_id))
    assert s["b"] == s["c"] == TaskStatus.RUNNING

    wf = await run_until_done(orch, clock, session_factory, wf_id)
    assert wf.status == WorkflowStatus.SUCCEEDED


async def test_failure_skips_downstream_but_independent_branch_finishes(
    make_orchestrator, create_workflow, session_factory, clock
):
    orch = make_orchestrator()
    wf_id = create_workflow(
        {"a": [], "bad": ["a"], "after_bad": ["bad"], "leaf": ["after_bad"], "ok": ["a"]},
        commands={"bad": "run --fail"},
    )
    wf = await run_until_done(orch, clock, session_factory, wf_id)

    assert wf.status == WorkflowStatus.FAILED
    s = statuses(wf)
    assert s["bad"] == TaskStatus.FAILED
    assert s["after_bad"] == s["leaf"] == TaskStatus.SKIPPED
    assert s["ok"] == TaskStatus.SUCCEEDED
    bad = next(t for t in wf.tasks if t.name == "bad")
    assert bad.error and 0 < bad.progress < 100


async def test_cancel_stops_in_flight_and_pending(
    make_orchestrator, create_workflow, session_factory, clock
):
    orch = make_orchestrator()
    wf_id = create_workflow({"a": [], "b": ["a"]})
    await orch.tick()
    clock.advance(3)
    await orch.tick()

    await orch.cancel(wf_id)
    wf = load(session_factory, wf_id)
    assert wf.status == WorkflowStatus.CANCELLED
    assert statuses(wf) == {"a": TaskStatus.CANCELLED, "b": TaskStatus.CANCELLED}

    # Further ticks don't resurrect it.
    clock.advance(20)
    await orch.tick()
    assert load(session_factory, wf_id).status == WorkflowStatus.CANCELLED


async def test_restart_with_fresh_mock_marks_jobs_lost(
    make_orchestrator, create_workflow, session_factory, clock
):
    wf_id = create_workflow({"a": [], "b": ["a"]})
    await make_orchestrator().tick()

    # New orchestrator + new in-memory mock, same DB: simulates a backend restart.
    wf = await run_until_done(make_orchestrator(), clock, session_factory, wf_id)
    s = statuses(wf)
    assert s == {"a": TaskStatus.FAILED, "b": TaskStatus.SKIPPED}
    assert "job lost" in next(t for t in wf.tasks if t.name == "a").error
