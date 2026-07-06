FROM python:3.12-slim

# uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy the whole project (source, app.py, data, pyproject, lock).
# .dockerignore keeps .venv/.env/.git out of the image.
COPY . /app

# Install dependencies into the project venv (no dev deps)
RUN uv sync --no-dev

# Streamlit / Cloud Run runtime settings
ENV STREAMLIT_SERVER_HEADLESS=true
EXPOSE 8080

# Cloud Run sends traffic to 8080; bind Streamlit there on all interfaces
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
