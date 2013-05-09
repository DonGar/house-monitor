#!/usr/bin/python

import copy
import logging

from twisted.internet import task
from twisted.internet import threads

import monitor.util.ping

def update_ping_result(status, host, value):
  logging.info('Updating %s to %s', host, value)
  uri = 'status://hosts/%s/up' % host
  status.set(uri, value)

def schedule_update_all_ping_status(status):
  for host in status.get('status://hosts'):
    logging.info('Pinging %s', host)
    d = threads.deferToThread(monitor.util.ping.ping, host)
    d.addCallback(lambda value, host=host: update_ping_result(status,
                                                              host,
                                                              value))

def setup(status):
  # Setup background loop for ping targets in status
  loopingCall = task.LoopingCall(schedule_update_all_ping_status, status)
  loopingCall.start(10, True)
