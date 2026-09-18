# Ultron Solo Backend

This gateway gives the Android app one simple endpoint while keeping the
OpenAI API key off the phone.

## Required secrets

- `OPENAI_API_KEY`: server-side OpenAI Platform key
- `ULTRON_CLIENT_TOKEN`: a long random password used only by the APK
- `OPENAI_MODEL`: defaults to `gpt-5-mini`

Deploy the repository using `render.yaml`, or build the included Dockerfile.
After deployment, enter the HTTPS service URL and `ULTRON_CLIENT_TOKEN` in the
Ultron Companion app. Never put `OPENAI_API_KEY` into the APK.

For local testing:

```bash
export OPENAI_API_KEY="..."
export ULTRON_CLIENT_TOKEN="..."
python app.py
```

The backend accepts `POST /v1/chat` with a `messages` array and returns
`{"reply":"..."}`. It limits request size, conversation length, and requests
per minute. OpenAI Responses are requested with storage disabled.

