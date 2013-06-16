#!/usr/bin/python

import unittest

from datetime import datetime
from datetime import time
from datetime import timedelta
from pytz import timezone

from monitor.util import repeat

LATITUDE = 37.3861
LONGITUDE = -122.0839


class TestRepeatFunctions(unittest.TestCase):

  def test_utc_to_localtime(self):
    dt = datetime.utcnow()
    self.assertEquals(repeat.localtime_to_utc(repeat.utc_to_localtime(dt)),
                      dt)

    src = datetime(2012, 12, 9, 0, 32, 49)
    self.assertEquals(repeat.utc_to_localtime(src),
                      datetime(2012, 12, 8, 16, 32, 49))

  def test_localtime_to_utc(self):
    dt = datetime.now()
    self.assertEquals(repeat.utc_to_localtime(repeat.localtime_to_utc(dt)),
                      dt)

    src = datetime(2012, 12, 8, 16, 32, 49)
    self.assertEquals(repeat.localtime_to_utc(src),
                      datetime(2012, 12, 9, 0, 32, 49))

  def test_datetime_to_seconds_delay(self):
    now = datetime.utcnow()

    def compareDifference(delta, expected_seconds):
      seconds = repeat.datetime_to_seconds_delay(now, now + delta)
      self.assertAlmostEquals(seconds, expected_seconds, places=2)

    compareDifference(timedelta(days=1), 86400)
    compareDifference(timedelta(seconds=100), 100)
    compareDifference(timedelta(seconds=10), 10)
    compareDifference(timedelta(seconds=1), 1)
    compareDifference(timedelta(seconds=0), 0)
    compareDifference(timedelta(seconds=-100), -100)

  def _almost_timedates(self, left, right):
    self.assertEquals(left.replace(microsecond=0),
                      right.replace(microsecond=0))

  def test_sunrise_next(self):
    helper = repeat.sunrise_helper(LATITUDE, LONGITUDE)
    expected = datetime(2012, 12, 9, 15, 36, 38)

    now = datetime(2012, 12, 9, 0, 32, 49)
    self._almost_timedates(helper(now), expected)

    now = expected - timedelta(seconds=1)
    self._almost_timedates(helper(now), expected)

    now = expected + timedelta(seconds=1)
    expected_next = datetime(2012, 12, 10, 15, 36, 57)
    self._almost_timedates(helper(now), expected_next)


  def test_sunset_next(self):
    helper = repeat.sunset_helper(LATITUDE, LONGITUDE)
    expected = datetime(2012, 12, 9, 4, 47, 24)

    now = datetime(2012, 12, 9, 0, 32, 49)
    self._almost_timedates(helper(now), expected)

    now = expected - timedelta(seconds=1)
    self._almost_timedates(helper(now), expected)

    now = expected + timedelta(seconds=1)
    expected_next = datetime(2012, 12, 10, 4, 48, 0)
    self._almost_timedates(helper(now), expected_next)

  def test_interval_next(self):
    helper_five = repeat.interval_helper(timedelta(minutes=5))

    # Basic tests
    now = datetime(2012, 12, 9, 0, 32, 49)
    self.assertEquals(helper_five(now), datetime(2012, 12, 9, 0, 35, 0))
    self.assertEquals(repeat.interval_next(now, timedelta(minutes=8)),
                      datetime(2012, 12, 9, 0, 40, 0))

    # Started on even time
    now = datetime(2012, 12, 9, 0, 0, 0)
    self.assertEquals(helper_five(now), datetime(2012, 12, 9, 0, 0, 0))

    # Hour boundries
    now = datetime(2012, 12, 9, 0, 58, 49)
    self.assertEquals(helper_five(now),
                      datetime(2012, 12, 9, 1, 0, 0))
    self.assertEquals(repeat.interval_next(now, timedelta(minutes=10)),
                      datetime(2012, 12, 9, 1, 0, 0))
    self.assertEquals(repeat.interval_next(now, timedelta(minutes=15)),
                      datetime(2012, 12, 9, 1, 0, 0))

    # Day boundry
    now = datetime(2012, 12, 9, 23, 58, 0)
    self.assertEquals(repeat.interval_next(now, timedelta(minutes=5)),
                      datetime(2012, 12, 10, 0, 0, 0))

  def test_daily_next(self):
    helper_noon = repeat.daily_helper(time(12, 0, 0))
    helper_midnight = repeat.daily_helper(time(0, 0, 0))

    # Noon - Morning
    now = repeat.localtime_to_utc(datetime(2012, 2, 13, 3, 21, 17))
    result = helper_noon(now)
    self.assertEquals(result, datetime(2012, 2, 13, 20, 0))

    # Noon - Evening
    now = repeat.localtime_to_utc(datetime(2012, 2, 13, 17, 21, 17))
    result = helper_noon(now)
    self.assertEquals(result, datetime(2012, 2, 14, 20, 0))

    # Noon - Month/Year wrap
    now = repeat.localtime_to_utc(datetime(2012, 12, 31, 23, 59, 59))
    result = helper_noon(now)
    self.assertEquals(result, datetime(2013, 1, 1, 20, 0))

    # Midnight - Morning
    now = repeat.localtime_to_utc(datetime(2012, 2, 13, 3, 21, 17))
    result = helper_midnight(now)
    self.assertEquals(result, datetime(2012, 2, 14, 8, 0))

    # Midnight - Evening
    now = repeat.localtime_to_utc(datetime(2012, 2, 13, 13, 21, 17))
    result = helper_midnight(now)
    self.assertEquals(result, datetime(2012, 2, 14, 8, 0))

    # Midnight - Midnight
    now = repeat.localtime_to_utc(datetime(2012, 2, 13, 0, 0, 0))
    result = helper_midnight(now)
    self.assertEquals(result, datetime(2012, 2, 14, 8, 0))

    # Odd Time
    now = repeat.localtime_to_utc(datetime(2012, 2, 13, 3, 21, 17))
    result = repeat.daily_next(now, time(13, 37, 19))
    self.assertEquals(result, datetime(2012, 2, 13, 21, 37, 19))


if __name__ == '__main__':
  unittest.main()
