#!/usr/bin/python

import copy
import logging

from twisted.internet import defer
from twisted.internet import reactor

PREFIX = 'status://'

#
# See 'status' variable at the end.
#

class Status:

  def __init__(self, value=None):
    if value is None:
      value = {}

    self._revision = 1
    self._values = copy.deepcopy(value)
    self._notifications = []
    self._pending_notify = None

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

  def get_matching(self, url):
    """Accept urls with wild cards. Ie: status://*/button."""


    def _get_matching_recurse(url, values, keys):

      # If there are no keys left, we are done looking up.
      if not keys:
        return [{ 'url': url, 'status': values, 'revision': self.revision()}]

      # If the first key is a wild card, replace it with every possible value
      # and add up tghe results.
      if keys[0] == '*':
        result = []
        for key in values.keys():
          result += _get_matching_recurse(url, values, [key] + keys[1:])
        return result

      if len(keys) > 0:
        key = keys[0]

        try:
          if key in values.keys():
            # Recurse down on this key.
            if not url.endswith('/'):
              url += '/'
            url += key
            values = values[key]
            return _get_matching_recurse(url, values, keys[1:])
        except AttributeError:
          # This means that values didn't have 'keys', and so wasn't a dict.
          pass

      # Didn't find anything.
      return []



    values = self._values
    keys = self._parse_url(url)

    return _get_matching_recurse(PREFIX, values, keys)

  def set(self, url, update_value):
    values = self._values
    keys = self._parse_url(url)
    final_key = keys.pop()

    for key in keys:
      if key not in values:
        values[key] = {}

      values = values[key]

    if final_key not in values or values[final_key] != update_value:
      # Increment our revision, and
      self._revision += 1

      # Set the new value
      values[final_key] = copy.deepcopy(update_value)

      # Notify listeners.
      logging.info('New revision %d', self.revision())
      self._notify()

  def deferred(self, revision=0, url='status://'):
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

  def _parse_url(self, url):
    """status://foo/bar -> [foo, bar]"""
    self._validate_url(url)
    result = url[len(PREFIX):].split('/')

    # Fixup the slightly broken results of split.
    if result == ['']:
      result = []

    return result

  def _validate_url(self, url):
    assert(url.startswith(PREFIX))

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

  class _StatusDeferred(defer.Deferred):
    """Helper class for watching part of the status to see if it was updated.

    This is a deferred with helpers (for use by Status only) to help figure
    out if it's time for it to call back or not, and what value to send to
    the callback.
    """

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
