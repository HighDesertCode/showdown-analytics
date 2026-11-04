"""Fixtures for the pipelines' database tests; tests/conftest.py builds the database they run against."""

import psycopg
import pytest


@pytest.fixture
def conn(database_url: str, schemas: None):
    """A connection as showdown-analyst, the pipelines' role, whose changes are rolled back after each test."""
    with psycopg.connect(database_url) as connection:
        connection.execute('SET ROLE "showdown-analyst"')
        yield connection
        connection.rollback()
