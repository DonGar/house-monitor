#!/usr/bin/python

import unittest
import mock

from twisted.internet import task
from twisted.internet import reactor

import twisted.trial.unittest

import monitor.status

# pylint: disable=W0212

class TestStatusBase(twisted.trial.unittest.TestCase):

  def _create_status(self, values=None):
    if values is None:
      values = {
        'int': 2,
        'list': [],
        'dict': {'sub1': 3, 'sub2': 4},
      }

    return monitor.status.Status(values, None, None)


# class TestStatusDeferred(TestStatusBase):

#   def test_url_match(self):
#     status = self._create_status({
#         'int': 2,
#         'list': [],
#         'dict': {'sub1': {'sub2': 1}},
#       })

#     d = monitor.status.StatusDeferred('status://dict/sub1')
#     self.assertTrue(d.changed('status://dict'))
#     self.assertTrue(d.match_url('status://dict/sub1/foo'))
#     self.assertTrue(d.match_url('status://dict/sub1/sub2'))
#     self.assertFalse(d.match_url('status://bar'))

#   def test_url_match_none(self):
#     status = self._create_status()
#     d = monitor.status.StatusDeferred(None)
#     self.assertTrue(d.match_url('status://bar'))


class TestStatus(TestStatusBase):

  def _add_assert_timeout(self, d):
    # timeout is a unique object guaranteed different from any other result.
    timeout = object()
    d.addCallback(self.assertIs, timeout)
    reactor.callLater(0.5, d.callback, timeout)

  def test_creation(self):
    """Verify handle_action with status and http URL strings."""
    status = self._create_status({})

    # If we start with nothing, we should end up with nothing but a revision
    # of 1.
    self.assertEqual(status._values, {'revision': 1})

  def test_get(self):
    status = self._create_status()

    self.assertEqual(status.get('status://revision'), 1)
    self.assertEqual(status.get('status://int'), 2)
    self.assertEqual(status.get('status://list'), [])
    self.assertEqual(status.get('status://dict'), {'sub1': 3, 'sub2': 4})
    self.assertEqual(status.get('status://dict/sub1'), 3)

    # Ensure values copied out are copied, not referenced.
    l = status.get('status://list')
    l.append(1)
    self.assertEqual(status.get('status://list'), [])

  def test_set(self):
    status = self._create_status()

    self.assertEqual(status.get('status://revision'), 1)
    self.assertEqual(status.get('status://int'), 2)
    self.assertEqual(status.get('status://list'), [])
    self.assertEqual(status.get('status://dict'), {'sub1': 3, 'sub2': 4})

    # Revision didn't change with the gets.
    self.assertEqual(status.get('status://revision'), 1)

    # Set an integer
    status.set('status://int', 10)
    self.assertEqual(status.get('status://int'), 10)
    self.assertEqual(status.get('status://revision'), 2)

    # Set a complex structure, and ensure it is copied, not referenced.
    l = []
    status.set('status://list2', l)
    self.assertEqual(status.get('status://list2'), [])
    l.append(1)
    self.assertEqual(status.get('status://list2'), [])
    self.assertEqual(status.get('status://revision'), 3)

    # Ensure that setting to an unchanged value does not increment revision.
    status.set('status://int', 10)
    self.assertEqual(status.get('status://int'), 10)
    self.assertEqual(status.get('status://revision'), 3)

    # Set a nested value.
    status.set('status://dict/sub1', 5)
    self.assertEqual(status.get('status://dict/sub1'), 5)
    self.assertEqual(status.get('status://revision'), 4)

  def test_notification_mismatch_revision_no_url(self):
    status = self._create_status({ 'int': 2 })

    d = status.createNotification(0)
    d.addCallback(self.assertEquals, {
        'revision': 1,
        'int': 2,
      })
    return d

  def test_notification_mismatch_revision_with_url(self):
    status = self._create_status({ 'int': 2 })

    d = status.createNotification(0, url='status://int')
    d.addCallback(self.assertEquals, 2)
    return d

  def test_notification_mismatch_revision_with_url_and_updates(self):
    status = self._create_status({ 'int': 2 })

    d = status.createNotification(0, url='status://int')
    status.set('status://int', 3)
    d.addCallback(self.assertEquals, 3)
    return d

  def test_notification_single_change_no_url(self):
    status = self._create_status({ 'int': 2 })

    # Test that the expected notification fires after we make a change.
    d = status.createNotification(revision=1)
    status.set('status://int', 3)
    d.addCallback(self.assertEquals, {
        'revision': 2,
        'int': 3,
      })
    return d

  def test_notification_double_change_no_url(self):
    status = self._create_status({ 'int': 2 })

    # Make a couple of changes rapidly, and ensure we only fire with final
    # value.
    d = status.createNotification(revision=1)
    status.set('status://int', 3)
    status.set('status://int', 4)
    d.addCallback(self.assertEquals, {
        'revision': 3,
        'int': 4,
      })
    return d

  def test_notification_no_change(self):
    status = self._create_status({ 'int': 2 })

    d = status.createNotification(revision=1)
    self._add_assert_timeout(d)
    return d

  def test_notification_noop_change(self):
    status = self._create_status({ 'int': 2 })

    # Make a couple of changes rapidly, and ensure we only fire once.
    d = status.createNotification(revision=1)
    status.set('status://int', 2)
    self._add_assert_timeout(d)
    return d

  def test_notification_url(self):
    status = self._create_status()

    # Ask for a specialized notification.
    d = status.createNotification(revision=1, url='status://int')
    status.set('status://int', 3)
    d.addCallback(self.assertEquals, 3)
    return d

  def test_notification_url_not_updated(self):
    status = self._create_status({ 'foo': 1, 'bar': 2 })

    # Ask for a specialized notification.
    d = status.createNotification(revision=1, url='status://bar')
    status.set('status://int', 3)
    self._add_assert_timeout(d)
    return d


if __name__ == '__main__':
  unittest.main()
