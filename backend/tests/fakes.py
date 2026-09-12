"""A minimal stand-in for the Supabase query builder.

CLAUDE.md section 14: unit tests must not call external APIs. This fake applies
the same filters PostgREST would, over an in-memory list of rows, and supports
insert/update/delete so write-path services can be tested the same way.
"""

from dataclasses import dataclass, field


@dataclass
class _Result:
    data: list[dict]
    count: int | None = None


class FakeQuery:
    def __init__(self, table_rows: list[dict], recorder: list[tuple]):
        # The real list backing the table -- insert/delete mutate this so
        # changes are visible to the next `.table(...)` call in the same test.
        self._table_rows = table_rows
        # A shallow copy for filtering. The dicts inside are the same objects
        # as in _table_rows, so an in-place update() mutates the "stored" row.
        self._rows = list(table_rows)
        self._recorder = recorder
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._pending_update: dict | None = None
        self._pending_insert: dict | list[dict] | None = None
        self._delete = False

    def select(self, *args, **kwargs):
        self._recorder.append(("select", args))
        return self

    def ilike(self, column: str, value: str):
        self._recorder.append(("ilike", column, value))
        needle = value.lower()
        self._rows = [r for r in self._rows if str(r.get(column, "")).lower() == needle]
        return self

    def in_(self, column: str, values):
        self._recorder.append(("in_", column, tuple(values)))
        allowed = set(values)
        self._rows = [r for r in self._rows if r.get(column) in allowed]
        return self

    def gte(self, column: str, value):
        self._recorder.append(("gte", column, value))
        self._rows = [r for r in self._rows if str(r.get(column, "")) >= str(value)]
        return self

    def eq(self, column: str, value):
        self._recorder.append(("eq", column, value))
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def order(self, column: str, desc: bool = False):
        self._recorder.append(("order", column, desc))
        self._order = (column, desc)
        return self

    def limit(self, n: int):
        self._recorder.append(("limit", n))
        self._limit = n
        return self

    def update(self, fields: dict):
        self._recorder.append(("update", fields))
        self._pending_update = fields
        return self

    def insert(self, payload: dict | list[dict]):
        self._recorder.append(("insert", payload))
        self._pending_insert = payload
        return self

    def delete(self):
        self._recorder.append(("delete",))
        self._delete = True
        return self

    def execute(self) -> _Result:
        if self._pending_insert is not None:
            payloads = (
                self._pending_insert
                if isinstance(self._pending_insert, list)
                else [self._pending_insert]
            )
            inserted = [dict(payload) for payload in payloads]
            self._table_rows.extend(inserted)
            return _Result(data=inserted, count=len(inserted))

        if self._pending_update is not None:
            for row in self._rows:
                row.update(self._pending_update)
            return _Result(data=list(self._rows), count=len(self._rows))

        if self._delete:
            removed = list(self._rows)
            for row in removed:
                if row in self._table_rows:
                    self._table_rows.remove(row)
            return _Result(data=removed, count=len(removed))

        rows = self._rows
        if self._order:
            column, desc = self._order
            rows = sorted(rows, key=lambda r: str(r.get(column) or ""), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _Result(data=rows, count=len(self._rows))


@dataclass
class FakeSupabase:
    """`FakeSupabase({"jobs_history": [...]})` behaves like the real client."""

    tables: dict[str, list[dict]] = field(default_factory=dict)
    calls: list[tuple] = field(default_factory=list)

    def table(self, name: str) -> FakeQuery:
        self.calls.append(("table", name))
        return FakeQuery(self.tables.setdefault(name, []), self.calls)


class ExplodingSupabase:
    """A client whose queries always fail, to prove errors are not swallowed."""

    def __init__(self, message: str = "connection reset"):
        self.message = message

    def table(self, name: str):
        raise RuntimeError(self.message)
