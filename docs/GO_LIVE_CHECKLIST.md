# Go-Live Checklist

## Before Deploy
- [ ] Confirm staging and production environments are configured (`api/.env`, feature flags).
- [ ] Database migrations have been applied (`alembic upgrade head`).
- [ ] `/healthz` returns `db: ok`, `redis: ok`, `celery: ok`.
- [ ] `/metrics` shows reminder counters and worker uptime increasing.
- [ ] `./scripts/smoke.sh` passes in staging.
- [ ] Backup verification: latest pg_dump + Redis snapshot restored in staging (`docs/BACKUP_RESTORE.md`).
- [ ] Admin dashboard shows healthy queues/workers.
- [ ] Feature flags set appropriately (Voice, Calendar, Multi-channel).
- [ ] On-call schedule updated; incident channel monitored.

## Rollout Plan
1. **Canary 10%**
   - Deploy to 10% of traffic / single instance.
   - Monitor `/metrics`, logs, admin dashboard for 30 minutes.
   - Rollback: redeploy previous Docker image (Render Manual Deploy) if errors spike.
2. **Scale to 50%**
   - Increase traffic allocation to 50% or add nodes.
   - Re-run smoke tests.
3. **Scale to 100%**
   - Full deployment once metrics stable.

## Rollback Strategy
- Keep previous image tag ready.
- Use Render Manual Deploy to revert; confirm rollback via `/healthz` and smoke test.
- Restore DB/Redis from latest backup if data corruption suspected.

## Post-Deployment
- [ ] Verify reminders fire and calendar sync works end-to-end.
- [ ] Confirm `/admin` observability data.
- [ ] Send release notes to stakeholders.
- [ ] Schedule retro if incidents occurred.
