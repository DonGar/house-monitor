#!/usr/bin/python

import copy
import logging

from twisted.internet import defer
from twisted.internet import reactor

class Status:

  def __init__(self, log_handler, log_stream):
    self._values = { 'revision': 1 }
    self._notifications = []
    self._log_handler = log_handler
    self._log_stream = log_stream
    self._pending_notify = None

  def notify_handler(self):
    self._pending_notify = None
    for deferred in self._notifications[:]:
      deferred.callback(self)

  def notify(self):
    self._values['revision'] += 1
    logging.info('New revision %d', self.revision())

    # This small delay notifying clients allows multiple updates to
    # go through in a single notification.
    if not self._pending_notify:
      self._pending_notify = reactor.callLater(0.05, self.notify_handler)
    else:
      self._pending_notify.reset(0.05)

  def createNotification(self, revision=None):
    """Create a deferred that's called when status is next updated.

       If an outdated revision is provided, we will call back right away. Otherwise,
       revision is ignored.
    """
    d = defer.Deferred()

    # If revision specified and outdated, schedule an update callback shortly.
    if revision is not None and revision < self._values['revision']:
      reactor.callLater(0, d.callback, self)
    else:
      # Attach to our notifications list, and setup removal from list when needed.
      self._notifications.append(d)
      d.addBoth(self._notification_ended, d)

    return d

  def _notification_ended(self, result, deferred):
    self._notifications.remove(deferred)
    return result

  def revision(self):
    return self._values['revision']

  def _parse_uri(self, uri):
    """status://foo/bar -> [foo, bar]"""
    if uri is None:
      return []

    PREFIX = 'status://'
    assert(uri.startswith(PREFIX))
    return uri[len(PREFIX):].split('/')

  def get(self, uri=None):
    values = self._values
    keys = self._parse_uri(uri)

    for key in keys:
      values = values[key]

    return copy.deepcopy(values)

  def set(self, uri, update_values):
    values = self._values
    keys = self._parse_uri(uri)
    final_key = keys.pop()

    for key in keys:
      values = values[key]

    if final_key not in values or values[final_key] != update_values:
      values[final_key] = copy.deepcopy(update_values)
      self.notify()

  def get_log(self):
    self._log_handler.flush()
    result = {
      'revision': self.revision(),
      'log': self._log_stream.getvalue().split('\n'),
    }
    return result
