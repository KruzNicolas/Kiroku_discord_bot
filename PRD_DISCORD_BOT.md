# PRD: Discord Bot Adapter for Kiroku API

## 1. Overview

Build a Discord bot adapter that receives messages from specific channels and routes them to Kiroku API endpoints.

This adapter is a **channel gateway**, not a business-logic service. Domain logic remains in the Kiroku API.

---

## 2. Goals

1. Route channel messages to correct API endpoints.
2. Enforce access restrictions by Discord IDs.
3. Provide clear in-channel feedback (success/failure/retry).
4. Avoid duplicate processing with idempotency keys.

---

## 3. Scope

### In scope

- Discord bot event handling.
- Channel-based routing.
- Service-token auth to Kiroku API.
- Idempotency-key generation and propagation.
- Basic retry and status reactions.

### Out of scope

- Core processing logic (videos/receipts/study assets).
- Multi-tenant support.
- Advanced moderation workflows.

---

## 4. Routing Rules

### Channels

- `videos` channel -> `/api/v1/videos` or `/api/v1/videos/batch`
- `receipts` channel -> `/api/v1/receipts`
- `receipts-manual` channel (or command) -> `/api/v1/receipts/manual`
- `japanese` channel -> `/api/v1/study-assets/japanese`

### Channel-gated mode (no slash commands)

For private-server operation, routing is channel-only (no slash commands required):

- `videos` -> text message with one or more YouTube links.
- `receipts` -> image attachment required; message text is optional `store_hint`.
- `receipts-manual` -> structured text payload only (manual purchases).
- `japanese` -> image attachment required; message text maps to optional `note`.

If content type does not match channel policy, bot rejects with concise guidance (`❌`).

### Behavior

- If video channel message has 1 YouTube URL -> single endpoint.
- If it has 2+ URLs -> batch endpoint.
- Attachments in receipts/study channels are normalized before API call:
  - Accept common image sources (`jpg`, `jpeg`, `png`).
  - Send receipts to API as `multipart/form-data` with:
    - `receipt_image` (binary file)
    - optional `store_hint`
    - optional `request_id`
  - Send Japanese study assets to API as `multipart/form-data` with:
    - `image` (binary file, jpeg/png)
    - optional `note`
- Manual small purchases can be sent as JSON to `/api/v1/receipts/manual`:
  - `date`, `category`, `store`, `items[{product, quantity, price}]`, `request_id` created by the bot.

---

## 5. Security

### Required allowlists

- `guild_id` allowlist
- `channel_id` allowlist
- `user_id` allowlist

### Strict validation order

Every incoming Discord event must be validated in this order:

1. Ignore bot/system messages.
2. Validate `guild_id` is allowlisted.
3. Validate `channel_id` is allowlisted.
4. Validate `user_id` allowlist.
5. Validate payload type is allowed for that channel.

If any step fails, do not forward to API.

### API auth

- Header: `Authorization: Bearer <INTERNAL_API_TOKEN>`

### Required forward headers to Kiroku API

Every request forwarded to `/api/v1/*` must include:

- `Authorization: Bearer <INTERNAL_API_TOKEN>`
- `X-Source: discord-bot`
- `X-Source-Message-Id: <discord_message_id>`
- `X-Source-User-Id: <discord_user_id>`
- `Idempotency-Key: discord:<guild_id>:<channel_id>:<message_id>`

---

## 6. Idempotency

### Header format

- `Idempotency-Key: discord:<guild_id>:<channel_id>:<message_id>`

### Result

- Duplicate message delivery or emoji retry does not duplicate business processing.

### Additional rule

- The same key must be reused across retries for the same Discord message.
- A new message must always generate a new key.

---

## 7. Error Handling Matrix

### Kiroku API response handling

- `200/201` -> success feedback (`✅`) with short summary.
- `400` -> user input error (`❌`) with actionable guidance (what to fix).
- `401` -> integration/configuration error; log as high-priority (`❌`), do not expose token details.
- `429` -> transient rate limit; respect `Retry-After`, retry automatically.
- `502/503` -> transient upstream/API failure; retry with backoff, then fail with concise message.
- `500` -> unexpected API error; no aggressive retry loop, return friendly failure and log full context.

### Retry policy (bot side)

- Retry only for: `429`, `502`, `503`, network timeout.
- Max attempts: `3`.
- Backoff: exponential (`1s`, `2s`, `4s`) + jitter.
- Do not retry for: `400`, `401`, `403`, `404`, `422`.

---

## 8. UX/Feedback

### Reactions

- Processing: `⏳`
- Success: `✅`
- Failure: `❌`
- Retry trigger: `🔁` (optional)

### Retry policy

- Bot retries transient failures with exponential backoff.
- On hard failure, post concise error in thread/reply.

### Emoji controls

- `⏳` while processing
- `✅` on success
- `❌` on failure
- `🔁` to trigger retry (manual operator action)

### Batch partial-failure UX (videos)

When `/api/v1/videos/batch` returns `failed_urls`:

1. Bot posts a summary message:
   - total/success/fail counts
   - explicit list of failed links
2. Bot adds `🔁` reaction to that summary.
3. If authorized user reacts with `🔁`, bot retries **only failed links**.
4. Retry message includes new result summary and remaining failures (if any).

Authorization for `🔁` reaction:

- message author, or
- allowlisted moderators/admins.

Safety:

- max manual retries per batch message (recommended: `2`)
- cooldown between retries (recommended: `10s`)

---

## 9. Routing input contracts (strict)

### Videos channel

- Verify the message contains a valid YouTube URL(s).
- Extract all YouTube URLs from message text.
- `1 URL` -> `/api/v1/videos` with JSON `{ "url": "..." }`
- `2+ URLs` -> `/api/v1/videos/batch` with JSON `items[]`.

### Receipts channel

- Requires image attachment.
- Send `multipart/form-data`:
  - `receipt_image` (required)
  - `store_hint` (optional)
  - `request_id` (optional)
  - `batch_category` (optional)

### Receipts manual command

Use explicit command format to avoid parser ambiguity:

```text
/receipt_manual date=YYYY-MM-DD category=<Category> store="<Store Name>" items="Product A|1|2000;Product B|0.5|15000"
```

Mapping:

- `date` -> string (`YYYY-MM-DD`)
- `category` -> one allowed API category
- `store` -> string
- `items` -> split by `;`, then each item split by `|` => `{product, quantity, price}`

### Study Japanese channel

- Requires image attachment.
- Send `multipart/form-data`:
  - `image` (required)
  - `note` (optional)

---

## 10. Attachment normalization and limits

- Accepted source formats from Discord: `jpg`, `jpeg`, `png`.
- Bot-side size limit (recommended): `<= 20MB` per file.
- If file exceeds limit or is unsupported: return user-facing guidance and do not forward invalid payload.

---

## 11. Configuration (`.env`)

- `DISCORD_BOT_TOKEN=`
- `DISCORD_ALLOWED_GUILD_IDS=`
- `DISCORD_ALLOWED_CHANNEL_IDS=`
- `DISCORD_ALLOWED_USER_IDS=`
- `API_BASE_URL=`
- `INTERNAL_API_TOKEN=`
- `REQUEST_TIMEOUT_SECONDS=20`

---

## 12. Observability

- Structured logs with:
  - `source=discord-bot`
  - `guild_id`
  - `channel_id`
  - `message_id`
  - `user_id`
  - `endpoint`
  - `status_code`

### Metrics (minimum)

- `bot_requests_total{endpoint,status}`
- `bot_retries_total{endpoint,reason}`
- `bot_idempotency_replays_total{endpoint}`
- `bot_failures_total{endpoint,error_type}`

---

## 13. Acceptance Criteria

1. Messages in allowed channels are routed correctly.
2. Unauthorized guild/channel/user messages are ignored.
3. Duplicate message events do not create duplicate API processing.
4. Success/failure feedback is visible in Discord.
5. Logs contain correlation fields for debugging.
6. Retry policy follows status-code matrix and honors `Retry-After`.
7. Manual receipts command parsing is deterministic and validated.
