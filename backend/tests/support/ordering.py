"""Deterministic "write order" for test assertions over rows written by separate transactions.

``created_at``/``at`` default to the database ``now()``; the test PostgreSQL runs in a VM whose clock can step
backwards (~1 s), so ordering rows of *different* transactions by those columns is not reliable. ``xmin`` is
the id of the inserting transaction — the tests run their transactions one after another, so it gives the
real write order. Use it only for append-only tables (an UPDATE gives the row a new ``xmin``).
"""

TXN_ORDER = "xmin::text::bigint"
