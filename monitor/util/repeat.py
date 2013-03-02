#!/usr/bin/python

import ephem
from datetime import datetime
from datetime import time
from datetime import timedelta
import traceback

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


def next_sunrise(latitude, longitude):
  """Next sunrise (today or tomorrow)"""

  obs = ephem.Observer()
  obs.lat = latitude
  obs.long = longitude

  while True:
    utc_now = datetime.utcnow()
    obs.date = utc_now
    result = obs.next_rising(ephem.Sun()).datetime()
    yield datetime_to_seconds_delay(utc_now, result)


def next_sunset(latitude, longitude):
  """Next sunset (today or tomorrow)"""

  obs = ephem.Observer()
  obs.lat = latitude
  obs.long = longitude

  while True:
    utc_now = datetime.utcnow()
    obs.date = utc_now
    result = obs.next_setting(ephem.Sun()).datetime()
    yield datetime_to_seconds_delay(utc_now, result)


def next_interval(interval=timedelta(minutes=5)):
  """Return the next even interval in a naive utc timestamp."""

  # Make sure interval is > 0.
  interval = max(interval, timedelta(seconds=1))

  while True:
    utc_now = datetime.utcnow()

    # Start results at UTC midnight, work forward.
    result = datetime.combine(utc_now.date(), time())
    while result < utc_now:
      result += interval

    yield datetime_to_seconds_delay(utc_now, result)


def next_daily(daytime=time(12, 0, 0)):
  """Return the next noon (localtime) in a naive utc timestamp."""

  while True:
    utc_now = datetime.utcnow()

    def _next_daily_recursive(utc_in):
      local_in = utc_to_localtime(utc_in)
      local_time = datetime.combine(local_in.date(), daytime)
      utc_time = localtime_to_utc(local_time)

      if utc_time > utc_now:
        return utc_time

      return _next_daily_recursive(utc_in + timedelta(hours=12))

    result = _next_daily_recursive(utc_now)
    yield datetime_to_seconds_delay(utc_now, result)


def call_repeating(next_call, work, *args, **kwargs):
  """Call a function repeatedly.

  Args:
    next_call: A function which accepts a datetime for 'now', and returns
               the next time at which to run.
    work: A function to be called at repeating intervals.
          Passed *args, **kwargs.
  """

  def do_work_repeating():
    # Don't let an error doing the work prevent the job from repeating.
    try:
      work(*args, **kwargs)
    except Exception as e:
      log.err()

    task.deferLater(reactor, next(next_call), do_work_repeating)

  # Setup initial call to do_work_repeating
  task.deferLater(reactor, next(next_call), do_work_repeating)

