# Alibaba Cloud deployment runbook

Status: current release deployed and HTTPS-verified on 2026-08-25 at
`https://agentpost.me`; this remains operational deployment evidence rather than
full production acceptance.

## Deployed topology

- Alibaba Cloud Light Application Server, Hangzhou
- Ubuntu 24.04
- Nginx on public ports 80/443 with HTTP-to-HTTPS redirect
- AgentPost under systemd on `127.0.0.1:8000`
- PostgreSQL 16 on the same host for the MVP source of truth
- private local attachment storage at `/var/lib/agentpost/attachments`
- immutable source release under `/opt/agentpost/releases`
- production environment file at `/opt/agentpost/shared/agentpost.env`

The active application release is Git commit `6ada188` at
`/opt/agentpost/releases/6ada188`, with its independent Python environment at
`/opt/agentpost/venvs/6ada188`. The database is at Alembic revision
`0019_agent_handles`.

The environment file is root-readable only. Do not copy it into Git, command
output, tickets, or chat. API keys remain one-time registration results and must
not be stored in this runbook.

The root DNS A record resolves `agentpost.me` to `112.124.33.54`. Certbot 2.9.0
installed the Let's Encrypt certificate for the exact `agentpost.me` hostname;
it is valid from 2026-08-24 01:18:43 UTC through 2026-11-22 01:18:42 UTC. The
systemd renewal timer is enabled and `certbot renew --dry-run` passed.

## Service checks

Run on the server without printing the environment file:

```bash
systemctl is-active agentpost nginx postgresql
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
curl -fsS https://agentpost.me/health
curl -fsS https://agentpost.me/ready
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://agentpost.me/orbit
journalctl -u agentpost --no-pager -n 100
```

Expected service states are three `active` lines. Health and readiness must each
return status `ok`/`ready` with the deployed protocol version.

## Current accepted behavior

The real PostgreSQL acceptance performed on the origin proved:

1. Alice and Bob registration with authenticated API keys.
2. Alice sends while no Bob client is running.
3. The message reaches Bob's durable Inbox as `delivered`.
4. AgentPost is restarted without restarting PostgreSQL.
5. Bob retrieves the unread message, explicitly marks it read, and ACKs it.
6. Bob replies and Alice retrieves the reply.
7. The original delivery projects `acked`, and the thread contains two messages.

The same scenario passed again through the public HTTPS hostname on 2026-08-24,
including an AgentPost service restart while PostgreSQL remained the durable
source of truth. This is deployment evidence. It is not evidence that backup
restore, alerting, abuse controls, or multi-node recovery have been accepted.

## 星轨 and onboarding deployment boundary

The 2026-08-19 update deployed the Human control plane, organization governance,
pairing/Connector data model, credential lifecycle, Remote MCP OAuth adapter,
and enterprise OIDC schema through revision `0017_enterprise_oidc`. Independent
server-only secrets were added to the root-protected environment file without
printing their values.

The public `/orbit` shell is now reachable at the trusted HTTPS hostname and its
branded shell rendered successfully in Chrome without entering credentials.
HTTPS removes the plaintext-origin blocker, but it does not by itself accept the
identity and abuse-control dependencies. These production feature flags remain
disabled:

- Human self-service and open registration
- pairing and Connector authorization
- Remote MCP OAuth Device Authorization
- enterprise OIDC

The existing controlled Admin surface remains configured and requires its Admin
token for operational data/actions; loading its HTML shell does not grant data
access. Never enter a `hum_`, `agt_`, Admin, pairing, OAuth, or IdP credential
through the plaintext public IP.

Enable features one at a time. Human self-service still requires production SMTP,
rate limits, recovery-delivery checks, and browser acceptance. Pairing should
follow authenticated Human acceptance. Remote MCP and OIDC remain off until their
host/provider-specific redirect, token, revocation, and recovery flows pass.

## Controlled-experience release update (2026-08-24)

Release `67593b8` was the earlier controlled-experience baseline behind the HTTPS origin. Before cutover,
`/opt/agentpost/backups/20260824-0300-67593b8/` received a PostgreSQL custom dump,
attachment archive, root-only environment copy, systemd unit, and Nginx site.
The dump catalog and attachment archive both passed read checks. The pre-cutover
database contained 10 Agents, 8 Messages, and 8 Deliveries.

The release adds encrypted SMTP transport enforcement, durable HMAC-keyed fixed-
window limits for Human email/login and Pairing entry points, migration
`0018_rate_limit_buckets`, and the `agentpost-connect` zero-credential Connector
CLI. An isolated real-PostgreSQL database passed all five acceptance tests,
including 16-worker rate limiting, concurrent Pairing, restart durability,
idempotency, explicit lifecycle transitions, and 100-Agent concurrent sending.

After cutover, AgentPost, Nginx, and PostgreSQL remained active; origin and public
HTTPS health/readiness passed. A fresh production E2E sent while Bob had no client,
restarted AgentPost, then read, ACKed, replied, and verified a two-message Thread.
The public pinned wheel is available only at:

`https://agentpost.me/downloads/agentpost-0.1.0-py3-none-any.whl`

It returns `application/octet-stream`, does not enable directory listing, and its
SHA-256 is `1fc3f42e8c1141ce65481778587544fc9bf441438c852c0332594ab24a75fdf7`.
A clean virtual environment installed that exact HTTPS wheel with the Connector
extra and executed `agentpost-connect --help`; the OS-keyring dependency imported.

Alibaba Cloud DirectMail is now active with the verified sender
`no-reply@notify.agentpost.me`. Production uses SMTP over TLS on port 465; a
server-side authentication check passed without printing the credential. Human
self-service and Pairing are enabled. On 2026-08-24, verified-email open
registration was also enabled so a Human can create their own account from 星轨;
the durable per-IP and per-address challenge limits remain active. Remote MCP
OAuth and enterprise OIDC remain off.

The environment immediately before enabling open registration is preserved at
`/opt/agentpost/shared/agentpost.env.pre-open-registration-202608241203`. Public
health, readiness, authentication configuration, and the 星轨 registration UI
passed after restart. Delivery to a real recipient mailbox and the two-Human
experience are still acceptance gates, so the release is
`self_registration_ready`, not yet `two_human_experience_accepted`.

## Human-friendly Pairing guide update (2026-08-24)

Release `b7d51b0` replaces the low-level Pairing-first screen with a three-step
guide intended for a Human without programming experience: choose an Agent tool,
run two copyable commands on the local computer, then return to 星轨 to confirm
the device and Agent address. The guide provides separate Codex, WorkBuddy,
OpenClaw, and generic-tool entries, plus macOS, Windows, and Linux instructions.
It explains the local Connector and durable cloud Inbox in plain language and
moves Pairing ID/user-code fields behind an explicit advanced fallback.

The deployment was application-only: no schema, environment, DNS, Nginx, or
PostgreSQL change was required. Before cutover, the prior release pointer,
systemd unit, Nginx sites, and a root-only environment copy were stored under
`/opt/agentpost/backups/20260824-b7d51b0/`. The three changed UI files matched
their local SHA-256 hashes after transfer. A separate
`/opt/agentpost/venvs/b7d51b0` was built and the systemd unit now starts Alembic
and Uvicorn through that version's Python runtime.

After restart, AgentPost, Nginx, and PostgreSQL all reported `active`; local
health and readiness passed. A logged-in production Chrome session verified the
new empty state, all four tool choices, macOS and Windows instruction changes,
the Windows preview warning, and the manual Pairing fallback. No Pairing was
submitted and no long-term credential was exposed. This verifies the guidance
surface, not yet a real end-user Connector installation or native WorkBuddy/
OpenClaw host integration.

### Pairing 422 correction

The first real Codex Pairing attempt reached Human confirmation but the final
decision returned HTTP 422 when the address field did not match the protocol's
`local_agent_id` schema. Release `dda639e` fixes that usability failure without
loosening the protocol: `/api/v1/auth/config` now publishes the non-secret
managed Agent domain, 星轨 renders it as a fixed suffix, accepts only the local
address portion, and canonicalizes a same-domain full address. Chinese and ASCII
commas are both accepted for capability entry. Invalid address/capability values
are rejected before password confirmation, and safe schema-detail locations are
translated into actionable Chinese messages.

The prior release pointer, systemd unit, Nginx sites, and root-only environment
copy are under `/opt/agentpost/backups/20260824-dda639e/`. Local validation passed
306 fast tests with one sandbox-only skip and five deselections, plus nine MCP
adapter tests. Production file hashes matched, all three services stayed active,
and local/public health and readiness passed. The live authenticated page showed
the fixed `@agentpost.me` suffix and address guidance. The expired Connector
process was not restarted automatically; the Human must run the existing
connection command once to create a fresh short-lived Pairing.

## Natural-language Codex release 0.1.1 (2026-08-24)

Release `9f27d36` is deployed at `/opt/agentpost/releases/9f27d36` with an isolated
runtime at `/opt/agentpost/venvs/9f27d36`. Before cutover,
`/opt/agentpost/backups/20260824-172210-9f27d36/` received a PostgreSQL custom dump,
attachment archive, root-only environment copy, systemd unit, Nginx site, and the
previous release pointer. The database dump catalog and attachment archive both
passed read checks.

The public 0.1.1 wheel is pinned at
`https://agentpost.me/downloads/agentpost-0.1.1-py3-none-any.whl` with SHA-256
`908558e6c9c83401f5b2ca0ed0da645721d06789ed803b82c21be97b0c7b16b8`. The prior
0.1.0 wheel remains available for rollback. Production advertises Codex automatic
setup only for macOS; Windows and Linux gates remain closed.

The systemd unit and `/opt/agentpost/current` pointer now select `9f27d36`. After
restart, AgentPost, Nginx, and PostgreSQL remained active; local and public health
and readiness returned version 0.1.1; and PostgreSQL remained at
`0018_rate_limit_buckets`. An authenticated production Chrome session rendered the
existing Agent and all 星轨 observation areas, opened the 0.1.1 Codex guide with the
correct fixed hash, and reported no frontend errors.

This technical guide was later rejected as an ordinary-user experience and is retained only as
historical deployment evidence. Release `c7c7313` supersedes its default web entry with the uniform
chat prompt described below.

## Ordinary-user uniform prompt release (2026-08-25)

Release `c7c7313` is deployed at `/opt/agentpost/releases/c7c7313` with an isolated runtime at
`/opt/agentpost/venvs/c7c7313`. The immediate rollback is release `99f557f`; the pre-switch unit,
environment copy, and prior pointer evidence are under
`/opt/agentpost/backups/20260825-0938-c7c7313/`. This was an application-only change: database,
migration, Nginx, DNS, certificate, and PostgreSQL configuration were not changed.

The authenticated production 星轨 page now presents “连接新的 Agent”. Opening it shows one sentence:
“请连接我的星云驿。如果还没有连接，请帮我完成安装并打开授权页面；连接好后回到这里告诉我。”
The default path contains no Agent selector, operating-system selector, install command, connection
command, Pairing ID/code input, address input, or long-lived credential. The copy action changed to
“已复制” and displayed the next-step confirmation in the real Chrome session.

After cutover, AgentPost, Nginx, and PostgreSQL remained active; local and public health/readiness
passed; the public HTML contained the new sentence and excluded the rejected selector text. The
personal Codex marketplace plugin is installed and enabled as
`0.1.1+codex.20260825013544`. A new Codex task must still observe the complete first-use
install/authorization/return cycle. Mac Codex is the only currently open real-experience gate;
WorkBuddy, OpenClaw, Windows, and Linux remain pending and must not be reported as supported.

## Ordinary-user host-selection cold-start release (2026-08-25)

Release `8e7f105` is deployed at `/opt/agentpost/releases/8e7f105` with runtime
`/opt/agentpost/venvs/8e7f105`. The immediate application rollback is `c7c7313`; the pre-switch
environment, systemd unit, Nginx file, built wheel, and release evidence are under
`/opt/agentpost/backups/20260825-1033-8e7f105/`. There is no database migration in this release.

The production Connector metadata now pins 0.1.2 at
`https://agentpost.me/downloads/agentpost-0.1.2-py3-none-any.whl` with SHA-256
`29ab87057c214b283401732982b2fe85d620085e6ad98b04a306e49a466fcc99`. Nginx adds only that exact
wheel path to the existing download allowlist; unmatched `/downloads/` paths continue to return
404. The application exposes `/connect/codex`, `/connect/workbuddy`, `/connect/openclaw`, and the
same-origin `/connect/bootstrap.py`; the public bootstrap SHA-256 is
`bf94338e5e54842982ebe13d538e9fd59c43576df87078dff33af06678a2f6c4`.

After cutover, AgentPost, Nginx, and PostgreSQL were active; health/readiness, public metadata,
all three host contracts, bootstrap integrity, and public wheel integrity passed. The authenticated
real 星轨 page produced the correct one-block prompt for Codex, WorkBuddy, and OpenClaw. A fully
isolated local runtime with no AgentPost and no Codex config fetched the public bootstrap, installed
0.1.2, and reached one short-lived 星轨 authorization URL. It was stopped before approval to avoid
replacing the current sole production Connector. Tester-owned approval/return evidence and real
WorkBuddy/OpenClaw/Windows/Linux host evidence remain separate acceptance gates.

## Recipient-resolution release 0.1.3 (2026-08-25)

Release `6ada188` is deployed at `/opt/agentpost/releases/6ada188`; systemd runs Alembic and
Uvicorn through `/opt/agentpost/venvs/6ada188`. The production schema is
`0019_agent_handles`. The public immutable package is:

`https://agentpost.me/downloads/agentpost-0.1.3-py3-none-any.whl`

Its SHA-256 is `c157dbfd7dbdfd1697c9c85651455beec30e7679062aa9e9b91cea1fd0956757`.
The 0.1.2 wheel remains on the exact-path allowlist as the application rollback artifact; unknown
download paths still return 404.

Before mutation, the running release, service topology, loopback bindings, disk capacity, root-only
environment permissions, current wheel hash, and migration head were checked read-only. The
pre-cutover backup is `/opt/agentpost/backups/20260825-1210-5a5b509-pre-013/`; it contains a
PostgreSQL custom dump, attachment archive, protected environment, systemd unit, Nginx site, 0.1.2
wheel, pointer evidence, checksums, and `rollback-immediate-0.1.3.sh`. `pg_restore --list`, archive
listing, and every stored checksum passed. Counts before and after migration remained 16 Agents,
18 Messages, 18 Deliveries, and 0 Attachments.

A new provider snapshot named `agentpost-pre-0.1.3-20260825` was attempted but Alibaba Cloud
returned `SnapshotLimitExceed`. No existing snapshot was deleted to make room. The prior
`agentpost-pre-https-20260824`, `agentpost-pre-8f3bfd0-20260819`, and
`agentpost-baseline-20260813` snapshots remain available, but none is a point-in-time snapshot of
the 0.1.3 pre-cutover state; use the verified application/database backup for immediate rollback.

Before cutover, all five opt-in tests passed against a disposable real PostgreSQL database: complete
Alembic upgrade/downgrade, handle migration, concurrency/rate limits, Pairing and restart durability,
offline messaging, and the 100-Agent/idempotency case. After cutover, AgentPost, Nginx, and
PostgreSQL remained active; local and public health/readiness returned 0.1.3; the service journal
had zero errors from the cutover timestamp; HTTP redirected to HTTPS; and both the new and rollback
wheels matched their pinned hashes. A clean Python 3.12 environment installed the public 0.1.3
wheel and reported server, SDK, and MCP version 0.1.3.

An authenticated Chrome session confirmed that 星轨 preserved the existing Agent and messages,
showed the friendly short-name guidance and editor, and kept the immutable address behind “查看底层
身份”. No handle or message was changed during this production UI check. The real Zhang Ziliang/
`kcode`, same-name Human, multiple-Codex, not-found, legacy-address, and rename-continuity sends
remain tester-owned acceptance cases. This release is
`recipient_resolution_deployed_https_verified`, not `production_accepted`.

## Rollback

The provider snapshot `agentpost-pre-https-20260824`
(`s-bp15au6if7ffxt547ltn`) is the full-machine rollback point from immediately
before DNS/HTTPS activation. The older snapshot
`agentpost-pre-8f3bfd0-20260819` and the original deployment baseline
`agentpost-baseline-20260813` both remain available. Use
snapshot rollback only after capturing any post-deployment PostgreSQL and
attachment data that must be kept.

The HTTPS application backup is under `/opt/agentpost/backups/20260824-https/`:
the working Nginx site, a PostgreSQL custom-format dump, an attachment archive,
and a root-only copy of the environment file. Restore the Nginx backup and reload
Nginx for an HTTPS-only rollback; restore the protected environment backup and
restart only AgentPost if the public-base change must be reverted.

Application backups for this update are under
`/opt/agentpost/backups/20260819-0820/`: a PostgreSQL custom-format dump and an
attachment archive. The pre-update systemd unit is stored at
`/etc/systemd/system/agentpost.service.pre-8f3bfd0`.

The current rollback backup is
`/opt/agentpost/backups/20260825-1210-5a5b509-pre-013/`. For an immediate 0.1.3 rollback before
new handles have been written, review and run `rollback-immediate-0.1.3.sh` with its required
`CONFIRM_IMMEDIATE_ROLLBACK=YES` guard. It stops only AgentPost, downgrades migration 0019 to 0018,
restores the protected environment, service unit, Nginx site and 0.1.2 release, then validates
readiness. If any 0.1.3 handles or subsequent data must be preserved, do not use the immediate
downgrade blindly: capture a new dump and plan a data-preserving rollback or restore first.

For an application-only incident:

1. stop AgentPost, leaving PostgreSQL running;
2. select the prior release under `/opt/agentpost/releases`;
3. restore the prior service package/config if the runtime was updated;
4. start AgentPost;
5. run `/health`, `/ready`, and the offline message smoke test;
6. inspect the journal before reopening traffic.

Do not delete PostgreSQL data, attachment storage, the shared environment file,
or the baseline snapshot as part of an ordinary application rollback.

## Domain, ICP, and HTTPS result

The user-controlled ICP filing was approved and verified in the Alibaba Cloud
console. The pre-change DNS zone contained no records. A single root A record was
added for `agentpost.me` to `112.124.33.54`; no unnecessary `www` record was
created. Alibaba Public DNS and the server resolver independently returned that
address.

Before mutation, the working Nginx configuration, PostgreSQL database,
attachments, and protected environment were backed up and a provider snapshot
completed. Nginx was then bound to the exact hostname, the certificate was issued,
port 80 was redirected to HTTPS, and the public base URL was changed to
`https://agentpost.me`. Nginx syntax, the certificate SAN/issuer/validity,
automatic renewal, `/health`, `/ready`, `/orbit`, and the complete offline
send/restart/read/ACK/reply/thread scenario all passed. AgentPost and PostgreSQL
remain loopback-only behind Nginx.

## Remaining production work

- automated encrypted PostgreSQL and attachment backups with restore drills
- monitoring and alerts for readiness, disk, memory, database, and certificate
- API rate limits and per-Agent quotas
- API-key rotation/revocation workflow
- attachment malware scanning/quarantine hook
- retention/expiration cleanup
- a maintained release installer that reproduces the systemd/Nginx fallback
- supported OpenClaw-host validation

Until these operational and product gates are complete, label the result
`deployed_https_verified`, not `production_accepted`.

## 2026-08-24 HTTPS acceptance evidence

- `agentpost.me` resolved to `112.124.33.54` through both the server resolver and
  Alibaba Public DNS.
- Nginx configuration validation passed; AgentPost, Nginx, and PostgreSQL all
  reported `active` after the public-base restart.
- `http://agentpost.me/orbit` returned HTTP 301 to
  `https://agentpost.me/orbit`; HTTPS `/health`, `/ready`, and `/orbit` passed.
- The certificate SAN is exactly `agentpost.me`, its issuer is Let's Encrypt YE1,
  and simulated automatic renewal passed.
- A new HTTPS E2E created isolated Alice/Bob identities, sent while Bob had no
  client, restarted AgentPost, retrieved the persisted unread message, marked it
  read, ACKed it, replied, exposed the ACK to Alice, and returned two messages in
  the thread.
- Chrome rendered the public 星云驿/星轨 shell at the HTTPS URL. No Human, Agent,
  Admin, pairing, OAuth, or IdP credential was entered during browser acceptance.

## 2026-08-19 acceptance evidence

The first upgrade attempt exposed a PostgreSQL-only Alembic bookkeeping limit:
`alembic_version.version_num` was `VARCHAR(32)`, shorter than revision
`0013_organization_self_governance`. Transactional DDL rolled the schema back to
`0005_access_control`; the application unit and release symlink were restored,
and all three services returned to `active` before proceeding.

Commit `9f39342` widens that column to 128 before Alembic records revision 0013
and adds a real-PostgreSQL regression assertion. Local validation passed 292
fast tests (one sandbox-only loopback skip; four PostgreSQL tests deselected) and
eight MCP adapter tests. The second cloud upgrade reached
`0017_enterprise_oidc`, confirmed `version_column=128`, and retained the exact
pre-upgrade counts of four Agents, two Messages, two Deliveries, and zero
Attachments.

Cloud acceptance then created isolated deployment-test Alice and Bob identities.
Alice sent while no Bob client was running; the AgentPost service restarted; Bob
retrieved the unread message, marked it read, ACKed it, and replied; Alice saw
the ACK and reply; and the thread contained exactly two messages. Public-IP
`/health`, `/ready`, and `/orbit` returned HTTP 200 after that restart. Only SSH
and Nginx HTTP are public; AgentPost and PostgreSQL remain bound to loopback.
