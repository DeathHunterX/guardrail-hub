"""Unit tests for ProgressThrottle (stage change OR >=10% OR >=30s)."""

import unittest

from app.services.notification.policy.throttle import ProgressThrottle


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class ProgressThrottleTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.throttle = ProgressThrottle(
            min_percent_step=10, min_interval_seconds=30.0, clock=self.clock
        )

    def test_first_snapshot_always_emits(self):
        self.assertTrue(self.throttle.should_emit("spider", 0))

    def test_same_stage_and_small_progress_within_interval_is_suppressed(self):
        self.throttle.should_emit("spider", 0)
        self.assertFalse(self.throttle.should_emit("spider", 5))

    def test_stage_change_emits(self):
        self.throttle.should_emit("spider", 10)
        self.assertTrue(self.throttle.should_emit("active-scan", 10))

    def test_ten_percent_step_emits(self):
        self.throttle.should_emit("scan", 10)
        self.assertFalse(self.throttle.should_emit("scan", 19))
        self.assertTrue(self.throttle.should_emit("scan", 20))

    def test_time_interval_emits(self):
        self.throttle.should_emit("scan", 10)
        self.assertFalse(self.throttle.should_emit("scan", 12))
        self.clock.advance(30)
        self.assertTrue(self.throttle.should_emit("scan", 13))


if __name__ == "__main__":
    unittest.main()
