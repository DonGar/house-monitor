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

class _Node(object):
  def __init__(self, revision, value):
    self.revision = revision
    self._content = self._value_to_content(value)
    assert not isinstance(value, _Node)

  def _value_to_content(self, value):
    """Convert a status struct to nested _Node values (content).

    Dictionary values have each sub-value converted to a node. Other a values
    simply go through a deepcpoy (only needed for list values).
    """
    assert not isinstance(value, _Node)
    dict_iteritems = None
    try:
      dict_iteritems = value.iteritems()
    except AttributeError:
      # Handle everything but dict.
      return copy.deepcopy(value)

    result = {}
    for key, subvalue in dict_iteritems:
      assert isinstance(key, basestring)
      result[key] = _Node(self.revision, subvalue)
    return result

  def to_value(self):
    """Convert content (_Node structure) to simple values.

    Dictionary values have each sub-node converted to a values. Other a values
    simply go through a deepcpoy (only needed for list values).
    """
    assert not isinstance(self._content, _Node)

    if self.is_dict():
      return {key: subvalue.to_value()
              for key, subvalue in self._content.iteritems()}
    else:
      # Copy plain values that were already unpacked.
      return copy.deepcopy(self._content)

  def is_dict(self):
    return isinstance(self._content, dict)

  def add_child(self, key, value):
    assert isinstance(key, basestring)
    assert self.is_dict()

    new_node = _Node(self.revision, value)
    self._content[key] = new_node
    return new_node

  def remove_child(self, key):
    assert isinstance(key, basestring)
    assert self.is_dict()

    del self._content[key]

  def child(self, key):
    assert isinstance(key, basestring)
    assert self.is_dict()

    return self._content[key]

  def children(self):
    assert self.is_dict()
    return self._content.keys()

  def __repr__(self):
    return '%s(0x%s): rev: %s - contents: %s' % (type(self),
                                                 id(self),
                                                 self.revision,
                                                 self._content)

#
# See 'status' variable at the end.
#

class Status(object):

  def __init__(self, value=None):
    if value is None:
      value = {}

    self._node = _Node(revision=1, value=value)
    self._notifications = set()

  def revision(self, url='status://'):
    """Return the current revision of the system status.

    This number starts 1 one at startup, and increases monotonically with
    every change.
    """
    keys = self._parse_url(url)
    return self._get_node_by_keys(keys).revision

  def get(self, url='status://', default_result=None):
    """Fetch a subtree from the status."""
    try:
      keys = self._parse_url(url)
      return self._get_node_by_keys(keys).to_value()
    except UnknownUrl:
      return default_result

  def get_matching_urls(self, url):
    """Accept urls with wild cards.

    Returns:
      A list of URLs that exist in status and match the wild card pattern.
    """
    return self._expand_wildcards(url)

  def set(self, url, update_value, revision=None):
    """Change the value of a status subtree.

    Will create parent dictionaries as needed to satisfy the URL.
    """
    keys = self._parse_url(url)

    # Partial is okay, because we'll create missing nodes later.
    nodes = self._get_nodes_by_keys(keys, partial_okay=True)

    # If there is a specified revision, it must exactly match revisions of
    # the target node, or any of it's parents.
    if revision is not None:
      if revision not in [n.revision for n in nodes]:
        raise RevisionMismatch('%d received, %d current' %
                               (revision, self.revision()))

    # Test to see if new value is a change.
    try:
      if self.get(url) == update_value:
        return
    except UnknownUrl:
      pass

    # We've decided we can set, update existing revisions.
    new_revision = self.revision() + 1
    for node in nodes:
      node.revision = new_revision

    # Ensure any missing predecessor nodes are present.
    for i in xrange(len(keys)-1):
      key, node = keys[i], nodes[i]
      if not key in node.children():
        nodes.append(node.add_child(key, {}))

    # Remove the node we are replacing, if present.
    if len(nodes) > len(keys):
      nodes.pop()

    # Nodes contains the root node, which has no matching key, but is
    # missing the final node, which does.
    assert len(keys) == len(nodes)

    nodes[-1].add_child(keys[-1], update_value)

    # Notify listeners.
    logging.debug('Status revision %d: %s -> %s',
                  self.revision(), update_value, url)

    self._notify()
    return update_value

  def deferred(self, revision=None, url='status://'):
    """Create a deferred that's called when status is next updated.

       If an outdated revision is provided, we will call back right away.
       Otherwise, revision is ignored.

       The deferred value (when fired) will be a list of URLs that match
       the URL passed in (wildcards accepted),
    """
    deferred = self._Deferred(self, url)

    if revision is not None and revision != self.revision(url):
      # Send event right away.
      deferred.issue_callback()
    else:
      # Save it off, so we can send it later.
      self._notifications.add(deferred)



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

  def _get_node_by_keys(self, keys):
    """Look up the raw values for a url.

    Raises:
      UnknownUrl if any key doesn't exist.
    """
    return self._get_nodes_by_keys(keys)[-1]

  def _get_nodes_by_keys(self, keys, partial_okay=False):
    """Look up the raw values for a url.

    Raises:
      UnknownUrl if any key doesn't exist.
    """
    node = self._node
    result = [node]

    for key in keys:
      try:
        if not node.is_dict():
          # If we try to step into a node without a dict parent, it's a BadUrl.
          raise BadUrl(self._join_url(keys))

        node = node.child(key)
        result.append(node)
      except KeyError:
        if partial_okay:
          break
        else:
          raise UnknownUrl(self._join_url(keys))

    return result

  def _expand_wildcards(self, url):
    """Return a list of URLs which exist and match url with wildcards expanded.

    May return an empty list if a single url is passed in which does not exist.
    """
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
          self._get_node_by_keys(keys)
        except (UnknownUrl, BadUrl):
          # URL doesn't exist, skip it.
          continue

        # We found a concrete URL that exists, it's a result.
        result.append(self._join_url(keys))
        continue

      pre_wildcard_keys = keys[:index]
      post_wildcard_keys = keys[index+1:]
      try:
        wildcard_node = self._get_node_by_keys(pre_wildcard_keys)
      except UnknownUrl:
        # partial URL doesn't exist, skip it.
        continue

      if not wildcard_node.is_dict():
        # The wildcard_node isn't a dictionary, can't expand it.
        continue

      for expanded_key in wildcard_node.children():
        urls.append(self._join_url(pre_wildcard_keys +
                                   [expanded_key] +
                                   post_wildcard_keys))

    return result

  def _notify(self):
    """Look for deferreds that need to fire."""
    # Firing a deferred can modify (add or remove) our set of notifications
    # underneath us.
    for d in self._notifications.copy():
      # If the deferred was handled in a nested call and removed...
      #   skip it.
      if d not in self._notifications:
        continue

      if d.changed():
        self._notifications.remove(d)
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
      self._watching = self._find_revisions()

    def changed(self):
      return self._watching != self._find_revisions()

    def issue_callback(self):
      self.callback(self._status.get_matching_urls(self._url))

    def _find_revisions(self):
      result = {}
      urls = self._status.get_matching_urls(self._url)
      for url in urls:
        try:
          result[url] = self._status.revision(url)
        except UnknownUrl:
          result[url] = None
      return result
