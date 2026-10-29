---
name: hermes-on-oracle-free-tier
description: "Run an always-on Hermes gateway on an Oracle Cloud Always Free Arm VM."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux]
metadata:
  agent:
    tags: [hermes, oracle-cloud, oci, free-tier, arm, gateway, server, systemd]
    related_skills: [hermes-messaging-channels, hermes-cron-jobs, hermes-provider-credentials]
---

# Hermes on an Oracle Cloud Always Free VM

## When to Use

You want Hermes reachable 24/7 (chat channels, cron jobs, alerts) without leaving
a PC on, and without paying for a VPS. The VM is the always-on backbone; heavy
interactive work can stay on your own machine.

## Know the limits before you start

Oracle changes these numbers. Re-read the
[Always Free resources page](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
before planning around them. As of this writing it says:

- **Arm (`VM.Standard.A1.Flex`)**: 1,500 OCPU-hours and 9,000 GB-hours a month,
  which Oracle states as **2 OCPUs and 12 GB of memory** in total. Use one 2-OCPU
  VM, or two 1-OCPU VMs.
- **Block storage**: 200 GB in total, and boot volumes count against it. The minimum
  boot volume is 47 GB.
- **Home region only.** Always Free instances must be created in your tenancy's
  home region.
- **Idle reclamation.** An Always Free instance can be reclaimed if, over 7 days,
  its 95th-percentile CPU, network **and** (on A1) memory are all under 20%. An
  idle Hermes gateway can fit that description. If you are counting on Pay As You
  Go to avoid reclamation, confirm it in Oracle's current terms; the resources
  page does not say.
- **"Out of host capacity"** means Oracle has no free Arm hosts in that
  availability domain right now. Retry in another availability domain, or later.
  Oracle's own suggestion is to upgrade to Pay As You Go, which gives access to
  more capacity and does not charge for usage inside the Always Free limits.

Pay As You Go is a real billing account: anything beyond the free limits is
charged. Budgets only send alerts; they do not stop resource creation. Use
compartment quotas if you need a hard ceiling.

## Procedure

### 1. A dedicated SSH key

```bash
ssh-keygen -t ed25519 -f ~/.ssh/hermes_vm -N ''
```

The private key stays on your machine; the public key goes into the instance form.
Adding a key after creation is more work, so get it right in the form.

### 2. Create the instance

Console: Compute → Instances → Create instance.

- Image: Canonical Ubuntu 24.04 **aarch64** (an x86 image will not boot on an Arm
  shape). The Minimal image is smaller.
- Shape: `VM.Standard.A1.Flex`, OCPUs and memory inside the limits above.
- Networking: a public subnet with a route to an internet gateway, and "assign a
  public IPv4 address" checked, or you cannot reach it over SSH.
- Paste the public key from step 1.

With the OCI CLI the same thing is `oci compute instance launch` with
`--shape VM.Standard.A1.Flex --shape-config '{"ocpus":2,"memoryInGBs":12}'`, your
availability domain, compartment, subnet and image OCIDs, and
`--ssh-authorized-keys-file ~/.ssh/hermes_vm.pub`. On "out of host capacity",
retry with the next `--availability-domain`.

### 3. Install Hermes and the gateway service

```bash
ssh -i ~/.ssh/hermes_vm ubuntu@<public-ip>
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes doctor
hermes gateway install            # user service
sudo loginctl enable-linger $USER # keep it running after you log out
hermes gateway status
```

Hermes's docs recommend the system service for headless hosts that must come back
after a reboot without anyone logging in (`sudo hermes gateway install --system`).
Either works; pick one and verify it after a reboot.

Then connect a channel by following `hermes-messaging-channels`: allowlist before
token, one token per poller.

### 4. Do not copy your desktop config wholesale

A `config.yaml` from a Windows or macOS machine carries hooks, TTS settings and
paths that point at files that do not exist on the VM, and can break terminal and
file tools. Start from a clean config and bring settings across one at a time.
If you copy `.env`, strip CRLF line endings (`sed -i 's/\r$//' ~/.hermes/.env`):
a stray `\r` can silently break token and allowlist checks.

Keep memory usage in mind on a 12 GB box. Anything that spawns several agent
workers at once (parallel task dispatch, many browsers) can push the gateway out
of memory. Enable those features deliberately, not by copying a config that had
them on.

### 5. Harden it

The gateway gives whoever is allowlisted a shell on this VM. Treat it like one.

- SSH: `PasswordAuthentication no` and `PermitRootLogin no` in `sshd_config`; only
  your key in `authorized_keys`; `sudo passwd -l ubuntu`.
- Firewall: the gateway connects out to the chat platform (long polling), so it
  needs no inbound port. Allow only SSH, ideally only from addresses you trust.
  This needs both the OCI security list or NSG **and** the host firewall.
- Install `fail2ban`, or move SSH behind a private network such as Tailscale and
  close port 22 to the internet.
- Verify from outside: password login, root login and an unknown user must all be
  refused.

### 6. Credentials: one machine per login

Subscription OAuth refresh tokens are often single-use. If the same account is
logged in on your PC and on the VM, whichever refreshes first kills the other's
copy. Keep each login on one machine, or sync them deliberately
(see `hermes-provider-credentials`). The same goes for bot tokens: one gateway
per token.

### 7. Back it up off the box

Back up `~/.hermes/memories`, `~/.hermes/skills`, `config.yaml` and anything else
you would hate to rebuild to somewhere that is not this VM. Ubuntu Minimal ships
without `crontab`; use a systemd user timer (lingering is already on), or a Hermes
cron job (see `hermes-cron-jobs`). Never put `auth.json` or `.env` into an
unencrypted backup.

## Operating notes

- **Disk fills from old work trees.** `node_modules`, build output and browser
  profiles under `~/.hermes` grow quickly on a 47-50 GB boot volume. Alert well
  before full (85% is a sensible line), and kill browsers left running for hours.
- **The boot volume grows online:** `oci bv boot-volume update --size-in-gbs N`,
  wait for AVAILABLE, rescan the device, `growpart`, `resize2fs`. No reboot. Stay
  inside the 200 GB total.
- **Changing OCPUs or memory reboots the VM.** Schedule it for a quiet hour, and
  have a post-boot check report that the gateway and its channels came back.
- **A new OCI API key returns intermittent 401s for a few minutes.** Retry before
  debugging. Generate the key pair on the VM and paste only the public key into
  the console.
- **Audit the free limits from the VM.** A weekly job that lists instances,
  volumes and backups and alerts only when something exceeds Always Free is
  cheaper than finding out from the bill.

## Verification

```bash
hermes gateway status                 # running
systemctl --user status hermes-gateway   # or the system unit, if you installed that
curl -s -H "Authorization: Bearer Oracle" http://169.254.169.254/opc/v2/instance/ | grep -i shape
```

Then the two checks that matter:

1. Reboot the VM (`sudo reboot`), wait, and confirm the gateway is back and its
   channel reports connected, without you logging in.
2. Send the bot a message from an allowlisted account and get an answer, and
   confirm that a non-allowlisted account is refused.
