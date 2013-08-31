#!/usr/bin/python

import datetime
from itertools import groupby
import logging

import monitor.actions
from monitor.util import repeat

from twisted.internet import defer


class _WatchHelper(object):
  def __init__(self, engine, rule):
    self._engine = engine
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
      monitor.actions.handle_action(self._engine.status, self._rule['action'])

    return value


class RulesEngine(object):

  # The known types of rules.
  BEHAVIORS = ('watch', 'daily', 'interval')

  def __init__(self, status):
    self.status = status

    # This creates a dictionary of rules indexed by behavior string.
    #  { 'mirror': (<mirror rules>), 'interval': (<interval rules>), etc }
    rules = status.get('status://config/rule', {})
    behaviors = dict([(b, tuple(br)) for b, br in
                      groupby(rules.itervalues(), lambda r: r['behavior'])])

    # Make sure we only have rules of known types.
    assert set(behaviors.keys()).issubset(set(self.BEHAVIORS))

    # Remember the rules split out by type of rule.
    self._watch_rules = behaviors.get('watch', ())
    self._daily_rules = behaviors.get('daily', ())
    self._interval_rules = behaviors.get('interval', ())

    # Start processing watch rules.
    self._watch_helpers = [_WatchHelper(self, rule) for
                           rule in self._watch_rules]

    # Setup the timer base rules.
    self._setup_daily_rules()
    self._setup_interval_rules()


  def stop(self):
    deferred_list = [w.stop() for w in self._watch_helpers]
    return defer.DeferredList([d for d in deferred_list if d],
                              consumeErrors=True)

  # Handle Daily Rules
  def _setup_daily_rules(self):
    latitude = float(self.status.get('status://server/latitude'))
    longitude = float(self.status.get('status://server/longitude'))

    for rule in self._daily_rules:
      logging.info('Init daily rule for %s', rule['time'])
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

  # Handle Interval Rules
  def _setup_interval_rules(self):
    for rule in self._interval_rules:
      logging.info('Init interval rule for %s', rule['time'])
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
