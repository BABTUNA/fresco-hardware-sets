# the viewer with the sample books baked in and every book pre-extracted, so the first visit is instant
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev && uv run python experiments/run_hwsets.py
ENV PORT=8080
CMD ["uv", "run", "hwsets", "serve", "--port", "8080"]
