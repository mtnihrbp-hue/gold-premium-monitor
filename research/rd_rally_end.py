"""When does a rally end? Conditional survival of 8%-ZigZag rallies (SP-D research, SP_D_HANDOFF.md section 4)."""
import json, os
from datetime import date
from statistics import median
import rd_legs as z   # reuses the ZigZag
legs = z.zigzag(0.08)
c, d = z.c, z.d
done = [(a, b) for k, a, b in legs[:-1] if k == "rally" and d[a].year >= 2013]
k, a0, b0 = legs[-1]
age, gain = len(c) - 1 - a0, (c[-1] / c[a0] - 1) * 100
print(f"current rally: {d[a0]} at {c[a0]/1e7:.2f} M, {age} trading days, {gain:+.1f}%; peak {max(c[a0:])/1e7:.2f} M")
print(f"rally-end line (8% below the peak): {max(c[a0:]) * 0.92 / 1e7:.2f} M  = {(max(c[a0:]) * 0.92 / c[-1] - 1) * 100:+.1f}% from the last close")
print(f"\ncompleted rallies since 2013: {len(done)}")
for label, cond in (("lasted at least as long", lambda a, b: b - a >= age),
                    ("gained at least as much", lambda a, b: (c[b] / c[a] - 1) * 100 >= gain),
                    ("both", lambda a, b: b - a >= age and (c[b] / c[a] - 1) * 100 >= gain)):
    sel = [(a, b) for a, b in done if cond(a, b)]
    if not sel:
        print(f"  {label}: none"); continue
    more_days = [b - a - age for a, b in sel]
    final_gain = [(c[b] / c[a] - 1) * 100 for a, b in sel]
    print(f"  {label}: {len(sel)} rallies; they lasted {min(more_days)}..{max(more_days)} more days (median {median(more_days):.0f}); "
          f"final gain median {median(final_gain):+.0f}% (range {min(final_gain):+.0f}..{max(final_gain):+.0f}%)")
    for a, b in sel:
        print(f"     {d[a]} -> {d[b]}: {b - a:4} days, {(c[b] / c[a] - 1) * 100:+5.0f}%")
lengths = sorted(b - a for a, b in done)
print(f"\nall rallies: {sum(1 for x in lengths if x > age)} of {len(lengths)} lasted longer than {age} days")
