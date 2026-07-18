import json
import subprocess


def get_usd_sell_rate() -> int:
    result = subprocess.run(
        ["python", "-m", "bonbast", "export"],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)

    usd = data["currencies"]["USD"]

    return int(usd["sell"])
