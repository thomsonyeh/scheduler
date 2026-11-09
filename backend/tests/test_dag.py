from dataclasses import dataclass, field

from app import dag
from app.models import TaskStatus


@dataclass
class T:
    name: str
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING


def test_valid_diamond():
    assert dag.validate([("a", []), ("b", ["a"]), ("c", ["a"]), ("d", ["b", "c"])]) == []


def test_duplicate_names():
    errors = dag.validate([("a", []), ("a", [])])
    assert errors == ["duplicate task names: a"]


def test_unknown_dependency():
    errors = dag.validate([("a", ["nope"])])
    assert errors == ["task 'a' depends on unknown task(s): nope"]


def test_self_dependency():
    assert "task 'a' depends on itself" in dag.validate([("a", ["a"])])


def test_cycle():
    errors = dag.validate([("a", ["c"]), ("b", ["a"]), ("c", ["b"])])
    assert len(errors) == 1
    assert errors[0].startswith("dependency cycle:")


def test_ready_tasks_waits_for_all_deps():
    tasks = [
        T("a", status=TaskStatus.SUCCEEDED),
        T("b", status=TaskStatus.RUNNING),
        T("c", ["a"]),
        T("d", ["a", "b"]),
    ]
    assert [t.name for t in dag.ready_tasks(tasks)] == ["c"]


def test_downstream_is_transitive():
    tasks = [T("a"), T("b", ["a"]), T("c", ["b"]), T("x")]
    assert dag.downstream_of("a", tasks) == {"b", "c"}
    assert dag.downstream_of("x", tasks) == set()
