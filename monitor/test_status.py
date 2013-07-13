#!/usr/bin/python

import unittest

import monitor.status
import monitor.util.test_base

# pylint: disable=W0212


class TestStatusDeferred(monitor.util.test_base.TestBase):

  def test_status_deferred(self):
    status = self._create_status()

    d_no_force = monitor.status.Status._StatusDeferred(
        status,
        url='status://dict/sub1',
        force_update=False)
    d_force = monitor.status.Status._StatusDeferred(
        status,
        url='status://dict/sub1',
        force_update=True)

    # Test when status has not been updated at all.
    expected_value = {'revision': 1, 'url': 'status://dict/sub1', 'status': 3}

    self.assertFalse(d_no_force.changed())
    self.assertEqual(d_no_force.value(), expected_value)
    self.assertTrue(d_force.changed())
    self.assertEqual(d_force.value(), expected_value)

    # Test when status has an unreleated change.
    status.set('status://int', 12)
    expected_value = {'revision': 2, 'url': 'status://dict/sub1', 'status': 3}
    self.assertFalse(d_no_force.changed())
    self.assertEqual(d_no_force.value(), expected_value)
    self.assertTrue(d_force.changed())
    self.assertEqual(d_force.value(), expected_value)

    # Test when status has a releated noop change.
    status.set('status://dict/sub1', 3)
    expected_value = {'revision': 2, 'url': 'status://dict/sub1', 'status': 3}
    self.assertFalse(d_no_force.changed())
    self.assertEqual(d_no_force.value(), expected_value)
    self.assertTrue(d_force.changed())
    self.assertEqual(d_force.value(), expected_value)

    # Test when status has a releated change.
    status.set('status://dict/sub1', 4)
    expected_value = {'revision': 3, 'url': 'status://dict/sub1', 'status': 4}
    self.assertTrue(d_no_force.changed())
    self.assertEqual(d_no_force.value(), expected_value)
    self.assertTrue(d_force.changed())
    self.assertEqual(d_force.value(), expected_value)


class TestStatus(monitor.util.test_base.TestBase):

  def test_creation(self):
    """Verify handle_action with status and http URL strings."""
    status = self._create_status({})

    # If we start with nothing, we should end up with nothing but a revision
    # of 1.
    self.assertEqual(status._revision, 1)
    self.assertEqual(status._values, {})

  def test_get(self):
    status = self._create_status()

    self.assertEqual(status.get('status://'),
                     {'dict': {'sub1': 3, 'sub2': 4}, 'int': 2, 'list': []})
    self.assertEqual(status.get('status://nonexistant'), None)
    self.assertEqual(status.get('status://nonexistant', 'default'), 'default')
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

    self.assertEqual(status.revision(), 1)
    self.assertEqual(status.get('status://int'), 2)
    self.assertEqual(status.get('status://list'), [])
    self.assertEqual(status.get('status://dict'), {'sub1': 3, 'sub2': 4})

    # Revision didn't change with the gets.
    self.assertEqual(status.revision(), 1)

    # Set an integer
    status.set('status://int', 10)
    self.assertEqual(status.get('status://int'), 10)
    self.assertEqual(status.revision(), 2)

    # Set a complex structure, and ensure it is copied, not referenced.
    l = []
    status.set('status://list2', l)
    self.assertEqual(status.get('status://list2'), [])
    l.append(1)
    self.assertEqual(status.get('status://list2'), [])
    self.assertEqual(status.revision(), 3)

    # Ensure that setting to an unchanged value does not increment revision.
    status.set('status://int', 10)
    self.assertEqual(status.get('status://int'), 10)
    self.assertEqual(status.revision(), 3)

    # Set a nested value.
    status.set('status://dict/sub1', 5)
    self.assertEqual(status.get('status://dict/sub1'), 5)
    self.assertEqual(status.revision(), 4)


  def _expected_result(self, revision=1, url='status://', value=None):
    return { 'revision': revision,
             'url': url,
             'status': value }

  def test_notification_mismatch_revision_no_url(self):
    status = self._create_status({ 'int': 2 })

    d = status.deferred(0)
    d.addCallback(self.assertEquals,
                  self._expected_result(value={ 'int': 2 }))
    return d

  def test_notification_mismatch_revision_with_url(self):
    status = self._create_status({ 'int': 2 })

    url = 'status://int'
    d = status.deferred(0, url=url)
    d.addCallback(self.assertEquals,
                  self._expected_result(url=url, value=2))
    return d

  def test_notification_mismatch_revision_with_url_and_updates(self):
    status = self._create_status({ 'int': 2 })

    url = 'status://int'
    d = status.deferred(0, url=url)
    status.set(url, 3)
    d.addCallback(self.assertEquals,
                  self._expected_result(revision=2, url=url, value=3))
    return d

  def test_notification_single_change_no_url(self):
    status = self._create_status({ 'int': 2 })

    # Test that the expected notification fires after we make a change.
    d = status.deferred(revision=1)
    status.set('status://int', 3)
    d.addCallback(self.assertEquals,
                  self._expected_result(revision=2, value={'int': 3}))
    return d

  def test_notification_double_change_no_url(self):
    status = self._create_status({ 'int': 2 })

    # Make a couple of changes rapidly, and ensure we only fire with final
    # value.
    d = status.deferred(revision=1)
    status.set('status://int', 3)
    status.set('status://int', 4)
    d.addCallback(self.assertEquals,
                  self._expected_result(revision=3, value={'int': 4}))
    return d

  def test_notification_no_change(self):
    status = self._create_status({ 'int': 2 })

    d = status.deferred(revision=1)
    self._add_assert_timeout(d)
    return d

  def test_notification_noop_change(self):
    status = self._create_status({ 'int': 2 })

    # Make a couple of changes rapidly, and ensure we only fire once.
    d = status.deferred(revision=1)
    status.set('status://int', 2)
    self._add_assert_timeout(d)
    return d

  def test_notification_url(self):
    status = self._create_status()

    # Ask for a specialized notification.
    url = 'status://int'
    d = status.deferred(revision=1, url=url)
    status.set(url, 3)
    d.addCallback(self.assertEquals,
                  self._expected_result(revision=2, url=url, value=3))
    return d

  def test_notification_url_not_updated(self):
    status = self._create_status({ 'foo': 1, 'bar': 2 })

    # Ask for a specialized notification.
    d = status.deferred(revision=1, url='status://bar')
    status.set('status://int', 3)
    self._add_assert_timeout(d)
    return d


if __name__ == '__main__':
  unittest.main()
