#!/usr/bin/python

import ephem
from datetime import datetime
from datetime import time
from datetime import timedelta

import pytz

from twisted.internet import task
from twisted.internet import reactor

from twisted.python import log


UTC_TZ = pytz.utc
PACIFIC_TZ = pytz.timezone('US/Pacific')


def utc_to_localtime(datetime_in):
  """Convert a naive datetime from utc to naive localtime"""
  utc_datetime = UTC_TZ.localize(datetime_in)
  pacific_datetime = utc_datetime.astimezone(PACIFIC_TZ)
  naive = pacific_datetime.replace(tzinfo=None)
  return naive


def localtime_to_utc(datetime_in):
  """Convert a naive datetime from localtime to naive utc"""
  pacific_datetime = PACIFIC_TZ.localize(datetime_in)
  utc_datetime = pacific_datetime.astimezone(UTC_TZ)
  naive = utc_datetime.replace(tzinfo=None)
  return naive


def datetime_to_seconds_delay(utc_now, future):
  delta = future - utc_now
  return delta.total_seconds()


def sunrise_next(utc_now, latitude, longitude):
  """Next sunrise (today or tomorrow)"""

  obs = ephem.Observer()
  obs.lat = latitude
  obs.long = longitude
  obs.date = utc_now
  return obs.next_rising(ephem.Sun()).datetime()


def sunrise_helper(latitude, longitude):
  return lambda now: sunrise_next(now, latitude, longitude)


def sunset_next(utc_now, latitude, longitude):
  """Next sunset (today or tomorrow)"""

  obs = ephem.Observer()
  obs.lat = latitude
  obs.long = longitude
  obs.date = utc_now
  return obs.next_setting(ephem.Sun()).datetime()


def sunset_helper(latitude, longitude):
  return lambda now: sunset_next(now, latitude, longitude)


def interval_next(utc_now, interval=timedelta(minutes=5)):
  """Return the next even interval in a naive utc timestamp."""

  # Make sure interval is > 0.
  interval = max(interval, timedelta(seconds=1))

  # Start results at UTC midnight, work forward.
  result = datetime.combine(utc_now.date(), time())
  while result < utc_now:
    result += interval

  return result


def interval_helper(interval):
  return lambda now: interval_next(now, interval)


def daily_next(utc_now, daytime=time(12, 0, 0)):
  """Return the next noon (localtime) in a naive utc timestamp."""

  def _daily_next_recursive(utc_in):
    local_in = utc_to_localtime(utc_in)
    local_time = datetime.combine(local_in.date(), daytime)
    utc_time = localtime_to_utc(local_time)

    if utc_time > utc_now:
      return utc_time

    return _daily_next_recursive(utc_in + timedelta(hours=12))

  return _daily_next_recursive(utc_now)


def daily_helper(daytime):
  return lambda now: daily_next(now, daytime)


def call_repeating(timing_helper, work, *args, **kwargs):
  """Call a function repeatedly.

  Args:
    timing_helper: A function which accepts a datetime() for the current
        time, and returns a datetime telling when the work function should
        next be called.

    work: A function to be called at repeating intervals.
          Passed *args, **kwargs.
  """

  def timing_helper_to_seconds_delay():
    utc_now = datetime.utcnow()
    result = timing_helper(utc_now)
    return datetime_to_seconds_delay(utc_now, result)

  def do_work_repeating():
    # Don't let an error doing the work prevent the job from repeating.
    try:
      work(*args, **kwargs)
    # pylint: disable=W0703
    except Exception:
      log.err()

    task.deferLater(reactor,
                    timing_helper_to_seconds_delay(),
                    do_work_repeating)

  # Setup initial call to do_work_repeating
  task.deferLater(reactor,
                  timing_helper_to_seconds_delay(),
                  do_work_repeating)
