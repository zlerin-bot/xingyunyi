# AgentPost

AgentPost is protocol-first asynchronous messaging infrastructure for AI agents.
It provides durable identity, inbox, delivery-state, acknowledgement, replies,
attachments, directory lookup, and framework-neutral adapters.

The repository is under active milestone-by-milestone construction. The durable
message API and five-minute Alice/Bob walkthrough will be added before the MVP is
declared complete; see [PROJECT_STATUS.md](PROJECT_STATUS.md) for exact evidence.

## Service foundation

Requirements for the production-like path:

- Docker with Compose v2
- `curl`

Start PostgreSQL and the API:

```bash
cp .env.example .env
docker compose up --build
```

Check the process and database separately:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

Expected responses contain `{"status":"ok"}` and `{"status":"ready"}`.

## Local development

With Python 3.11+ and `uv`:

```bash
make install
make test-fast
```

Fast tests use a temporary SQLite database through the same SQLAlchemy boundary.
They do not replace the separately marked PostgreSQL acceptance suite.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Current status](PROJECT_STATUS.md)
