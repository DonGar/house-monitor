#!/usr/bin/python

import logging

from twisted.internet import defer
from twisted.internet import reactor

class Status:

  def __init__(self, log_handler, log_stream):
    self._values = {}
    self._notifications = []
    self._revision = 1
    self._log_handler = log_handler
    self._log_stream = log_stream

  def update(self, updates):
    notify = False

    for key, value in updates.iteritems():
      if key not in self._values or value != self._values[key]:
        notify = True
        self._values[key] = value

    if notify:
      self._revision += 1
      logging.info('New revision %d', self._revision)

      # This small delay notifying clients allows multiple updates to
      # go through in a single notification.
      reactor.callLater(0.05, self.notify)

  def notify(self):
    for deferred in self._notifications[:]:
      deferred.callback(self)

  def createNotification(self, revision=None):
    """Create a deferred that's called when status is next updated.

       If an outdated revision is provided, we will call back right away. Otherwise,
       revision is ignored.
    """
    d = defer.Deferred()

    # If revision specified and outdated, schedule an update callback shortly.
    if revision is not None and revision < self._revision:
      reactor.callLater(0, d.callback, self)
    else:
      # Attach to our notifications list, and setup removal from list when needed.
      self._notifications.append(d)
      d.addBoth(self._notification_ended, d)

    return d

  def _notification_ended(self, result, deferred):
    self._notifications.remove(deferred)
    return result

  def get_values(self):
    result = self._values.copy()
    result['revision'] = self._revision
    return result

  def get_log(self):
    self._log_handler.flush()
    return self._log_stream.getvalue().split('\n')
