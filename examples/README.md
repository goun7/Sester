# Examples

## FastAPI

This example shows how to protect a FastAPI application with `SesterMeter`.

Install the demo dependencies:

```bash
pip install "sester[demo]"
```

Run the example:

```bash
uvicorn examples.fastapi_demo:app
```

Then call:

```bash
curl http://127.0.0.1:8000/weather
```

Without a valid payment envelope, Sester returns `402 Payment Required`.

With a valid payment envelope, the request reaches the FastAPI route and returns a `200` response.

The example uses a request price of `0.05` and a daily quota of `0.25`, so five paid requests are allowed and the sixth is rejected with `quota_exceeded`.
