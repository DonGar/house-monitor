#!/usr/bin/python

import datetime
import logging
import os

from monitor.util import repeat

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task

class UnknownRuleBehavior(Exception):
  """Raised when a rule with an unknown 'behavior' is found."""


class RulesEngine(object):

  # The known types of rules.
  BEHAVIORS = ('interval', 'daily', 'watch')

  def __init__(self, status, action_manager):
    self._status = status
    self._action_manager = action_manager
    self._helpers = []

    self._update_rules()

  def _update_rules(self):
    # Stop/clear old rules.
    for helper in self._helpers:
      helper.stop()
    self._helpers = []

    # Recreate all rules.
    rule_urls = self._status.get_matching_urls('status://*/rule/*')

    for url in rule_urls:
      rule = self._status.get(url)

      assert rule['behavior'] in self.BEHAVIORS

      if rule['behavior'] == 'interval':
        helper_type = _IntervalHelper
      elif rule['behavior'] == 'daily':
        helper_type = _DailyHelper
      elif rule['behavior'] == 'watch':
        helper_type = _WatchHelper
      else:
        raise UnknownRuleBehavior(str(rule))

      self._helpers.append(helper_type(self, self._status, url, rule))

    for helper in self._helpers:
      helper.start()

  def stop(self):
    deferred_list = [w.stop() for w in self._helpers]

    # Return a deferred which will fire when all rules have been shut down. This
    # is required since some of our rules have outstanding deferreds whose
    # cancel operations require another iteration of the reactor.
    return defer.DeferredList([d for d in deferred_list if d],
                              consumeErrors=True)

  def utc_now(self):
    """This method exists for unittests to override to control current time."""
    return datetime.datetime.utcnow()


class _RuleHelper(object):
  def __init__(self, engine, status, url, rule):
    self._engine = engine
    self._status = status
    self._url = url
    self._rule = rule
    self._deferred = None

    logging.info('Init %s rule %s.', self._rule['behavior'], self._url)

  def start(self):
    logging.info('Starting rule %s.', self._url)

    def restart_handler(value):
      """This function is a callback handler that sets up the next deferred."""

      # This happens normally at shutdown.
      def cancel_ok(failure):
        failure.trap(defer.CancelledError)

      self._deferred = self.next_deferred()
      self._deferred.addCallback(restart_handler)
      self._deferred.addCallback(self.fire)
      self._deferred.addErrback(cancel_ok)
      return value

    # Setup the initial deferred.
    restart_handler(None)
    return self._deferred

  def stop(self):
    logging.info('Stopping rule %s', self._url)
    if self._deferred:
      d = self._deferred
      self._deferred.cancel()
      self._deferred = None
      return d

  def next_deferred(self):
    return defer.Deferred()

  def fire(self, value):
    logging.info('Firing rule: %s', self._url)
    # pylint: disable=W0212
    self._engine._action_manager.handle_action(
        os.path.join(self._url, 'action'))
    return value


class _DailyHelper(_RuleHelper):
  def __init__(self, engine, status, url, rule):
    super(_DailyHelper, self).__init__(engine, status, url, rule)

    latitude = float(self._status.get('status://server/latitude'))
    longitude = float(self._status.get('status://server/longitude'))

    # The _find_next_fire_time is a method that returns the datetime in which to
    # next fire if passed utcnow as a datetime. The different implementations of
    # it are how we adjust for different types of daily rules.

    if self._rule['time'] == 'sunset':
      self._find_next_fire_time = repeat.sunset_helper(latitude, longitude)
    elif self._rule['time'] == 'sunrise':
      self._find_next_fire_time = repeat.sunrise_helper(latitude, longitude)
    else:
      # Else we expect time to be in the format 'hh:mm:ss'
      hours, minutes, seconds = [int(i) for i in self._rule['time'].split(':')]
      time_of_day = datetime.time(hours, minutes, seconds)
      self._find_next_fire_time = repeat.daily_helper(time_of_day)

  def next_deferred(self):
    utc_now = self._engine.utc_now()
    time_to_fire = self._find_next_fire_time(utc_now)
    seconds_delay = repeat.datetime_to_seconds_delay(utc_now, time_to_fire)
    return task.deferLater(reactor, seconds_delay, lambda: None)


class _IntervalHelper(_RuleHelper):
  def __init__(self, engine, status, url, rule):
    super(_IntervalHelper, self).__init__(engine, status, url, rule)

    # The _find_next_fire_time is a method that returns the datetime in which to
    # next fire if passed utcnow as a datetime. The different implementations of
    # it are how we adjust for different types of daily rules.

    # Multiple times a day. Expect 'time' to be in format 'hh:mm:ss'
    hours, minutes, seconds = [int(i) for i in rule['time'].split(':')]
    interval = datetime.timedelta(hours=hours,
                                  minutes=minutes,
                                  seconds=seconds)
    self._find_next_fire_time = repeat.interval_helper(interval)

  def next_deferred(self):
    utc_now = self._engine.utc_now()
    time_to_fire = self._find_next_fire_time(utc_now)
    seconds_delay = repeat.datetime_to_seconds_delay(utc_now, time_to_fire)
    return task.deferLater(reactor, seconds_delay, lambda: None)


class _WatchHelper(_RuleHelper):

  def next_deferred(self):
    return self._status.deferred(url=self._rule['value'])

  def fire(self, value):
    possible_trigger_value = self._status.get(self._rule['value'])

    # If a trigger exists in the rule, it must match to fire the rule.
    if 'trigger' in self._rule:
      fire_action = possible_trigger_value == self._rule['trigger']
    else:
      fire_action = True

    # If the value doesn't exist, don't fire a rule watching it.
    if possible_trigger_value is None:
      fire_action = False

    if fire_action:
      super(_WatchHelper, self).fire(value)

    return value
