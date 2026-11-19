FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# git is required for uv to fetch semente-agents from the lapig-ufg/semente
# repository; ffmpeg is required by the TTS feature (pydub) and by the biomass video tool.
RUN apt-get update && apt-get -y install git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache

COPY . .

# Strip Windows line endings in case the script was checked out with CRLF.
RUN sed -i 's/\r$//' scripts/start.sh

EXPOSE 8501 8080

# Streamlit chat by default (port 8501, as before); PASTO_BACANO_SERVICE=api
# starts the agent API instead (see scripts/start.sh).
CMD ["sh", "scripts/start.sh"]
