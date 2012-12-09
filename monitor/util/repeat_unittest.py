#!/usr/bin/python

import unittest

from datetime import datetime
from datetime import time
from datetime import timedelta
from pytz import timezone

import repeat

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

  def test_next_sunrise(self):
    src = datetime(2012, 12, 9, 0, 32, 49)
    expected = datetime(2012, 12, 9, 15, 11, 5)

    self._almost_timedates(repeat.next_sunrise(src),
                           expected)

    self._almost_timedates(repeat.next_sunrise(expected - timedelta(minutes=5)),
                           expected)

    expected_next = datetime(2012, 12, 10, 15, 11, 52)
    self._almost_timedates(repeat.next_sunrise(expected + timedelta(minutes=5)),
                           expected_next)


  def test_next_sunset(self):
    src = datetime(2012, 12, 9, 0, 32, 49)
    expected = datetime(2012, 12, 9, 0, 50, 41)

    self._almost_timedates(repeat.next_sunset(src),
                           expected)

    self._almost_timedates(repeat.next_sunset(expected - timedelta(minutes=5)),
                           expected)

    expected_next = datetime(2012, 12, 10, 0, 50, 47)
    self._almost_timedates(repeat.next_sunset(expected + timedelta(minutes=5)),
                           expected_next)

  def test_next_interval(self):
    # Basic tests
    src = datetime(2012, 12, 9, 0, 32, 49)
    self.assertEquals(repeat.next_interval(src, 5),
                      datetime(2012, 12, 9, 0, 35, 0))
    self.assertEquals(repeat.next_interval(src, 8),
                      datetime(2012, 12, 9, 0, 40, 0))

    # Started on even time
    src = datetime(2012, 12, 9, 0, 0, 0)
    self.assertEquals(repeat.next_interval(src, 5),
                      datetime(2012, 12, 9, 0, 5, 0))

    # Hour boundries
    src = datetime(2012, 12, 9, 0, 58, 49)
    self.assertEquals(repeat.next_interval(src, 5),
                      datetime(2012, 12, 9, 1, 0, 0))
    self.assertEquals(repeat.next_interval(src, 10),
                      datetime(2012, 12, 9, 1, 0, 0))
    self.assertEquals(repeat.next_interval(src, 15),
                      datetime(2012, 12, 9, 1, 0, 0))

    # Day boundry
    src = datetime(2012, 12, 9, 23, 58, 0)
    self.assertEquals(repeat.next_interval(src, 5),
                      datetime(2012, 12, 10, 0, 0, 0))

  def test_next_daily(self):

    # Noon - Morning
    src = repeat.localtime_to_utc(datetime(2012, 2, 13, 3, 21, 17))
    result = repeat.next_daily(src)
    self.assertEquals(result, datetime(2012, 2, 13, 20, 0))

    # Noon - Evening
    src = repeat.localtime_to_utc(datetime(2012, 2, 13, 17, 21, 17))
    result = repeat.next_daily(src)
    self.assertEquals(result, datetime(2012, 2, 14, 20, 0))

    # Noon - Month/Year wrap
    src = repeat.localtime_to_utc(datetime(2012, 12, 31, 23, 59, 59))
    result = repeat.next_daily(src)
    self.assertEquals(result, datetime(2013, 1, 1, 20, 0))

    # Midnight - Morning
    src = repeat.localtime_to_utc(datetime(2012, 2, 13, 3, 21, 17))
    result = repeat.next_daily(src, time(0, 0, 0))
    self.assertEquals(result, datetime(2012, 2, 14, 8, 0))

    # Midnight - Evening
    src = repeat.localtime_to_utc(datetime(2012, 2, 13, 13, 21, 17))
    result = repeat.next_daily(src, time(0, 0, 0))
    self.assertEquals(result, datetime(2012, 2, 14, 8, 0))

    # Midnight - Midnight
    src = repeat.localtime_to_utc(datetime(2012, 2, 13, 0, 0, 0))
    result = repeat.next_daily(src, time(0, 0, 0))
    self.assertEquals(result, datetime(2012, 2, 14, 8, 0))

    # Odd Time
    src = repeat.localtime_to_utc(datetime(2012, 2, 13, 3, 21, 17))
    result = repeat.next_daily(src, time(13, 37, 19))
    self.assertEquals(result, datetime(2012, 2, 13, 21, 37, 19))


if __name__ == '__main__':
  unittest.main()
