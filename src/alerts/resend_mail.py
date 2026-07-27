import os
from datetime import datetime

import resend

resend.api_key = os.environ["RESEND_API_KEY"]

EMAIL_TO = os.environ["EMAIL_TO"]


def _send(subject: str, html: str):

    resend.Emails.send(
        {
            "from": "Gold Premium Monitor <onboarding@resend.dev>",
            "to": [EMAIL_TO],
            "subject": subject,
            "html": html,
        }
    )


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


def send_daily_recap(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
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

<p><b>World Gold:</b> {world:.2f}</p>

<p><b>USD:</b> {usd:,}</p>

</div>
"""

    _send(
        f"{signal['signal']} Gold Alert",
        html,
    )
