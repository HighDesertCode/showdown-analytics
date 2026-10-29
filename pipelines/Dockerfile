# Stage 1: provides only the uv binary, pinned to the version used locally.
FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

# Stage 2: installs the locked dependencies (plus dbt, without dev tools) and the pipelines package into a
# virtual environment. uv, its download cache, and the source files stay behind in this stage.
FROM python:3.13-slim AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --group dbt --no-install-project
COPY pipelines pipelines
RUN uv sync --locked --no-dev --group dbt --no-editable

# Stage 3: the image that runs: the virtual environment and the dbt project, as an unprivileged user.
FROM python:3.13-slim
RUN useradd --create-home --uid 10001 pipelines
WORKDIR /app
COPY --from=build /app/.venv .venv
COPY transform transform
# dbt writes its artifacts and logs to /tmp, since the user can't write to /app, and sends no usage stats.
ENV PATH=/app/.venv/bin:$PATH \
    DBT_TARGET_PATH=/tmp/dbt/target \
    DBT_LOG_PATH=/tmp/dbt/logs \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false
USER pipelines
CMD ["pipelines", "--help"]
