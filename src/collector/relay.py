"""The data relay (SP-D, SP_D_HANDOFF.md section 10): a route for the Iranian sources that
GitHub's runner cannot reach (Daric answers it 403, TSETMC refuses the connection).

`get_json(url)` tries the source directly; if that is refused or times out and a relay is
configured (RELAY_URL and RELAY_TOKEN, GitHub secrets), it asks the relay -- a Cloudflare
Worker, src/worker/data-relay.js -- to fetch it instead. Without a relay it raises as the
direct call did, so a collector fails exactly as before.
"""

import os
from urllib.parse import quote

import requests

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def configured():
    return bool(os.environ.get("RELAY_URL") and os.environ.get("RELAY_TOKEN"))


def via_relay(url, timeout=(4, 10)):           # inside the collectors' 20 s global timeout
    response = requests.get(f"{os.environ['RELAY_URL'].rstrip('/')}/?url={quote(url, safe='')}",
                            headers={**UA, "X-Relay-Token": os.environ["RELAY_TOKEN"]}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_json(url, timeout=(5, 15)):
    try:
        response = requests.get(url, headers=UA, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        if not configured():
            raise
        return via_relay(url)
