import os
from datetime import datetime

import resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_TO = os.environ.get("EMAIL_TO")


def _send(subject: str, html: str):
    if not RESEND_API_KEY:
        print("EMAIL SKIP: RESEND_API_KEY not set")
        return
    if not EMAIL_TO:
        print("EMAIL SKIP: EMAIL_TO not set")
        return

    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send(
            {
                "from": "Gold Premium Monitor <onboarding@resend.dev>",
                "to": [EMAIL_TO],
                "subject": subject,
                "html": html,
            }
        )
        print(f"EMAIL OK: sent to {EMAIL_TO}")
    except Exception as e:
        print(f"EMAIL ERROR: {e}")


def _market_rows(markets):
    rows = ""
    for name, info in markets.items():
        if info["status"] != "OK":
            continue
        rows += f"""
<tr>
<td style="padding:6px;border-bottom:1px solid #ddd;">
{name}
</td>
<td style="padding:6px;border-bottom:1px solid #ddd;text-align:right;">
{info["price"]:,.0f}
</td>
</tr>
"""
    return rows


def _trend_block_html(trends):
    """Optional trend block for email HTML."""
    if not trends:
        return ""

    lines = []
    arrow = trends.get("arrow", "→")
    diff = trends.get("arrow_diff")
    ma7 = trends.get("ma7")

    if diff is not None:
        lines.append(f"3-Day Trend: {arrow} ({diff:+.2f}%)")
    if ma7 is not None:
        lines.append(f"7-Day MA: {ma7:.2f}%")

    if not lines:
        return ""

    return "<p><b>Trends:</b> " + " | ".join(lines) + "</p>"


def send_daily_recap(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
):
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:650px;">

<h2>Daily Gold Premium Report</h2>

<table style="border-collapse:collapse;width:100%;">
<tr>
<th align="left">Platform</th>
<th align="right">Price</th>
</tr>

{_market_rows(markets)}

<tr>
<td><b>Fair Price</b></td>
<td align="right"><b>{fair:,.0f}</b></td>
</tr>

</table>

<p><b>Lowest:</b> {lowest:,.0f}</p>

<p><b>Premium:</b> {premium:.2f}%</p>

{_trend_block_html(trends)}

<p><b>World Gold:</b> {world:.2f} USD/oz</p>

<p><b>USD:</b> {usd:,} IRR</p>

<hr>

<p>
Generated:
{datetime.now().strftime("%Y-%m-%d %H:%M")}
</p>

</div>
"""

    _send(
        "Daily Gold Premium Report",
        html,
    )


def send_alert(
    signal,
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
):
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:650px;">

<h2>{signal["signal"]} ALERT</h2>

<p>
<b>
{signal["reason"]}
</b>
</p>

<table style="border-collapse:collapse;width:100%;">

<tr>
<th align="left">Platform</th>
<th align="right">Price</th>
</tr>

{_market_rows(markets)}

<tr>
<td><b>Fair Price</b></td>
<td align="right"><b>{fair:,.0f}</b></td>
</tr>

</table>

<p><b>Lowest:</b> {lowest:,.0f}</p>

<p><b>Premium:</b> {premium:.2f}%</p>

{_trend_block_html(trends)}

<p><b>World Gold:</b> {world:.2f} USD/oz</p>

<p><b>USD:</b> {usd:,} IRR</p>

<hr>

<p>
Generated:
{datetime.now().strftime("%Y-%m-%d %H:%M")}
</p>

</div>
"""

    _send(
        f"{signal['signal']} Gold Alert",
        html,
    )
