#!/usr/bin/python

import copy
import logging
import urlparse

from twisted.internet import defer
from twisted.internet import reactor

class Status:
  PREFIX = 'status://'

  class _StatusDeferred(defer.Deferred):

    def __init__(self, status, url, force_update=False):
      defer.Deferred.__init__(self)
      self._status = status
      self._url = url
      self._force_update = force_update

      self._value = status.get(url)

    def changed(self):
      return self._force_update or self._status.get(self._url) != self._value

    def value(self):
      return {
               'revision': self._status.revision(),
               'url': self._url,
               'status': self._status.get(self._url),
             }

  def __init__(self, config, log_handler, log_stream):
    self._revision = 1
    self._values = copy.deepcopy(config)

    self._notifications = []
    self._pending_notify = None

    self._log_handler = log_handler
    self._log_stream = log_stream

  def _parse_url(self, url):
    """status://foo/bar -> [foo, bar]"""
    self._validate_url(url)
    result = url[len(Status.PREFIX):].split('/')

    # Fixup the slightly broken results of split.
    if result == ['']:
      result = []

    return result

  def _validate_url(self, url):
    assert(url.startswith(Status.PREFIX))

  def _notify_handler(self):
    self._pending_notify = None
    for deferred in self._notifications[:]:
      if deferred.changed():
        self._notifications.remove(deferred)
        deferred.callback(deferred.value())

  def _notify(self):
    if self._notifications:
      # This small delay notifying clients allows multiple updates to
      # go through in a single notification.
      if not self._pending_notify:
        self._pending_notify = reactor.callLater(0.05, self._notify_handler)
      else:
        self._pending_notify.reset(0.05)

  def deferred(self, revision, url='status://'):
    """Create a deferred that's called when status is next updated.

       If an outdated revision is provided, we will call back right away.
       Otherwise, revision is ignored.
    """
    self._validate_url(url)
    force_update = revision != self.revision()

    d = self._StatusDeferred(self, url, force_update)
    self._notifications.append(d)

    if force_update:
      self._notify()

    return d

  def revision(self):
    return self._revision

  def get(self, url='status://', default_result=None):
    values = self._values
    keys = self._parse_url(url)

    try:
      for key in keys:
        values = values[key]
    except KeyError:
      values = default_result

    return copy.deepcopy(values)

  def set(self, url, update_value):
    values = self._values
    keys = self._parse_url(url)
    final_key = keys.pop()

    for key in keys:
      values = values[key]

    if final_key not in values or values[final_key] != update_value:
      # Increment our revision, and
      self._revision += 1

      # Set the new value
      values[final_key] = copy.deepcopy(update_value)

      # Notify listeners.
      logging.info('New revision %d', self.revision())
      self._notify()

  def get_log(self):
    self._log_handler.flush()
    result = {
      'revision': self.revision(),
      'log': self._log_stream.getvalue().split('\n'),
    }
    return result
