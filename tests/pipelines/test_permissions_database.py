"""Checks database-level privileges from sql/permissions/ (see tests/pipelines/conftest.py)."""

import pytest


@pytest.mark.parametrize(
    ("role", "privilege", "expected"),
    [
        ("public", "CONNECT", False),
        ("public", "TEMPORARY", False),
        ("showdown-analyst", "CONNECT", True),
        ("showdown-analyst", "TEMPORARY", False),
        ("showdown-transform", "CONNECT", True),
        ("showdown-transform", "TEMPORARY", True),
    ],
)
def test_only_project_roles_can_use_the_database(conn, role, privilege, expected):
    row = conn.execute("SELECT HAS_DATABASE_PRIVILEGE(%s, CURRENT_DATABASE(), %s)", (role, privilege)).fetchone()

    assert row == (expected,)
