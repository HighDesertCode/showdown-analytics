# The public API's image. Build it from the repo root: docker build -f api/Dockerfile .
# api/Dockerfile.dockerignore, not the root .dockerignore (the pipelines image's), lists what the build can see.

# Stage 1: provides only the uv binary, pinned to the version used locally.
FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

# Stage 2: installs the locked dependencies and the api group, without dev tools, into a virtual environment. The
# project itself is installed too, because the API reads its version from the package metadata; hatch builds that
# package from pipelines/, so the image carries the pipelines code, unused. uv and its cache stay in this stage.
FROM python:3.13-slim AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --group api --no-install-project
COPY pipelines pipelines
RUN uv sync --locked --no-dev --group api --no-editable

# Stage 3: the image that runs: the virtual environment and the api package, as an unprivileged user.
FROM python:3.13-slim
# Remove pip, which the API never uses, and drop setuid bits, so programs like su and mount can't be used to gain
# privileges.
RUN python -m pip uninstall --yes pip \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} + \
    && useradd --create-home --uid 10001 api
WORKDIR /app
COPY --from=build /app/.venv .venv
COPY api api
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER api
EXPOSE 8080
# Uvicorn imports api.main from /app, the working directory.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
