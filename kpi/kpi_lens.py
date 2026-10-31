"""KPI -- the nightly LENS (SP_D_HANDOFF.md sections 84-86).

The owner, 2026-10-30: "the system lens HAVE to see all these, and provide a valid analysis"; on the preview of
2026-10-31, the AI model's part "1-approved. 2-go ahead".

Load-bearing properties:
- the ceasefire's odds are Polymarket's ladder, soonest first; a failed read is an empty list, never a raise;
- the headline filter is the research labelling's, character for character (that script is frozen for E-9);
- the model only picks and translates: a pick outside the headlines, on both sides, beyond three a side, or a
  translation carrying a number its headline does not carry is dropped; an unreadable reply, no key or a spent
  daily quota leaves the news out;
- the translation keeps who says it and a condition as a condition (9 Aban's three rounds, SP-D 87);
- the channels are paged back from their oldest message, text or not: a page of photos alone is not the end;
- the case summary is computed from the seed, never written by hand;
- every number the message prints is computed in analysis/lens.py; the message formats;
- the read's flags come from the numbers, never from the model;
- the message keeps Persian dates, its four blocks and the last line, and fits Telegram at its longest;
- it goes once per Tehran day from 21:00, behind config.lens.send, needs no database, and never raises.

No test here reaches the network: every fetcher and the transport are substituted (kpi_coherence.test_27).
"""

import json
import os
import re
import sys
import unittest
from datetime import date, datetime

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "research"))

import collector.polymarket as polymarket  # noqa: E402
from alerts import telegram_lens  # noqa: E402
from analysis import cases, lens  # noqa: E402
from intelligence import news_lens  # noqa: E402

LADDER = [{"question": "US x Iran ceasefire continues through November 8?", "endDate": "2026-11-09T00:00:00Z",
           "outcomePrices": "[\"0.71\", \"0.29\"]", "volume": "900000"},
          {"question": "US x Iran ceasefire continues through November 2?", "endDate": "2026-11-03T00:00:00Z",
           "outcomePrices": "[\"0.916\", \"0.084\"]", "volume": "200000"},
          {"question": "US x Iran ceasefire continues through October 28?", "endDate": "2026-10-29T00:00:00Z",
           "outcomePrices": "[\"0.99\", \"0.01\"]", "volume": "1"},
          {"question": "US x Iran ceasefire continues through the midterms?", "endDate": "2026-11-04T00:00:00Z",
           "outcomePrices": "[\"0.89\", \"0.11\"]", "volume": "1"},
          {"question": "Will the Iranian regime fall before 2027?", "endDate": "2027-01-01T00:00:00Z",
           "outcomePrices": "[\"0.05\", \"0.95\"]", "volume": "1"},
          {"question": "US x Iran ceasefire continues through November 20?", "endDate": "2026-11-21T00:00:00Z",
           "outcomePrices": "not json", "volume": "1"}]
HEADS = ["فعالیت بی سابقه آمریکا در نزدیکی مرز و ۸۰ فروند تانکر سوخت‌رسان در اسرائیل",
         "مذاکره‌کنندگان قطری ۱۲ ساعت است که در تهران هستند و مذاکرات ادامه دارد",
         "ترامپ: مذاکراتی در جریان است؛ آن‌ها می‌خواهند مذاکره کنند",
         "قیمت نفت برنت از ۱۱۸ دلار عبور کرد"]


def candles():
    return {"geram18": [{"date": "2026-10-31", "close": 256_000_000.0}, {"date": "2026-10-29", "close": 262_235_000.0},
                        {"date": "2026-10-28", "close": 264_084_000.0}],
            "ons": [{"date": "2026-10-30", "close": 3879.28}, {"date": "2026-10-29", "close": 4025.06}],
            "price_dollar_rl": [{"date": "2026-10-29", "close": 2_710_600.0}],
            "crypto-tether-irr": [{"date": "2026-10-30", "close": 2_732_450.0}, {"date": "2026-10-29", "close": 2_712_620.0}],
            "tether_history": [{"date": "2026-10-22", "close": 2_717_610.0}, {"date": "2026-10-29", "close": 2_712_620.0},
                               {"date": "2026-10-30", "close": 2_732_450.0}]}


def view(**over):
    seed = cases.load()
    market = lens.market_now(256_500_000.0, 3876.0, 2_740_000.0, candles(), "2026-10-31")
    odds, _ = lens.odds_view(polymarket.parse(LADDER, date(2026, 10, 31)), {"2026-11-08": 0.745}, date(2026, 10, 31))
    v = {"at": datetime(2026, 10, 31, 21, 5), "market": market, "odds": odds, "odds_state": {},
         "news": {"strike": [(HEADS[0], "Unprecedented US activity near the border; 80 US tankers in Israel")],
                  "deal": [(HEADS[1], "Qatari negotiators have been in Tehran for 12 hours; talks go on")]},
         "headlines": 4, "strikes": cases.summary(seed, "strike"), "deals": cases.summary(seed, "deal"),
         "base": seed["base"], "first_case": min(c["date"] for c in seed["cases"])}
    v["flags"] = lens.read_flags(market, odds, v["strikes"])
    v.update(over)
    return v


class LensKPI(unittest.TestCase):

    def test_01_the_odds_are_the_ceasefire_ladder_soonest_first(self):
        got = polymarket.parse(LADDER, date(2026, 10, 31))
        self.assertEqual([g[0] for g in got], [date(2026, 11, 2), date(2026, 11, 8)])
        self.assertAlmostEqual(got[0][1], 0.916)
        self.assertEqual(polymarket.parse(None, date(2026, 10, 31)), [])

    def test_02_a_failed_read_of_the_odds_is_empty_never_a_raise(self):
        real = polymarket.requests.get
        try:
            def boom(*a, **k):
                raise ConnectionError("down")
            polymarket.requests.get = boom
            self.assertEqual(polymarket.ceasefire_odds(datetime(2026, 10, 31, 17)), [])
        finally:
            polymarket.requests.get = real

    def test_03_the_headline_filter_is_the_labellings_character_for_character(self):
        import label_news_days
        self.assertEqual(news_lens.RELEVANT.pattern, label_news_days.RELEVANT.pattern)
        with open(os.path.join(ROOT, "research", "label_news_days.py"), encoding="utf-8") as f:
            self.assertIn(news_lens.MARKS.pattern, f.read())
        self.assertEqual(news_lens.MAX_HEADLINES, label_news_days.MAX_HEADLINES)
        self.assertEqual(news_lens.CHANNELS, label_news_days.CHANNELS)
        self.assertEqual(news_lens.MODEL, label_news_days.MODEL)
        self.assertIsNone(news_lens.headline("سلام"))
        self.assertEqual(news_lens.headline("🔺 قیمت نفت برنت از ۱۱۸ دلار عبور کرد\nمتن"), HEADS[3])

    def test_04_the_model_only_picks_and_translates(self):
        reply = {"strike": [{"id": 1, "en": "80 US tankers in Israel"}, {"id": 9, "en": "a headline it was not given"},
                            {"id": 4, "en": "Brent passed $120 a barrel"}],
                 "deal": [{"id": 1, "en": "the same headline on both sides"}, {"id": 2, "en": "Qatari talks <12 hours>"},
                          {"id": 3, "en": "Trump: talks are going on"}, {"id": 4, "en": "Brent above $118"},
                          {"en": "no id"}]}
        got = news_lens.validate(reply, HEADS)
        self.assertEqual([en for _, en in got["strike"]], ["80 US tankers in Israel"])   # 9 absent, 120 invented
        self.assertEqual([en for _, en in got["deal"]], ["Qatari talks &lt;12 hours&gt;", "Trump: talks are going on",
                                                         "Brent above $118"])
        self.assertIsNone(news_lens.validate("text", HEADS))
        many = {"deal": [{"id": i, "en": f"line number {i}"} for i in range(1, 5)]}
        self.assertEqual(len(news_lens.validate(many, [f"سرخط {i}" for i in range(1, 5)])["deal"]), 3)
        # the prompt as tested (SP-D 87): the first dropped "Axios" in 3 of 3 rounds and a threat's "if" in 2 of 3
        for rule in ("who says it stays", "a condition stays a condition", "never replaced by another",
                     "the meaning, not word for word"):
            self.assertIn(rule, news_lens.SYSTEM)

    def test_05_no_key_a_spent_quota_or_an_unreadable_reply_leaves_the_news_out(self):
        class R:
            def __init__(self, status, payload=None, text=""):
                self.status_code, self._p, self.text, self.headers = status, payload, text, {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(self.status_code)

            def json(self):
                return self._p
        calls = []

        def post(status, payload=None, text=""):
            def f(*a, **k):
                calls.append(k.get("json"))
                return R(status, payload, text)
            return f
        self.assertIsNone(news_lens.read(HEADS, key=""))
        self.assertIsNone(news_lens.read([], key="k", post=post(200)))
        self.assertIsNone(news_lens.read(HEADS, key="k", post=post(429, text="Rate limit: tokens per day (TPD)")))
        self.assertEqual(len(calls), 1, "a spent daily quota is not retried")
        bad = {"choices": [{"message": {"content": "not json"}}]}
        self.assertIsNone(news_lens.read(HEADS, key="k", post=post(200, bad)))
        good = {"choices": [{"message": {"content": json.dumps({"strike": [], "deal": [{"id": 3, "en": "Trump: talks go on"}]})}}]}
        self.assertEqual(news_lens.read(HEADS, key="k", post=post(200, good))["deal"][0][1], "Trump: talks go on")
        sent = calls[-1]["messages"][1]["content"]
        self.assertEqual(sent, "\n".join(f"{i}. {h}" for i, h in enumerate(HEADS, start=1)),
                         "the model is given the headlines and nothing else: never a price")

    def test_06_the_case_summary_is_computed_from_the_seed(self):
        seed = cases.load()
        s, d = cases.summary(seed, "strike"), cases.summary(seed, "deal")
        self.assertEqual((s["n"], s["higher"], d["n"], d["higher"]), (8, 6, 4, 3))
        self.assertTrue(s["lower_with_dollar_down"] and s["usual_direction"] and s["bigger"])
        self.assertEqual(sorted(c["shut_days"] for c in s["shut"]), [14, 15])
        made_up = {"base": {"higher_40_share": 0.5, "typical_abs_move_40": 20.0},
                   "cases": [{"kind": "strike", "date": "2020-01-03", "gold18_40": -30.0, "dollar_40": 5.0,
                              "gold18_5": -2.0, "shut_days": 0}]}
        m = cases.summary(made_up, "strike")
        self.assertEqual((m["higher"], m["bigger"], m["lower_with_dollar_down"]), (0, True, False))
        self.assertIsNone(cases.summary(made_up, "deal"))

    def test_07_now_is_read_against_tgjus_last_close_before_today(self):
        m = lens.market_now(256_500_000.0, 3876.0, 2_740_000.0, candles(), "2026-10-31")
        self.assertEqual(m["ref_date"], "2026-10-29")
        self.assertAlmostEqual(m["price_pct"], (256.5 / 262.235 - 1) * 100, places=6)
        self.assertAlmostEqual(m["world_pct"], (3876.0 / 4025.06 - 1) * 100, places=6)
        self.assertTrue(m["tether_record"])
        self.assertLess(m["gap_then"], 0)
        self.assertIsNone(lens.market_now(1.0, 1.0, 1.0, {"geram18": []}, "2026-10-31"))

    def test_08_the_odds_shown_and_the_odds_kept(self):
        odds = polymarket.parse(LADDER, date(2026, 10, 31))
        shown, kept = lens.odds_view(odds, {"2026-11-08": 0.745}, date(2026, 10, 31))
        self.assertEqual([(e, w) for e, _, w in shown], [(date(2026, 11, 2), None), (date(2026, 11, 8), 0.745)])
        self.assertEqual(set(kept), {"2026-11-02", "2026-11-08"})
        self.assertEqual(lens.odds_view([], {}, date(2026, 10, 31))[0], [])

    def test_09_the_reads_flags_come_from_the_numbers(self):
        s = cases.summary(cases.load(), "strike")
        m = {"world_pct": -3.7, "usd_pct": 1.1}
        self.assertEqual(lens.read_flags(m, [(date(2026, 11, 8), 0.71, None)], s)["driver"], "world")
        self.assertEqual(lens.read_flags({"world_pct": 0.2, "usd_pct": 2.0}, [], s)["driver"], "dollar")
        self.assertNotIn("driver", lens.read_flags({"world_pct": 1.0, "usd_pct": 0.8}, [], s))
        self.assertTrue(lens.read_flags(m, [(date(2026, 11, 8), 0.71, None)], s)["shut_caution"])
        self.assertFalse(lens.read_flags(m, [(date(2026, 11, 8), 0.95, None)], s)["shut_caution"])
        import inspect
        self.assertNotIn("news", inspect.signature(lens.read_flags).parameters)

    def test_10_the_message_four_blocks_persian_dates_the_last_line_and_its_length(self):
        text = telegram_lens.build_lens_message(view())
        for block in ("<b>NOW</b>", "<b>THE EVENT</b>", "<b>WHAT FOLLOWED BEFORE</b>", "<b>READ</b>"):
            self.assertIn(block, text)
        self.assertTrue(text.startswith("<b>GOLDPremium: LENS</b> · 9 Aban, 21:05"))
        self.assertTrue(text.endswith(telegram_lens.FOOTER))
        self.assertIn("to 11 Aban: 92 in 100; to 17 Aban: 71 in 100 (was 75)", text)
        self.assertIsNone(re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November"
                                    r"|December|20\d\d-\d\d-\d\d)\b", text))
        long = "x" * 120
        longest = view(news={"strike": [(h, long) for h in HEADS[:3]], "deal": [(h, long) for h in HEADS[:3]]})
        self.assertLess(len(re.sub(r"</?[bi]>", "", telegram_lens.build_lens_message(longest))), 4096)

    def test_11_what_was_not_read_is_said_and_the_rest_still_goes(self):
        text = telegram_lens.build_lens_message(view(market=None, odds=[], news=None, flags={}))
        self.assertIn("tgju's closes could not be read tonight.", text)
        self.assertIn("No market priced the ceasefire tonight.", text)
        self.assertIn("The headlines were not read tonight.", text)
        self.assertIn("<b>WHAT FOLLOWED BEFORE</b>", text)
        self.assertIn("No headline of 4 pointed either way.",
                      telegram_lens.build_lens_message(view(news={"strike": [], "deal": []})))

    def test_12_once_a_day_from_21_behind_its_switch_never_raising(self):
        import main
        import analysis.lens as al
        import alerts.telegram_lens as tl
        sent, real_view, real_send = [], al.build_view, tl.send_lens
        got = {}

        def fake_view(markets, world, usd, now, previous_odds=None):
            got["usd"] = usd
            return {**view(), "odds_state": {"2026-11-08": 0.71}}
        try:
            al.build_view, tl.send_lens = fake_view, sent.append
            state, on = {}, {"lens": {"send": True}}
            main._lens_run({}, 3876.0, 274_000, datetime(2026, 10, 31, 15, 0), state, on)    # 18:30 Tehran
            self.assertEqual(sent, [])
            main._lens_run({}, 3876.0, 274_000, datetime(2026, 10, 31, 17, 40), state, on)   # 21:10
            self.assertEqual((len(sent), got["usd"]), (1, 2_740_000), "bonbast's Tomans reach the lens as Rials")
            self.assertEqual(state["lens"], {"date": "2026-10-31", "odds": {"2026-11-08": 0.71}})
            main._lens_run({}, 3876.0, 274_000, datetime(2026, 10, 31, 18, 40), state, on)
            self.assertEqual(len(sent), 1, "once per Tehran day")
            main._lens_run({}, 3876.0, 274_000, datetime(2026, 11, 1, 17, 40), {}, {"lens": {"send": False}})
            self.assertEqual(len(sent), 1, "config.lens.send false stops it")

            def boom(*a, **k):
                raise RuntimeError("tgju down")
            al.build_view = boom
            main._lens_run({}, 3876.0, 274_000, datetime(2026, 11, 1, 17, 40), {}, on)        # prints, never raises
        finally:
            al.build_view, tl.send_lens = real_view, real_send

    def test_13_the_lens_needs_no_database_and_production_passes_the_models_key(self):
        import inspect
        for module in (lens, telegram_lens, news_lens, cases, polymarket):
            self.assertNotIn("database", inspect.getsource(module))
        with open(os.path.join(ROOT, ".github", "workflows", "gold-monitor.yml"), encoding="utf-8") as f:
            wf = f.read()
        execute = wf.split("- name: Execute", 1)[1].split("- name:", 1)[0]
        self.assertIn("GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}", execute)
        with open(os.path.join(ROOT, "config", "config.json"), encoding="utf-8") as f:
            self.assertIn("send", json.load(f)["lens"])

    def test_14_a_page_of_photos_alone_is_not_the_channels_end(self):
        import collector.news.telegram_channels as channels

        def post(i, hour, text=True):
            body = f'<div class="tgme_widget_message_text">headline {i}<br>more</div>' if text else ""
            return (f'<div class="tgme_widget_message" data-post="chan/{i}">{body}<a class="tgme_widget_message_date">'
                    f'<time datetime="2026-10-31T{hour:02d}:00:00+00:00"></time></a></div>')

        pages = {None: [post(30, 20), post(31, 21)],                         # the newest page
                 30: [post(20, 15, False), post(21, 16, False)],             # photos alone (khabarfouri, 1401)
                 20: [post(10, 9), post(11, 10)]}                            # older posts with text

        class R:
            def __init__(self, html):
                self.text = html

            def raise_for_status(self):
                pass

        real = channels.requests.get
        channels.requests.get = lambda url, params=None, **kw: R("".join(pages[(params or {}).get("before")]))
        try:
            got = channels.fetch_since("chan", datetime(2026, 10, 31, 8), max_pages=10)
        finally:
            channels.requests.get = real
        self.assertEqual([p["id"] for p in got], [10, 11, 30, 31])          # past the photos, none of them kept
        self.assertEqual(got[0]["text"], "headline 10\nmore")
        everything = channels.page_messages("".join(pages[30]), "chan")
        self.assertEqual([(p["id"], p["text"]) for p in everything], [(20, ""), (21, "")])
        self.assertEqual(channels.parse_page("".join(pages[30]), "chan"), [])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(LensKPI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print()
    print("=" * 55)
    print(f"LENS KPI RESULT: {passed}/{total} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
