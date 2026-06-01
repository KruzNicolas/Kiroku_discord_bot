FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt
COPY . .
CMD ["uv", "run", "python", "-m", "discord_bot.main"]