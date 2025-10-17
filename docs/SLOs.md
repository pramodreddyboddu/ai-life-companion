# Service Level Objectives

These SLOs define the target reliability for the AI Companion production environment. They support user expectations around reminders, chat responsiveness, and platform availability.

## 1. Availability
- **Target:** 99.5% monthly uptime for the `/healthz` endpoint and chat API.
- **Measurement:** Synthetic checks hitting `/healthz` every minute.
- **Error Budget:** 0.5% downtime (~3.6 hours per month).
  - Breach if downtime exceeds budget or four consecutive failed checks.

## 2. Reminder Delivery Latency
- **Target:** P95 reminder delivery within 2 minutes of the scheduled `run_ts`.
- **Measurement:** `reminder_fired` metrics (UTC timestamp difference between `run_ts` and `sent_at`).
- **Error Budget:** 5% of reminders may exceed 2 minutes (soft budget). If >5% exceed, freeze feature launches and investigate.

## 3. Chat Success Rate
- **Target:** 99% of `/chat` requests succeed (HTTP 2xx) excluding client errors.
- **Measurement:** Ingested via API logs / metrics counters.
- **Error Budget:** 1% failure window. Chronic 5xx errors trigger incident response.

## Error Budget Policy
- Exhausting any monthly error budget triggers:
  1. Immediate incident review and postmortem.
  2. Freeze on non-critical production changes until mitigations are deployed.
  3. Additional on-call support to track regression mitigations.

## On-call Expectations
- Coverage: one engineer primary, one secondary (follow published rotation).
- Response Time: acknowledge Sev-1 pages within 5 minutes, Sev-2 within 15 minutes.
- Availability Window: 08:00–22:00 local time (pager duty outside window by rotation agreement).
- Handoff: ensure open incidents + known issues are documented prior to shift change.

## Reporting
- Weekly SLO report summarizing availability, reminder latency, and significant incidents.
- Quarterly review of SLO targets with product/leadership.
