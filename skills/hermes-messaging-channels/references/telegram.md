# Telegram: Hermes gateway specifics

The rules that apply to every platform (allowlist before live, the protected `.env`,
restart consent, `platforms: {}`) are in `SKILL.md`.

## Creating the bot

The user does this in [@BotFather](https://t.me/BotFather): `/newbot`, a display
name, and a username ending in `bot`. BotFather replies with a token shaped
`<bot_id>:<secret>`. The numeric part before the colon is the bot's own user id.

Useful BotFather commands: `/revoke` (rotates the token; the old one dies at once),
`/setdescription`, `/setuserpic`, `/setprivacy`.

## Read-only probes, before writing anything

```bash
T="<token>"
curl -s "https://api.telegram.org/bot$T/getMe"          # identity: proves the token is live
curl -s "https://api.telegram.org/bot$T/getWebhookInfo" # delivery mode and backlog
curl -s "https://api.telegram.org/bot$T/getUpdates?limit=3"  # queued messages: the owner's id is here
```

Keep the token out of anything that gets logged or pasted back: shell history,
transcripts, screenshots.

`getMe` returns `{"ok":true,"result":{"id":...,"username":...}}`; a bad token
returns `401 Unauthorized`. `getWebhookInfo` with `"url":""` means long polling
(the default). A non-zero `pending_update_count` means messages are waiting for a
poller.

### The owner's id from `getUpdates`

```json
{"message":{"from":{"id":123456789,"is_bot":false,"username":"..."},
            "chat":{"id":123456789,"type":"private"}}}
```

`from.id` is the user id for `TELEGRAM_ALLOWED_USERS`. In a private chat `chat.id`
is the same number, and it is what `TELEGRAM_HOME_CHANNEL` wants. In groups
`chat.id` is a different, negative number; do not mix them up.

Calling `getUpdates` while no gateway polls is fine, but it confirms offsets on the
server. Read once, do not loop. If a gateway is already polling, your call competes
with it for the same updates.

## `.env` keys

| Key | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from BotFather; its presence activates the channel |
| `TELEGRAM_ALLOWED_USERS` | comma-separated user ids. **Set it** |
| `TELEGRAM_ALLOW_ALL_USERS` | opens the bot to everyone. Leave unset |
| `TELEGRAM_HOME_CHANNEL` | default chat for cron delivery (a private DM is your user id) |
| `TELEGRAM_WEBHOOK_URL` | setting it switches from long polling to webhook mode |

`config.yaml` has a small separate `telegram:` block with behaviour toggles, not
credentials. An empty block there says nothing about whether the channel is
configured. The token in `.env` is what matters.

## Privacy mode and groups

By default a bot in a group only sees messages that mention it or reply to it. If
it should read everything, disable privacy with BotFather `/setprivacy`, then
**remove and re-add** the bot to the group for it to take effect.

## Failure signatures

| Symptom | Cause |
|---|---|
| `401 Unauthorized` on `getMe` | wrong token, or revoked by a later `/revoke` |
| gateway "running", bot silent | `.env` written after the gateway started: `platforms: {}`, restart needed |
| bot answers only sometimes | two gateways polling the same token |
| strangers can use the bot | an allow-all flag is set, or the allowlist is in a commented line |
| cron output goes nowhere | `TELEGRAM_HOME_CHANNEL` unset |
| `No messaging platforms enabled` at boot, no Telegram error | the token line is still commented (`# TELEGRAM_BOT_TOKEN=...`). Writing a value onto a template line keeps the `#`. Grep with `^TELEGRAM_` (anchored) after every edit |
| a polling-conflict state with no current problem | leftover state from a token that was deliberately moved to another machine. Compare the writer pid in `gateway_state.json` with the current gateway pid, and check whether the token is commented out, before restarting anything |
