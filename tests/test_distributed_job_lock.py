from types import SimpleNamespace

from distributed_job_lock import run_with_advisory_lock


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class FakeTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, acquired=True, raises=False):
        self.acquired = acquired
        self.raises = raises
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return FakeTransaction()

    def execute(self, statement, parameters):
        self.statements.append((str(statement), parameters))
        if self.raises:
            raise OSError("database details")
        return FakeResult(self.acquired)


class FakeEngine:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return self.connection


def test_job_runs_when_advisory_lock_is_acquired():
    connection = FakeConnection(acquired=True)
    calls = []
    ran = run_with_advisory_lock(lambda: calls.append("run"), lock_id=73, engine=FakeEngine(connection))

    assert ran is True
    assert calls == ["run"]
    assert "pg_try_advisory_xact_lock" in connection.statements[0][0]
    assert connection.statements[0][1] == {"lock_id": 73}


def test_job_is_skipped_when_another_replica_owns_the_lock():
    connection = FakeConnection(acquired=False)
    calls = []
    ran = run_with_advisory_lock(lambda: calls.append("run"), lock_id=73, engine=FakeEngine(connection))

    assert ran is False
    assert calls == []


def test_job_fails_closed_when_the_lock_query_fails():
    connection = FakeConnection(raises=True)
    calls = []
    ran = run_with_advisory_lock(lambda: calls.append("run"), lock_id=73, engine=FakeEngine(connection))

    assert ran is False
    assert calls == []


def test_non_postgres_local_test_database_runs_job_without_advisory_lock():
    engine = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    calls = []
    ran = run_with_advisory_lock(lambda: calls.append("run"), lock_id=73, engine=engine)

    assert ran is True
    assert calls == ["run"]
