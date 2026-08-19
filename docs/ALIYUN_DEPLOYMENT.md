# Alibaba Cloud deployment runbook

Status: current release deployed and origin-verified on 2026-08-19; branded
domain pending ICP, DNS, and HTTPS.

## Deployed topology

- Alibaba Cloud Light Application Server, Hangzhou
- Ubuntu 24.04
- Nginx on the public HTTP origin
- AgentPost under systemd on `127.0.0.1:8000`
- PostgreSQL 16 on the same host for the MVP source of truth
- private local attachment storage at `/var/lib/agentpost/attachments`
- immutable source release under `/opt/agentpost/releases`
- production environment file at `/opt/agentpost/shared/agentpost.env`

The active application release is Git commit `9f39342` at
`/opt/agentpost/releases/9f39342`, with its independent Python environment at
`/opt/agentpost/venvs/9f39342`. The database is at Alembic revision
`0017_enterprise_oidc`.

The environment file is root-readable only. Do not copy it into Git, command
output, tickets, or chat. API keys remain one-time registration results and must
not be stored in this runbook.

## Service checks

Run on the server without printing the environment file:

```bash
systemctl is-active agentpost nginx postgresql
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
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

This is origin deployment evidence. It is not evidence that DNS, TLS, ICP,
backups, alerting, or multi-node recovery have been accepted.

## 星轨 and onboarding deployment boundary

The 2026-08-19 update deployed the Human control plane, organization governance,
pairing/Connector data model, credential lifecycle, Remote MCP OAuth adapter,
and enterprise OIDC schema through revision `0017_enterprise_oidc`. Independent
server-only secrets were added to the root-protected environment file without
printing their values.

The public `/orbit` shell is reachable through the IP origin for rendering and
diagnostics. It is **not** an accepted public login origin. Until a trusted HTTPS
hostname is available, these production feature flags remain disabled:

- Human self-service and open registration
- pairing and Connector authorization
- Remote MCP OAuth Device Authorization
- enterprise OIDC

The existing controlled Admin surface remains configured and requires its Admin
token for operational data/actions; loading its HTML shell does not grant data
access. Never enter a `hum_`, `agt_`, Admin, pairing, OAuth, or IdP credential
through the plaintext public IP.

After HTTPS is accepted, enable features one at a time, beginning with Human
authentication, then pairing, then Remote MCP/OIDC only after their provider-
specific redirect and token flows pass acceptance. Secure browser cookies cannot
be accepted through the current plaintext IP.

## Rollback

The provider snapshot `agentpost-pre-8f3bfd0-20260819`
(`s-bp14483a88wkwkpj47wd`) is the full-machine rollback point from immediately
before the current-stage update. The older snapshot
`agentpost-baseline-20260813` remains the original deployment baseline. Use
snapshot rollback only after capturing any post-deployment PostgreSQL and
attachment data that must be kept.

Application backups for this update are under
`/opt/agentpost/backups/20260819-0820/`: a PostgreSQL custom-format dump and an
attachment archive. The pre-update systemd unit is stored at
`/etc/systemd/system/agentpost.service.pre-8f3bfd0`.

For an application-only incident:

1. stop AgentPost, leaving PostgreSQL running;
2. select the prior release under `/opt/agentpost/releases`;
3. restore the prior service package/config if the runtime was updated;
4. start AgentPost;
5. run `/health`, `/ready`, and the offline message smoke test;
6. inspect the journal before reopening traffic.

Do not delete PostgreSQL data, attachment storage, the shared environment file,
or the baseline snapshot as part of an ordinary application rollback.

## Domain, ICP, and HTTPS gate

The current origin is in mainland China. Do not point `agentpost.me` at it or
request a public certificate until the domain registration review and ICP filing
steps are complete. Filing submission, identity verification, CAPTCHA, agreement
acceptance, and payment remain user-controlled actions.

After ICP approval:

1. record existing DNS before changing it;
2. add only the required A/AAAA records;
3. verify authoritative and client-visible resolution independently;
4. back up the working Nginx HTTP configuration;
5. issue a certificate for the exact hostname;
6. enable HTTP-to-HTTPS redirect;
7. verify hostname, certificate chain, expiry, `/health`, `/ready`, and the full
   Alice/Bob offline flow from outside the server;
8. recheck that PostgreSQL and attachment ports are not public.

## Remaining production work

- automated encrypted PostgreSQL and attachment backups with restore drills
- monitoring and alerts for readiness, disk, memory, database, and certificate
- API rate limits and per-Agent quotas
- API-key rotation/revocation workflow
- attachment malware scanning/quarantine hook
- retention/expiration cleanup
- a maintained release installer that reproduces the systemd/Nginx fallback
- supported OpenClaw-host validation

Until these and the domain gate are complete, label the result
`deployed_origin_verified`, not `production_accepted`.

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
