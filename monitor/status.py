#!/usr/bin/python

import copy
import logging

from twisted.internet import defer

PREFIX = 'status://'


class BadUrl(Exception):
  """Raised when a status url isn't valid."""

class UnknownUrl(Exception):
  """Raised when a status url isn't valid."""

class RevisionMismatch(Exception):
  """Raised when an operation can't compelete because of mismatch revision."""


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

  def revision(self):
    return self._revision

  def get(self, url='status://', default_result=None):
    try:
      keys = self._parse_url(url)
      return copy.deepcopy(self._get_values_by_keys(keys))
    except UnknownUrl:
      return default_result

  def get_matching_urls(self, url):
    """Accept urls with wild cards.

    Returns:
      A list of URLs that exist in status and match the wild card pattern.
    """
    return self._expand_wildcards(url)

  def get_matching_values(self, url):
    """Accept urls with wild cards.

    Returns:
      A copy of status will all content not matching the request URL stripped.
    """
    result = Status()

    for u in self.get_matching_urls(url):
      result.set(u, self.get(u))

    return result.get()

  def set(self, url, update_value, revision=None):

    if revision is not None and revision != self._revision:
      raise RevisionMismatch('%d received, %d current' %
                             (revision, self._revision))

    # The special case of setting the top level node.
    if url == PREFIX:
      self._values = copy.deepcopy(update_value)
      self._notify()
      return

    values = self._values
    keys = self._parse_url(url)
    final_key = keys.pop()

    for key in keys:
      if key not in values:
        values[key] = {}

      values = values[key]

    if final_key not in values or values[final_key] != update_value:
      self._revision += 1
      values[final_key] = copy.deepcopy(update_value)

      # Notify listeners.
      logging.debug('Status revision %d: %s -> %s',
                    self.revision(), update_value, url)
      self._notify()

  def deferred(self, revision=None, url='status://'):
    """Create a deferred that's called when status is next updated.

       If an outdated revision is provided, we will call back right away.
       Otherwise, revision is ignored.
    """
    deferred = self._Deferred(self, url)
    self._save_deferred(deferred, revision)
    return deferred

  def _validate_url(self, url):
    if not url.startswith(PREFIX):
      raise BadUrl(url)

  def _parse_url(self, url):
    """status://foo/bar -> [foo, bar]"""
    self._validate_url(url)
    result = url[len(PREFIX):].split('/')

    # Fixup empty string results to be empty.
    if result == ['']:
      result = []

    return result

  def _join_url(self, keys):
    """Inverse of _parse_url."""
    return PREFIX + '/'.join(keys)

  def _get_values_by_keys(self, keys):
    """Look up the raw values for a url.

    Raises:
      UnknownUrl if any key doesn't exist.
    """
    values = self._values

    for key in keys:
      try:
        values = values[key]
      except (KeyError, TypeError):
        raise UnknownUrl()

    return values

  def _expand_wildcards(self, url):
    urls = [url]
    result = []

    # For each url in urls, we look to see if it contains any wild cards.
    # If not, we look to see if it exists in our values. If it does, add
    # to results.
    #
    # If the url contains a wildcard, expand it, and add all discovered urls
    # back to the urls list to start over. This expands any additional wild
    # cards, and tests for existence of the fully expanded urls.
    while urls:
      keys = self._parse_url(urls.pop())
      try:
        index = keys.index('*')
      except ValueError:
        # There is no wildcard in the URL.
        try:
          self._get_values_by_keys(keys)
        except UnknownUrl:
          # URL doesn't exist, skip it.
          continue

        # We found a concrete URL that exists, it's a result.
        result.append(self._join_url(keys))
        continue

      pre_wildcard_keys = keys[:index]
      post_wildcard_keys = keys[index+1:]
      try:
        wildcard_node = self._get_values_by_keys(pre_wildcard_keys)
      except UnknownUrl:
        # partial URL doesn't exist, skip it.
        continue

      try:
        for expanded_key in wildcard_node.keys():
          urls.append(self._join_url(pre_wildcard_keys +
                                     [expanded_key] +
                                     post_wildcard_keys))
      except AttributeError:
        # The wildcard_node isn't a dictionary, can't expand it.
        continue

    return result

  def _save_deferred(self, deferred, revision):

    def _remove_callback(value):
      self._notifications.remove(deferred)
      return value

    deferred.addCallback(_remove_callback)
    self._notifications.append(deferred)

    if revision is not None and revision != self.revision():
      # Send event right away.
      deferred.issue_callback()

  def _notify(self):
    # Look for deferreds that need to fire.
    for d in self._notifications[:]:
      if d.changed():
        d.issue_callback()

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
      self._value = self._status.get_matching_values(self._url)

    def changed(self):
      return self._value != self._status.get_matching_values(self._url)

    def issue_callback(self):
      self.callback(self._status.get_matching_urls(self._url))
