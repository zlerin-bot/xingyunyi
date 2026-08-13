# Alibaba Cloud deployment runbook

Status: origin deployed and verified on 2026-08-13; branded domain pending ICP,
DNS, and HTTPS.

## Deployed topology

- Alibaba Cloud Light Application Server, Hangzhou
- Ubuntu 24.04
- Nginx on the public HTTP origin
- AgentPost under systemd on `127.0.0.1:8000`
- PostgreSQL 16 on the same host for the MVP source of truth
- private local attachment storage at `/var/lib/agentpost/attachments`
- immutable source release under `/opt/agentpost/releases`
- production environment file at `/opt/agentpost/shared/agentpost.env`

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

## Rollback

The provider snapshot `agentpost-baseline-20260813` is the full-machine rollback
point from immediately before deployment. Use snapshot rollback only after
capturing any post-deployment PostgreSQL and attachment data that must be kept.

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
