#!/usr/bin/python

import datetime
from itertools import groupby
import logging

from twisted.web.client import getPage

from monitor.util import action
from monitor.util import repeat

BEHAVIORS = ('mirror', 'daily', 'interval')

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

    (self.mirror_rules,
     self.daily_rules,
     self.interval_rules) = sort_rules(self.rules)

    # Setup the mirroring rules.
    self.setup_mirror_processing(None)
    self.process_mirror_rules()

    # Setup the timer base rules.
    self.setup_daily_rules()
    self.setup_interval_rules()

  # Handle Mirror Rules
  def setup_mirror_processing(self, _):
    notification = self.status.createNotification(self.status.revision())
    notification.addCallback(self.setup_mirror_processing)
    self.process_mirror_rules()

  def process_mirror_rules(self):
    logging.info('process_mirror_rules called')

    for rule in self.mirror_rules:
      src = rule['src']
      dest = rule['dest']
      self.status.set(dest, self.status.get(src))

  def _setup_repeating_helper(self, delay_helper, url, download_pattern=None):

    if download_pattern:
      # Actually start the repeating process.
      repeat.call_repeating(delay_helper,
                            action.download_page_wrapper,
                            self.status,
                            download_pattern,
                            url)
    else:
      # Actually start the repeating process.
      repeat.call_repeating(delay_helper,
                            action.get_page_wrapper,
                            self.status,
                            url)




  # Handle Daily Rules
  def setup_daily_rules(self):
    server = self.status.get_config()['server']
    latitude = float(server['latitude'])
    longitude = float(server['longitude'])

    for rule in self.daily_rules:
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
      self._setup_repeating_helper(delay_helper,
                                   rule['url'].encode('ascii'),
                                   rule.get('download_name', None))

  # Handle Interval Rules
  def setup_interval_rules(self):
    for rule in self.interval_rules:
      logging.info('Init interval rule for %s', rule['time'])
      # Multiple times a day. Expect 'time' to be in format 'hh:mm:ss'
      hours, minutes, seconds = [int(i) for i in rule['time'].split(':')]
      interval = datetime.timedelta(hours=hours,
                                    minutes=minutes,
                                    seconds=seconds)
      delay_helper = repeat.interval_helper(interval)

      # Actually start the repeating process.
      self._setup_repeating_helper(delay_helper,
                                   rule['url'].encode('ascii'),
                                   rule.get('download_name', None))
