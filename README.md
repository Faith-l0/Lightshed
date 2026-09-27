# LightShed

A distributed loadshedding information system. Independent services, communicating over HTTP
and (from Iteration 3) a RabbitMQ message queue.

## Status
- [x] Iteration 1: Place-name service (data cleaning + validation API)
- [ ] Iteration 2: Stage service, Schedule service
- [ ] Iteration 3: Error handling, panic alerts, message queue
- [ ] Iteration 4: AlertBot

## Run it

With Docker:

    docker compose up --build
    curl "localhost:8001/places/validate?town=cape%20town"

Without Docker:

    cd place-service
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest
    uvicorn app.main:app --reload --port 8001

## Place-name service contract

`GET /places/validate?town=<town>&province=<optional>`

| Outcome            | HTTP | Body                                                       |
|--------------------|------|------------------------------------------------------------|
| valid              | 200  | `{"status":"valid","town":"Cape Town","province":"Western Cape"}` |
| not found          | 404  | `{"status":"not_found","town":"...","suggestions":[...]}`  |
| ambiguous          | 409  | `{"status":"ambiguous","town":"Newlands","provinces":[...]}` |
| unknown province   | 422  | `{"status":"invalid_province","province":"..."}`           |

Other endpoints: `GET /health`, `GET /places?province=`.

## Cleaning rules (see `place-service/app/cleaning.py`)
- Trim, collapse whitespace, normalise casing
- Province aliases and abbreviations mapped to canonical names (WC, W Cape, KZN, ...)
- Duplicates across spellings collapse into one record
- Same town in different provinces is kept (and reported as ambiguous when no province is given)
- Rows with a missing town/province, unknown province, or digits in the town are rejected and logged with a reason

## Design decisions to record for the write-up
- Each service owns its own data; no shared database.
- Status codes are part of the contract; the Schedule service will depend on them.
- Rejected rows are logged, not silently dropped.
