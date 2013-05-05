#!/usr/bin/python

import logging

class Engine:

  def __init__(self, rules, status):
    self.rules = rules
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
        self.process_mirror(status, **rule)
      else:
        raise Exception('Unknown rule %s' % behavior)

  def process_mirror(self, status, behavior, src, dest):
    status.set(dest, status.get(src))
