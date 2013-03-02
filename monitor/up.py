#!/usr/bin/python

import logging

from twisted.internet import task
from twisted.internet import threads

from monitor import util

def update_ping_result(status, host, value):
  logging.info('Updating %s to %s', host, value)
  status.update({host : value})

def schedule_update_all_ping_status(status, hosts):
  for host in hosts:
    d = threads.deferToThread(util.ping, host)
    d.addCallback(lambda value, host=host: update_ping_result(status, host, value))

def setup(status, hosts):
  # Setup background loop for ping targets in status
  loopingCall = task.LoopingCall(schedule_update_all_ping_status, status, hosts)
  loopingCall.start(10, True)
