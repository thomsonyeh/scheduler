"""Pure DAG helpers. Work on anything with `.name`, `.depends_on`, `.status`."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from graphlib import CycleError, TopologicalSorter
from typing import Protocol

from app.models import TaskStatus


class TaskLike(Protocol):
    name: str
    depends_on: list[str]
    status: TaskStatus


def validate(tasks: Sequence[tuple[str, Sequence[str]]]) -> list[str]:
    """Validate (name, depends_on) pairs. Returns a list of error messages (empty if valid)."""
    errors: list[str] = []
    names = [name for name, _ in tasks]

    dupes = sorted(n for n, count in Counter(names).items() if count > 1)
    if dupes:
        errors.append(f"duplicate task names: {', '.join(dupes)}")

    known = set(names)
    for name, deps in tasks:
        if name in deps:
            errors.append(f"task '{name}' depends on itself")
        missing = sorted(set(deps) - known)
        if missing:
            errors.append(f"task '{name}' depends on unknown task(s): {', '.join(missing)}")
        dup_deps = sorted(d for d, count in Counter(deps).items() if count > 1)
        if dup_deps:
            errors.append(f"task '{name}' lists duplicate dependencies: {', '.join(dup_deps)}")

    if errors:
        return errors

    try:
        TopologicalSorter({name: deps for name, deps in tasks}).prepare()
    except CycleError as exc:
        cycle = exc.args[1]
        errors.append(f"dependency cycle: {' -> '.join(cycle)}")
    return errors


def ready_tasks[T: TaskLike](tasks: Iterable[T]) -> list[T]:
    """PENDING tasks whose dependencies have all SUCCEEDED."""
    tasks = list(tasks)
    status = {t.name: t.status for t in tasks}
    return [
        t
        for t in tasks
        if t.status == TaskStatus.PENDING
        and all(status[d] == TaskStatus.SUCCEEDED for d in t.depends_on)
    ]


def downstream_of(name: str, tasks: Iterable[TaskLike]) -> set[str]:
    """Names of all tasks that transitively depend on `name`."""
    children: dict[str, list[str]] = defaultdict(list)
    for t in tasks:
        for dep in t.depends_on:
            children[dep].append(t.name)

    result: set[str] = set()
    stack = list(children[name])
    while stack:
        n = stack.pop()
        if n not in result:
            result.add(n)
            stack.extend(children[n])
    return result
