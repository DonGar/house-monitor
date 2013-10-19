#!/usr/bin/python

import datetime
import logging

import monitor.actions
from monitor.util import repeat

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task

class UnknownRuleBehavior(Exception):
  """Raised when a rule with an unknown 'behavior' is found."""


class RulesEngine(object):

  # The known types of rules.
  BEHAVIORS = ('interval', 'daily', 'watch')

  def __init__(self, status):
    self.status = status

    self._helpers = []

    # This creates a dictionary of rules indexed by behavior string.
    #  { 'mirror': (<mirror rules>), 'interval': (<interval rules>), etc }
    rules = status.get('status://config/rule', {})

    for name, rule in rules.iteritems():
      assert rule['behavior'] in self.BEHAVIORS

      if rule['behavior'] == 'interval':
        helper_type = _IntervalHelper
      elif rule['behavior'] == 'daily':
        helper_type = _DailyHelper
      elif rule['behavior'] == 'watch':
        helper_type = _WatchHelper
      else:
        raise UnknownRuleBehavior(str(rule))

      self._helpers.append(helper_type(self, self.status, name, rule))

    for helper in self._helpers:
      helper.start()

  def stop(self):
    deferred_list = [w.stop() for w in self._helpers]

    # Return a deferred which will fire when all rules have been shut down. This
    # is required since our rules have outstanding deferreds whose cancel
    # operations require another iteration of the reactor.
    return defer.DeferredList([d for d in deferred_list if d],
                              consumeErrors=True)

  def utc_now(self):
    """This method exists for unittests to override to control current time."""
    return datetime.datetime.utcnow()


class _RuleHelper(object):
  def __init__(self, engine, status, name, rule):
    self._engine = engine
    self._status = status
    self._name = name
    self._rule = rule
    self._deferred = None

    logging.info('Init %s rule %s.', self._rule['behavior'], self._name)

  def start(self):
    logging.info('Starting rule %s.', self._name)

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
    logging.info('Stopping rule %s', self._name)
    if self._deferred:
      d = self._deferred
      self._deferred.cancel()
      self._deferred = None
      return d

  def next_deferred(self):
    return defer.Deferred()

  def fire(self, value):
    logging.info('Firing rule: %s', self._name)
    monitor.actions.handle_action(self._status, self._rule['action'])
    return value


class _DailyHelper(_RuleHelper):
  def __init__(self, engine, status, name, rule):
    super(_DailyHelper, self).__init__(engine, status, name, rule)

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
    return task.deferLater(reactor, seconds_delay, lambda : None)


class _IntervalHelper(_RuleHelper):
  def __init__(self, engine, status, name, rule):
    super(_IntervalHelper, self).__init__(engine, status, name, rule)

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
    return task.deferLater(reactor, seconds_delay, lambda : None)


class _WatchHelper(_RuleHelper):

  def next_deferred(self):
    return self._status.deferred(url=self._rule['value'])

  def fire(self, value):
    # If a trigger exists in the rule, it must match to fire the rule.
    if 'trigger' in self._rule:
      possible_trigger_value = self._status.get(self._rule['value'])
      fire_action =  possible_trigger_value == self._rule['trigger']
    else:
      fire_action = True

    if fire_action:
      logging.info('Firing rule: %s', self._name)
      monitor.actions.handle_action(self._status, self._rule['action'])

    return value
