# Discord Bot - Kiroku Bridge

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Private](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)

Discord bot that acts as a gateway to the Kiroku API. Receives messages from specific channels and automatically routes them to the corresponding endpoints to process YouTube videos, purchase receipts, and Japanese study assets.

## 🚀 Features

- **Smart channel-based routing**: Each channel has a specific purpose and the bot knows exactly which endpoint to send each message to
- **Strict security validation**: Only allows access from authorized guilds, channels, and users
- **Idempotency**: Prevents duplicate processing through idempotency keys
- **Automatic retries**: Retry policy with exponential backoff for transient failures
- **Real-time feedback**: Reactions and messages indicating processing status
- **Batch support**: Multiple video processing in a single message

## 📋 Prerequisites

1. **Python 3.11+**
2. **Discord Bot Token** (create at [Discord Developer Portal](https://discord.com/developers/applications))
3. **Kiroku API** running and accessible
4. **Environment variables** configured (see configuration section)

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone git@github.com:KruzNicolas/Kiroku_discord_bot.git
cd Kiroku_discord_bot
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Discord
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_ALLOWED_GUILD_IDS=guild_id_1,guild_id_2
DISCORD_ALLOWED_CHANNEL_IDS=channel_id_1,channel_id_2
DISCORD_ALLOWED_USER_IDS=user_id_1,user_id_2

# Kiroku API
API_BASE_URL=http://localhost:8000
INTERNAL_API_TOKEN=your_internal_api_token

# Optional: request timeout
REQUEST_TIMEOUT_SECONDS=20
```

## 🎮 Usage

### Channels and Behavior

| Channel | Content Type | API Endpoint |
|---------|--------------|--------------|
| `videos` | YouTube URLs (1 or more) | `/api/v1/videos` or `/api/v1/videos/batch` |
| `receipts` | Receipt image + optional text | `/api/v1/receipts` |
| `receipts-manual` | Structured text | `/api/v1/receipts/manual` |
| `japanese` | Study asset image | `/api/v1/study-assets/japanese` |

### Examples by Channel

#### 📺 Videos Channel

Send one or more YouTube links:

```
https://www.youtube.com/watch?v=abc123
https://www.youtube.com/watch?v=def456
```

- **1 URL** → Processes individually
- **2+ URLs** → Processes in batch automatically

#### 🧾 Receipts Channel

Send an image (JPG/PNG) with optional text as `store_hint`:

```
Falabella
```

Attach receipt image.

#### 📝 Manual Receipts Channel

Use structured command format:

```
/receipt_manual date=2026-03-24 category=Others store="MercadoLibre" items="Keyboard X|1|400000;Mouse Y|1|25000"
```

Format: `date=YYYY-MM-DD category=<Category> store="<Name>" items="Product|quantity|price;..."`

Valid categories: `Groceries`, `Pharmacy`, `Transport`, `Utilities`, `Subscriptions`, `Debt`, `Leisure`, `Others`

#### 🇯🇵 Japanese Channel

Send an image with optional text as note:

```
for future manual anki cards
```

Attach study material image.

### Bot Reactions

| Reaction | Meaning |
|----------|---------|
| ⏳ | Processing |
| ✅ | Success |
| ❌ | Error |
| 🔁 | Retry (only for transient failures or partial batches) |

## 🧪 Testing

### Run tests

```bash
source .venv/bin/activate
pytest
```

### Run tests with coverage

```bash
pytest --cov=src/discord_bot
```

### Secret scan (pre-commit)

```bash
./scripts/scan-secrets.sh
```

## 🏗 Architecture

The bot follows a modular layered architecture:

```
src/discord_bot/
├── discord/           # Discord handlers and events
├── transport/         # HTTP client to Kiroku API
├── attachments/       # Attachment normalization
├── security/          # Allowlists and validations
├── routing/           # Channel-based routing logic
├── domain/            # Models and business rules
├── observability/     # Logging and metrics
└── config.py          # Centralized configuration
```

### Processing Flow

1. **Reception**: Bot receives Discord message
2. **Validation**: Verifies guild, channel, and user against allowlists
3. **Routing**: Determines endpoint based on channel and content type
4. **Normalization**: Processes attachments and text according to API contract
5. **Dispatch**: Forwards to Kiroku API with required headers
6. **Feedback**: Reactions and messages based on response

### Headers Sent to Kiroku API

```
Authorization: Bearer <INTERNAL_API_TOKEN>
X-Source: discord-bot
X-Source-Message-Id: <discord_message_id>
X-Source-User-Id: <discord_user_id>
Idempotency-Key: discord:<guild_id>:<channel_id>:<message_id>
```

## 🔒 Security

### Required Allowlists

- `DISCORD_ALLOWED_GUILD_IDS`: Allowed server IDs
- `DISCORD_ALLOWED_CHANNEL_IDS`: Allowed channel IDs
- `DISCORD_ALLOWED_USER_IDS`: Allowed user IDs

### Strict Validation Order

1. Ignore bot/system messages
2. Validate `guild_id` in allowlist
3. Validate `channel_id` in allowlist
4. Validate `user_id` in allowlist
5. Validate content type is allowed for that channel

### Idempotency

- Key generated per message: `discord:<guild>:<channel>:<message>`
- Emoji retries use the same key
- Prevents duplication in the API

## 📊 Observability

### Structured Logs

Each log includes:
- `source=discord-bot`
- `guild_id`, `channel_id`, `message_id`, `user_id`
- `endpoint`, `status_code`

### Metrics

- `bot_requests_total{endpoint,status}`
- `bot_retries_total{endpoint,reason}`
- `bot_idempotency_replays_total{endpoint}`
- `bot_failures_total{endpoint,error_type}`

## 🔧 Retry Policies

### When to Retry

- `429 Too Many Requests`: Respects `Retry-After` header
- `502 Bad Gateway`: Transient upstream failure
- `503 Service Unavailable`: Temporarily unavailable service
- Network timeout

### When NOT to Retry

- `400 Bad Request`: User error
- `401 Unauthorized`: Configuration error
- `403 Forbidden`: Access denied
- `404 Not Found`: Resource doesn't exist
- `422 Unprocessable Entity`: Validation failed

### Backoff

Exponential with jitter: `1s` → `2s` → `4s` + random jitter

## 📁 Project Structure

```
discord_bot/
├── src/discord_bot/     # Main source code
├── tests/               # Unit and integration tests
├── scripts/             # Utility scripts
├── .env.example         # Environment variables template
├── pyproject.toml       # Python package configuration
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Development dependencies
└── README.md            # This file
```

## 🚨 Troubleshooting

### Bot doesn't respond to messages

1. Verify `DISCORD_BOT_TOKEN` is correct
2. Confirm bot has intents enabled in Discord Developer Portal
3. Check that guild/channel/user are in allowlists

### 401 Error when calling API

- `INTERNAL_API_TOKEN` doesn't match Kiroku API token
- Verify both sides use the same token

### 429 Error (Rate Limit)

- Bot is making too many requests per minute
- Wait or reduce message volume
- API includes `Retry-After` header with seconds to wait

### Attachments not processing

- Verify format: only `jpg`, `jpeg`, `png`
- Verify size: maximum 20MB per file

## 📝 Important Notes

- Keep `.env` out of git (already in `.gitignore`)
- Use `.env.example` as template without real secrets
- Run `./scripts/scan-secrets.sh` before each commit
- Don't commit `__pycache__/`, `.venv/`, or linter cache files

## 📄 License

Private. All rights reserved.

## 👨‍💻 Author

Developed as part of the Kiroku ecosystem.
