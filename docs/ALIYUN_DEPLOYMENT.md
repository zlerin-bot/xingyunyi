# Alibaba Cloud deployment runbook

Status: current release deployed and HTTPS-verified on 2026-08-24 at
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

The active application release is Git commit `67593b8` at
`/opt/agentpost/releases/67593b8`, with its independent Python environment at
`/opt/agentpost/venvs/67593b8`. The database is at Alembic revision
`0018_rate_limit_buckets`.

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

Release `67593b8` is deployed behind the existing HTTPS origin. Before cutover,
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

Human self-service and Pairing remain off until the user activates a production
mail provider and its sender is verified. Open registration, Remote MCP OAuth,
and enterprise OIDC remain off. This release is therefore
`deployed_controlled_experience_ready`, not yet `two_human_experience_accepted`.

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

The current application-only rollback backup is
`/opt/agentpost/backups/20260824-0300-67593b8/`. Because release `9f39342` does
not know revision `0018`, first use the `67593b8` environment to downgrade the
database to `0017_enterprise_oidc`, then restore the prior current-release symlink
and systemd unit. Verify counts and `/ready` before reopening traffic.

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
