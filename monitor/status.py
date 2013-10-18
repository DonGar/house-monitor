#!/usr/bin/python

import copy
import logging
import os

from twisted.internet import defer

PREFIX = 'status://'

#
# See 'status' variable at the end.
#

class Status(object):

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
      if len(keys) == 0:
        return [{ 'url': url,
                  'status': copy.deepcopy(values),
                  'revision': self.revision()
                }]

      try:
        key = keys[0]

        # If the first key is a wild card, replace it with every possible value
        # and add up tghe results.
        if key == '*':
          result = []
          for match_key in values.keys():
            result += _get_matching_recurse(url, values, [match_key] + keys[1:])
          return result

        # If we have keys left, and it's not a wild card, do normal expansion.
        if key in values.keys():
          url = os.path.join(url, key)
          return _get_matching_recurse(url, values[key], keys[1:])

      except AttributeError:
        # This means values wasn't a dict. Can't find things in it.
        pass

      # Didn't find anything.
      return []

    return _get_matching_recurse(PREFIX, self._values, self._parse_url(url))

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
      logging.info('Status revision %d: %s -> %s',
                   self.revision(), update_value, url)
      self._notify()

  def deferred(self, revision=None, url='status://'):
    """Create a deferred that's called when status is next updated.

       If an outdated revision is provided, we will call back right away.
       Otherwise, revision is ignored.
    """
    self._validate_url(url)
    deferred = self._Deferred(self, url)

    if revision is not None and revision != self.revision():
      # Send event right away.
      deferred.callback(deferred.value())
    else:
	  # Setup for later notification.
      self._notifications.append(deferred)

    return deferred

  def _parse_url(self, url):
    """status://foo/bar -> [foo, bar]"""
    self._validate_url(url)
    result = url[len(PREFIX):].split('/')

    # Fixup empty string results to be empty.
    if result == ['']:
      result = []

    return result

  def _validate_url(self, url):
    assert(url.startswith(PREFIX))

  def _notify(self):
    self._pending_notify = None
    for deferred in self._notifications[:]:
      if deferred.changed():
        self._notifications.remove(deferred)
        deferred.callback(deferred.value())

  class _Deferred(defer.Deferred):
    """Helper class for watching part of the status to see if it was updated.

    This is a deferred with helpers (for use by Status only) to help figure
    out if it's time for it to call back or not, and what value to send to
    the callback.
    """
    def __init__(self, status, url):
      defer.Deferred.__init__(self)
      self._status = status
      self._url = url

      self._value = self._status.get(self._url)

    def changed(self):
      return self._value != self._status.get(self._url)

    def value(self):
      return {
               'url': self._url,
               'status': self._status.get(self._url),
               'revision': self._status.revision(),
             }
