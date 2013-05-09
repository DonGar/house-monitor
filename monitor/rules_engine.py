#!/usr/bin/python

import logging

class RulesEngine:

  def __init__(self, status):
    self.rules = status.get_config().get('rules', [])
    self.setup_processing(status)
    self.process_rules(status)

  def setup_processing(self, status):
    notification = status.createNotification(status.revision())
    notification.addCallback(self.setup_processing)
    self.process_rules(status)

  def process_rules(self, status):
    print 'process_rules called'
    logging.info('process_rules called')

    for rule in self.rules:
      behavior = rule['behavior']

      if behavior == 'mirror':
        process_mirror(status, rule['src'], rule['dest'])
      else:
        raise Exception('Unknown rule %s' % behavior)

def process_mirror(status, src, dest):
  status.set(dest, status.get(src))
