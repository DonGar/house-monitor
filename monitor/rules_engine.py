#!/usr/bin/python

import datetime
import logging

import monitor.actions
from monitor.util import repeat

from twisted.internet import defer


class _WatchHelper(object):
  def __init__(self, engine, name, rule):
    self._engine = engine
    self._name = name
    self._rule = rule
    self._deferred = None

    self.start()

  def start(self):
    def cancel_ok(failure):
      # This happens normally at shutdown.
      failure.trap(defer.CancelledError)

    self._deferred = self._engine.status.deferred(url=self._rule['value'])
    self._deferred.addCallbacks(self.watch_updated, cancel_ok)

  def stop(self):
    logging.info('Stopping rule %s', self._name)
    if self._deferred:
      d = self._deferred
      self._deferred.cancel()
      self._deferred = None
      return d

  def watch_updated(self, value):
    self.start()

    # If a trigger exists in the rule, it must match to fire the rule.
    if 'trigger' in self._rule:
      fire_action = value == self._rule['trigger']
    else:
      fire_action = True

    if fire_action:
      logging.info('Firing rule: %s', self._name)
      monitor.actions.handle_action(self._engine.status, self._rule['action'])

    return value


class RulesEngine(object):

  # The known types of rules.
  BEHAVIORS = ('interval', 'daily', 'watch')

  def __init__(self, status):
    self.status = status

    self._interval_helpers = []
    self._daily_helpers = []
    self._watch_helpers = []

    # This creates a dictionary of rules indexed by behavior string.
    #  { 'mirror': (<mirror rules>), 'interval': (<interval rules>), etc }
    rules = status.get('status://config/rule', {})

    for name, rule in rules.iteritems():
      assert rule['behavior'] in self.BEHAVIORS

      if rule['behavior'] == 'interval':
        self._setup_interval_rule(name, rule)
      if rule['behavior'] == 'daily':
        self._setup_daily_rule(name, rule)
      if rule['behavior'] == 'watch':
        self._watch_helpers.append(_WatchHelper(self, name, rule))


  def stop(self):
    deferred_list = [w.stop() for w in self._watch_helpers]

    # Return a deferred which will fire when all rules have been shut down. This
    # is required since our rules have outstanding deferreds whose cancel
    # operations require another iteration of the reactor.
    return defer.DeferredList([d for d in deferred_list if d],
                              consumeErrors=True)

  # Handle Interval Rules
  def _setup_interval_rule(self, name, rule):
    logging.info('Init interval rule %s for %s', name, rule['time'])
    # Multiple times a day. Expect 'time' to be in format 'hh:mm:ss'
    hours, minutes, seconds = [int(i) for i in rule['time'].split(':')]
    interval = datetime.timedelta(hours=hours,
                                  minutes=minutes,
                                  seconds=seconds)
    delay_helper = repeat.interval_helper(interval)

    # Actually start the repeating process.
    repeat.call_repeating(delay_helper,
                          monitor.actions.handle_action,
                          self.status,
                          rule['action'])

  # Handle Daily Rules
  def _setup_daily_rule(self, name, rule):
    latitude = float(self.status.get('status://server/latitude'))
    longitude = float(self.status.get('status://server/longitude'))

    logging.info('Init daily rule %s for %s', name, rule['time'])
    # Once a day.
    if rule['time'] == 'sunset':
      delay_helper = repeat.sunset_helper(latitude, longitude)
    elif rule['time'] == 'sunrise':
      delay_helper = repeat.sunrise_helper(latitude, longitude)
    else:
      # Else we expect time to be in the format 'hh:mm:ss'
      hours, minutes, seconds = [int(i) for i in rule['time'].split(':')]
      time_of_day = datetime.time(hours, minutes, seconds)
      delay_helper = repeat.daily_helper(time_of_day)

    # Actually start the repeating process.
    repeat.call_repeating(delay_helper,
                          monitor.actions.handle_action,
                          self.status,
                          rule['action'])
