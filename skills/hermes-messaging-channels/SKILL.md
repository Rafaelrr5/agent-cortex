---
name: hermes-messaging-channels
description: "Connect Telegram or another chat app to the Hermes gateway safely, and keep it alive."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [hermes, gateway, telegram, messaging, security, autostart, watchdog]
    related_skills: [hermes-cron-jobs, hermes-on-oracle-free-tier]
---

# Hermes: wiring a chat channel into the gateway

Use when someone wants to reach their agent from a chat app (Telegram, Discord,
Slack, Matrix, WhatsApp...), hands you a bot token, or reports that a channel that
used to work has gone quiet. This covers what is the same on every platform:
where the credential lives, the access gate that must be closed before the channel
goes live, why nothing happens until a restart, and why the gateway must be made
to start and stay started on its own.

Platform and OS details:

- `references/telegram.md`: BotFather, read-only Bot API probes, `.env` keys,
  failure signatures.
- `references/gateway-autostart-windows.md`: proving whether the login item
  actually fired, and a Task Scheduler replacement that doubles as a watchdog.
  Ships `templates/windows-gateway-task.xml`.

Behaviour below was checked against Hermes Agent v0.21 and its documentation.

## First: is this a gateway channel at all?

| | Gateway platform channel | Queue bridge |
|---|---|---|
| examples | Telegram, Discord, Slack | voice assistants, webhooks, SMS gateways |
| why | Hermes ships a driver | no driver, or a hard response deadline |
| response budget | none, a turn can take minutes | seconds |

If the surface demands an answer faster than an agent turn (voice assistants give
you a few seconds), no gateway configuration helps. You need a two-step design
that queues the request and reads the answer back later. Check the deadline
before designing anything.

## One channel per context

Keep personal, work and client contexts on separate bots, hosts and credentials.
"You already have a bot/server for X" is only an argument when X belongs to the
same context. One bot shared across contexts also collides with the
one-token-one-poller rule below.

## Close the door before opening it

A messaging channel is **remote shell access**. The agent behind it has a terminal.
Whoever is admitted to the bot gets that shell.

In Hermes v0.21 the gateway denies users who are not allowlisted or paired, so an
empty allowlist is closed by default. The door opens if any of these is truthy:
`GATEWAY_ALLOW_ALL_USERS`, a per-platform `<PLATFORM>_ALLOW_ALL_USERS`, or an
adapter that enforces its own access policy. Older versions and other agents have
treated "empty" as "everyone". Read the semantics of the version in front of you
instead of assuming it fails closed.

Order of operations, not to be inverted:

1. Validate the token with a read-only probe.
2. Determine the owner's user id.
3. Write the token **and** the allowlist in the same edit, and confirm no
   `*_ALLOW_ALL_USERS` is set.
4. Only then let the gateway load it.

Writing the token first and "adding the allowlist in a moment" opens a window you
do not control. A login item, a scheduled task or a watchdog can start the gateway
at any time and load whatever is on disk at that moment.

### Get the owner's id instead of asking for it

People message a new bot immediately, out of curiosity. That message sits in the
update queue with their numeric id. Read it from the platform's update endpoint
(Telegram: `getUpdates`), check the username matches the person you are setting
up, and only ask if the queue is empty. The alternative is pairing: an unknown
user DMs the bot, gets a code, and the operator approves it with
`hermes pairing approve`.

## The credential file is protected: expect the refusal

`HERMES_HOME/.env` is a credential file, and the agent's file-editing tools refuse
to write it. That is correct; do not route around the guard with a less strict
tool. Channel credentials live in `.env`, not `config.yaml`, so `hermes config set`
does not cover them. `hermes gateway setup` is the official path and is
interactive.

When a non-interactive edit is unavoidable, make it with a uniqueness assertion and
a backup, and read back a redacted confirmation:

```bash
cp "$HERMES_HOME/.env" "$HERMES_HOME/.env.bak.$(date +%Y%m%d%H%M%S)"
python - "$HERMES_HOME/.env" <<'PY'
import io, sys
p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()
old = "# TELEGRAM_BOT_TOKEN=\n"
new = "TELEGRAM_BOT_TOKEN=<value>\nTELEGRAM_ALLOWED_USERS=<owner-id>\n"
assert s.count(old) == 1, "anchor not unique or not found"
io.open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new))
print("OK")
PY
grep -n "^TELEGRAM_" "$HERMES_HOME/.env" | sed 's/\(TOKEN=\).*/\1<REDACTED>/'
```

The assertion is the point: `.env` templates repeat the same comment shapes across
platform blocks, and a blind replace can hit the wrong one. Write with `\n` line
endings. A CRLF in `.env` can silently break token and allowlist parsing on Linux.

## Verify the channel actually loaded

The gateway reads `.env` at boot. A gateway started before your edit runs with no
channel and looks perfectly healthy:

```bash
hermes gateway status     # "running": necessary, not sufficient
python -c "import json,os;print(json.load(open(os.path.join(os.environ['HERMES_HOME'],'gateway_state.json')))['platforms'])"
```

`"platforms": {}` means no channel is attached. Compare the state file's start time
with your edit time. A loaded channel appears as a key, with its own state.

## A restart is consent-gated: ask, don't route around it

`hermes gateway restart` takes down every other channel and the cron ticker that
lives inside the gateway. If the restart is blocked pending approval, **stop**. Do
not rephrase it, do not reach the same result with `stop` + `start`, do not
background it. A blocked action is consent withheld. Give the user the exact
command and the decision. Better: ask up front, "config written; restart now, or
will you?"

## One token, one poller

In long-polling mode each update goes to **exactly one** poller. The same token on
two machines makes them race, and the user sees a bot that answers half the time.
For a second machine, create a second bot (or use webhook mode, which needs a
public URL).

When moving a token to another machine, comment it out on the old one, keep a
dated note saying where it went, and confirm the old poller is off before ever
reactivating it.

## The channel is only as alive as the gateway

A correctly configured channel behind a dead gateway looks exactly like a broken
bot: messages go nowhere and nothing raises an alarm. On one measured machine the
gateway exited uncleanly and stayed dead for **five days**. The user found out by
messaging the bot and getting silence.

"It should work every time I turn the PC on" is a request about uptime. Treat it as
part of the deliverable.

### Installed is not the same as ran

`hermes gateway status` saying a login item is installed means a file exists. To
know whether it fired, compare the boot time with the gateway's process start time:

```powershell
$b=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$p=Get-Process -Id <gateway-pid>
"delta $([math]::Round(($p.StartTime-$b).TotalMinutes,1)) min"
```

A delta of minutes means the autostart fired. Hours means it did not, and something
else started the process later. On desktop installs that is usually the user
opening the Hermes app, which is exactly what hides the failure. On Linux, use
`systemctl --user status hermes-gateway` and `journalctl --user -u hermes-gateway`,
and make sure lingering is enabled so the service outlives logout.

### If the launcher does not fire, change the mechanism

1. Native first: `hermes gateway install` (with its start-on-login/start-now
   options), then measure with the delta probe.
2. Only if the native login item is **measured** not to fire, move to the OS
   scheduler. On Windows: `references/gateway-autostart-windows.md`.

Give the replacement a **repeating** trigger, not only a logon trigger. A
15-minute repeat doubles as a watchdog, and that is the part that fixes the
five-day silent death.

Repeated launches are safe. A second gateway start on the same machine detects the
running one ("a gateway is already running", wording varies by version) and exits
or attaches without touching it. Old and new launchers can coexist. That is per machine only; it does
nothing for the one-token-one-poller collision between two machines.

### Prove it by killing it

```
kill the gateway → fire the launcher → status shows a NEW pid
                                     → the platform shows connected
fire the launcher again without killing → same pid, still connected
```

Give it 40-50 seconds before judging. A channel mid-connect at 10 seconds reads as
a failure. "The task is registered" is not a result; a new pid plus a reconnected
platform is.

When you shell out to test a launcher, quote paths with spaces. An unquoted
`...\Start Menu\Programs\Startup\...` makes a working launcher look broken.

## Token pasted into chat

If the user pasted the token into the conversation, it now also sits in the
session store on disk. Say so once, calmly: it is a local copy on a machine that
already holds `.env`, not an emergency. Offer revoke-and-replace with the new
secret written to a file by the user, so it never transits chat. Let them choose.

## Verification

```bash
# 1. token identity, before writing anything
curl -s "https://api.telegram.org/bot$TOKEN/getMe"
# 2. keys landed, redacted. Anchor with ^: a commented line must not match
grep -n "^TELEGRAM_" "$HERMES_HOME/.env" | sed 's/\(TOKEN=\).*/\1<REDACTED>/'
# 3. allowlist is set and nothing opens the door
grep -q "^TELEGRAM_ALLOWED_USERS=[0-9]" "$HERMES_HOME/.env" || echo "FAIL: no allowlist"
grep -nE "^(GATEWAY|TELEGRAM)_ALLOW_ALL_USERS=(1|true|yes)" "$HERMES_HOME/.env" && echo "FAIL: open to everyone"
# 4. channel attached after the restart: the platforms key in gateway_state.json
# 5. real round trip: the owner messages the bot and gets an answer
# 6. uptime: the autostart fired (delta in minutes), and a killed gateway comes back
```

Steps 1-3 can be checked by tools. Steps 4-5 need the restart. Until then, report
the channel as configured but not live. Only an end-to-end reply proves a working
channel.
