#!/usr/bin/python

import ephem
from datetime import datetime
from datetime import time
from datetime import timedelta

import pytz

from twisted.internet import task
from twisted.internet import reactor


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


def _mountainview_observer(utc_now):
  """Setup ephem.Observer for Mountain View, CA, now"""
  obs = ephem.Observer()
  obs.lat = '37.3861'
  obs.long= '-122.0839'
  obs.date = utc_now
  return obs


def next_sunrise(utc_now):
  """ Next sunrise (today or tomorrow)"""
  obs = _mountainview_observer(utc_now)
  return obs.next_rising(ephem.Sun()).datetime()


def next_sunset(utc_now):
  """ Next sunset (today or tomorrow)"""
  obs = _mountainview_observer(utc_now)
  return obs.next_setting(ephem.Sun()).datetime()


def next_interval(utc_now, interval_minutes=5):
  """Return the next even interval in a naive utc timestamp."""
  unrounded_time = utc_now + timedelta(minutes=interval_minutes)
  rounded_minutes = unrounded_time.minute - (unrounded_time.minute %
                                             interval_minutes)
  return unrounded_time.replace(minute=rounded_minutes,
                                second=0,
                                microsecond=0)


def next_daily(utc_now, time=time(12, 0, 0)):
  """Return the next noon (localtime) in a naive utc timestamp."""

  def _next_daily_recursive(utc_in, time):
    local_in = utc_to_localtime(utc_in)
    local_time = datetime.combine(local_in.date(), time)
    utc_time = localtime_to_utc(local_time)

    if utc_time > utc_now:
      return utc_time

    return _next_daily_recursive(utc_in + timedelta(hours=12), time)

  return _next_daily_recursive(utc_now, time)


def call_repeating(next_call, work, *args, **kwargs):
  """Call a function repeatedly.

  Args:
    next_call: A function which accepts a datetime for 'now', and returns
               the next time at which to run.
    work: A function to be called at repeating intervals.
          Passed *args, **kwargs.
  """

  def do_work_repeating():
    work(*args, **kwargs)
    now = datetime.utcnow()
    delay = datetime_to_seconds_delay(now, next_call(now))
    task.deferLater(reactor, delay, do_work_repeating)

  # Setup initial call to do_work_repeating
  now = datetime.utcnow()
  delay = datetime_to_seconds_delay(now, next_call(now))
  task.deferLater(reactor, delay, do_work_repeating)

