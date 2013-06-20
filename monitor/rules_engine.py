#!/usr/bin/python

import datetime
from itertools import groupby
import logging

from twisted.web.client import getPage

import monitor.actions
from monitor.util import repeat


class RulesEngine:

  # The known types of rules.
  BEHAVIORS = ('watch', 'daily', 'interval')

  def __init__(self, status):
    self.status = status

    # This creates a dictionary of rules indexed by behavior string.
    #  { 'mirror': (<mirror rules>), 'interval': (<interval rules>), etc }
    rules = status.get('status://rules', ())
    behaviors = dict([(b, tuple(br)) for b, br in
                      groupby(rules, lambda r: r['behavior'])])

    # Make sure we only have rules of known types.
    assert set(behaviors.keys()).issubset(set(self.BEHAVIORS))

    # Remember the rules split out by type of rule.
    self._watch_rules = behaviors.get('watch', ())
    self._daily_rules = behaviors.get('daily', ())
    self._interval_rules = behaviors.get('interval', ())

    # Create a list of 'last seen' values for the watch rules.
    self._watch_last_seen = [None] * len(self._watch_rules)

    # Start processing watch rules.
    self._setup_watch_processing()

    # Setup the timer base rules.
    self._setup_daily_rules()
    self._setup_interval_rules()

  # Handle Mirror Rules
  def _setup_watch_processing(self, _=None):
    notification = self.status.createNotification(self.status.revision())
    notification.addCallback(self._setup_watch_processing)
    self._process_watch_rules()

  def _process_watch_rules(self):
    logging.info('_process_watch_rules called')

    for i in xrange(len(self._watch_rules)):
      rule = self._watch_rules[i]

      # If the values referenced by the rule hasn't changed, skip this rule.
      value = self.status.get(rule['value'])
      if value == self._watch_last_seen[i]:
        continue
      self._watch_last_seen[i] = value

      # If the new value doesn't match the trigger, skip this rule.
      trigger = rule.get('trigger', None)
      if trigger is not None and value != trigger:
        continue

      # Fire off the rules action.
      monitor.actions.handle_action(self.status, rule['action'])

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
