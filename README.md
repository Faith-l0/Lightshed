# LightShed

A distributed loadshedding information system. Independent services, communicating over HTTP
and, from this iteration onward, a RabbitMQ message queue.

## Status
- [x] Iteration 1: Place-name service (data cleaning + validation API)
- [x] Iteration 2: Stage service, Schedule service (inter-service HTTP calls)
- [x] Iteration 3: Retries, `service.failed` / `stage.changed` events, Monitor + panic alerts
- [ ] Iteration 4: AlertBot

## Services

| Service           | Port | Role                                                              |
|-------------------|------|--------------------------------------------------------------------|
| place-service      | 8001 | Cleans and validates town/province data                           |
| stage-service       | 8002 | Holds/updates the current loadshedding stage                      |
| schedule-service    | 8003 | Returns a schedule for a town; calls place-service + stage-service |
| monitor            | 8004 | Consumes `service.failed` events, raises `panic.alert` on bursts  |
| rabbitmq           | 5672 (AMQP), 15672 (management UI, guest/guest) | Message broker |

## Run it

    docker compose up --build

Try it end to end:

    curl "localhost:8001/places/validate?town=cape%20town"
    curl "localhost:8003/schedule?town=cape+town"
    curl -X PUT localhost:8002/stage -H "Content-Type: application/json" -d '{"stage": 4}'
    curl localhost:8004/failures   # Monitor's view of recent service failures
    curl localhost:8004/alerts     # Any panic alerts raised so far

Without Docker, each service has its own venv:

    cd <service-name>
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest
    uvicorn app.main:app --reload --port <its port>

## Message queue design

One topic exchange, `lightshed`, with these routing keys so far:

| Routing key      | Published by      | Consumed by         |
|-------------------|-------------------|----------------------|
| `stage.changed`   | stage-service      | (Iteration 4: alert-bot) |
| `service.failed`  | schedule-service   | monitor              |
| `panic.alert`     | monitor            | (Iteration 4: alert-bot) |

**Fault tolerance decisions:**
- Publishing an event is fire-and-forget: if RabbitMQ is down, the publishing
  service logs a warning and carries on — a broker outage never turns into a
  failed HTTP request for the person calling the API.
- Schedule retries its calls to place-service and stage-service with
  exponential backoff (`app/retry.py`) before giving up.
- If place-service still fails after retries, schedule-service returns 503
  (it can't guess whether a town is valid) and reports the failure.
- If stage-service still fails after retries, schedule-service falls back to
  stage 0 and still answers — not knowing the current stage doesn't have to
  block the response — but it still reports the failure so Monitor sees it.
- Every consumer queue is bound with a dead-letter exchange (`lightshed.dlx`
  → `lightshed.dlq`), so a message that can't be processed lands somewhere
  inspectable instead of looping forever or vanishing.
- Monitor raises a `panic.alert` when a service fails 3+ times within 60
  seconds (`monitor/app/panic.py` — pure logic, unit tested without a broker).

## Place-name service contract

`GET /places/validate?town=<town>&province=<optional>`

| Outcome            | HTTP | Body                                                       |
|--------------------|------|--------------------------------------------------------------------|
| valid              | 200  | `{"status":"valid","town":"Cape Town","province":"Western Cape"}` |
| not found          | 404  | `{"status":"not_found","town":"...","suggestions":[...]}`  |
| ambiguous          | 409  | `{"status":"ambiguous","town":"Newlands","provinces":[...]}` |
| unknown province   | 422  | `{"status":"invalid_province","province":"..."}`           |

## Design decisions to record for the write-up
- Each service owns its own data; no shared database.
- HTTP status codes are part of the contract between services, not an afterthought.
- Rejected data rows are logged with a reason, not silently dropped.
- Degrade gracefully vs. fail loudly is a deliberate per-dependency choice
  (see the Schedule service section above), not a blanket policy.

## Known gaps / things to finish before submission
- `place-service/data/raw_places.csv` is a small placeholder dataset — swap
  in the real one from your course and re-check the cleaning rules against it.
- No AlertBot yet (Iteration 4).
