#!/usr/bin/python

import datetime
from itertools import groupby
import logging

from twisted.web.client import getPage

from monitor.util import repeat

BEHAVIORS = ('mirror', 'interval')

def sort_rules(rules):
  # This creates a dictionary of rules indexed by behavior string.
  #  { 'mirror': (<mirror rules>), 'interval': (<interval rules>), etc }
  behaviors = dict([(b, tuple(br)) for b, br in
                    groupby(rules, lambda r: r['behavior'])])

  # Make sure we only have rules of known types.
  assert set(behaviors.keys()).issubset(set(BEHAVIORS))

  # Return tuples of rules ordered by BEHAVIORS
  return [behaviors.get(b, []) for b in BEHAVIORS]

class RulesEngine:

  def __init__(self, status):
    self.status = status
    self.rules = status.get_config().get('rules', [])

    self.mirror_rules, self.interval_rules = sort_rules(self.rules)

    # Setup the mirroring rules.
    self.setup_mirror_processing(None)
    self.process_mirror_rules()

    # Setup the timer base rules.
    self.setup_interval_rules()

  # Handle Mirror Rules
  def setup_mirror_processing(self, _):
    notification = self.status.createNotification(self.status.revision())
    notification.addCallback(self.setup_mirror_processing)
    self.process_mirror_rules()

  def process_mirror_rules(self):
    print 'process_mirror_rules called'
    logging.info('process_mirror_rules called')

    for rule in self.mirror_rules:
      src = rule['src']
      dest = rule['dest']
      self.status.set(dest, self.status.get(src))

  # Handle Interval Rules
  def setup_interval_rules(self):
    server = self.status.get_config()['server']
    latitude = float(server['latitude'])
    longitude = float(server['longitude'])

    for rule in self.interval_rules:
      if rule['interval'] == 'daily':
        # Once a day.
        if rule['time'] == 'sunset':
          delay_helper = repeat.sunset_helper(latitude, longitude)
        elif rule['time'] == 'sunrise':
          delay_helper = repeat.sunset_helper(latitude, longitude)
        elif 'time' in rule:
          hours, minutes, seconds = [int(i) for i in rule['time'].split(':')]
          time_of_day = datetime.time(hours, minutes, seconds)
          delay_helper = repeat.daily_helper(time_of_day)
        else:
          raise Exception('Unknown interval.daily time %s.' % rule['time'])

      elif rule['interval'] == 'interval':
        # Multiple times a day.
        if 'time' in rule:
          hours, minutes, seconds = [int(i) for i in rule['time'].split(':')]
          interval = datetime.timedelta(hours=hours,
                                        minutes=minutes,
                                        seconds=seconds)
          delay_helper = repeat.interval_helper(interval)
      else:
        raise Exception('Unknown interval.interval interval %s.' %
                        rule['interval'])

      # Actually start the repeating process.
      repeat.call_repeating(delay_helper, self.perform_interval_rule, rule)

  def perform_interval_rule(self, rule):
    url = rule['url']
    logging.info('Started requet %s', url)

    def print_success(_):
      logging.info('Downloaded %s.', url)

    def print_error(error):
      logging.error('FAILED download %s: %s.', url, error)

    d = getPage(url.encode('ascii'))
    d.addCallbacks(print_success, print_error)
