import subprocess


def get_usd_sell_rate():
    result = subprocess.run(
        ["python", "-m", "bonbast", "export"],
        capture_output=True,
        text=True,
        check=True,
    )

    print(result.stdout)

    raise RuntimeError("STOP")
