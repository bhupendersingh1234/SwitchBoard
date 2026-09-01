## M0

- Engine owns the connection pool.
- Sessionmaker creates one Session per request.
- Lifespan initializes and cleans shared resources.
- /health checks app liveness; /readyz checks dependencies.
- Alembic provides versioned database migrations.