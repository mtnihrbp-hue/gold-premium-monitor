import unittest
from types import SimpleNamespace
from unittest.mock import patch

from alerts.resend_mail import send_alert as send_email_alert
from alerts.telegram import send_alert as send_telegram_alert


class TestAlertRouting(unittest.TestCase):
    def setUp(self):
        self.signal = {
            "signal": "BUY",
            "reason": "legacy threshold",
        }
        self.state_wait = SimpleNamespace(
            final_decision="WAIT",
            reason="Candidate conditions are not confirmed.",
            valuation="CHEAP",
            momentum="WEAKENING",
            premium_direction="DISCOUNT_NARROWING",
            structure="DISCOUNT_DOMINANT",
            conflict="CAUTION",
            candidate_decision="WAIT",
        )
        self.state_buy = SimpleNamespace(
            final_decision="BUY",
            reason="Final decision confirmed.",
            valuation="CHEAP",
            momentum="IMPROVING",
            premium_direction="DISCOUNT_WIDENING",
            structure="DISCOUNT_DOMINANT",
            conflict="SUPPORTIVE",
            candidate_decision="BUY",
        )
        self.markets = {}

    @patch("alerts.telegram._send")
    def test_telegram_does_not_send_when_final_is_wait(self, mock_send):
        send_telegram_alert(
            self.signal,
            2400,
            50000,
            1900000,
            1880000,
            -1.05,
            self.markets,
            signal_state=self.state_wait,
        )
        mock_send.assert_not_called()

    @patch("alerts.telegram._send")
    def test_telegram_uses_final_decision(self, mock_send):
        send_telegram_alert(
            {"signal": "SELL", "reason": "legacy mismatch"},
            2400,
            50000,
            1900000,
            1880000,
            -1.05,
            self.markets,
            signal_state=self.state_buy,
        )
        mock_send.assert_called_once()
        message = mock_send.call_args.args[0]
        self.assertIn("BUY SIGNAL", message)
        self.assertNotIn("SELL SIGNAL", message)

    @patch("alerts.resend_mail._send")
    def test_email_does_not_send_when_final_is_wait(self, mock_send):
        send_email_alert(
            self.signal,
            2400,
            50000,
            1900000,
            1880000,
            -1.05,
            self.markets,
            signal_state=self.state_wait,
        )
        mock_send.assert_not_called()

    @patch("alerts.resend_mail._send")
    def test_email_accepts_momentum_keyword(self, mock_send):
        send_email_alert(
            self.signal,
            2400,
            50000,
            1900000,
            1880000,
            -1.05,
            self.markets,
            trends=None,
            momentum={"verbal_direction": "Toward Buy"},
            signal_state=self.state_buy,
        )
        mock_send.assert_called_once()
        subject, _html = mock_send.call_args.args
        self.assertEqual(subject, "BUY Gold Alert")


if __name__ == "__main__":
    unittest.main()
