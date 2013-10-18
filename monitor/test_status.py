#!/usr/bin/python

import unittest

import monitor.status
import monitor.util.test_base

# pylint: disable=W0212


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

  def test_get_matching(self):
    value = {
      'match1': { 'foo': 1 },
      'match2': { 'foo': 2 },
      'solo1': { 'bar': 3 },
      'deep1': { 'sub_deep1': { 'foo': 4 },
                 'sub_deep2': { 'foo': 5 } },
      'deep2': { 'sub_deep1': { 'foo': 6 } }
    }

    status = self._create_status(value)

    def _validate_result(url, expected):
      self.assertEqual(sorted(status.get_matching(url)),
                       sorted(expected))

    _validate_result('status://',
                     [{
                        'revision': 1,
                        'url': 'status://',
                        'status': {
                          'match1': { 'foo': 1 },
                          'match2': { 'foo': 2 },
                          'solo1': { 'bar': 3 },
                          'deep1': { 'sub_deep1': { 'foo': 4 },
                                     'sub_deep2': { 'foo': 5 } },
                          'deep2': { 'sub_deep1': { 'foo': 6 } }
                        }
                      }])
    _validate_result('status://match1',
                     [{
                        'revision': 1,
                        'url': 'status://match1',
                        'status': { 'foo': 1 }
                      }])
    _validate_result('status://match1/foo',
                     [{
                        'revision': 1,
                        'url': 'status://match1/foo',
                        'status': 1
                      }])
    _validate_result('status://*/foo',
                     sorted([{
                        'revision': 1,
                        'url': 'status://match1/foo',
                        'status': 1
                      },{
                        'revision': 1,
                        'url': 'status://match2/foo',
                        'status': 2
                      }]))
    _validate_result('status://*/bar',
                     [{
                        'revision': 1,
                        'url': 'status://solo1/bar',
                        'status': 3
                      }])
    _validate_result('status://*/sub_deep1/foo',
                     [{
                        'revision': 1,
                        'url': 'status://deep1/sub_deep1/foo',
                        'status': 4
                      },
                      {
                        'revision': 1,
                        'url': 'status://deep2/sub_deep1/foo',
                        'status': 6
                      }])
    _validate_result('status://deep1/*/foo',
                     [{
                        'revision': 1,
                        'url': 'status://deep1/sub_deep1/foo',
                        'status': 4
                      },
                      {
                        'revision': 1,
                        'url': 'status://deep1/sub_deep2/foo',
                        'status': 5
                      }])
    _validate_result('status://*/*/foo',
                     [{
                        'revision': 1,
                        'url': 'status://deep1/sub_deep1/foo',
                        'status': 4
                      },
                      {
                        'revision': 1,
                        'url': 'status://deep1/sub_deep2/foo',
                        'status': 5
                      },
                      {
                        'revision': 1,
                        'url': 'status://deep2/sub_deep1/foo',
                        'status': 6
                      }])

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

    # Set a nested value with new intermediate paths.
    status.set('status://nest1/nest2/nest3', 'foo')
    self.assertEqual(status.get('status://nest1'),
                     {'nest2': {'nest3': 'foo' }})
    self.assertEqual(status.revision(), 5)

  def test_set_revision(self):
    """Test Status.set() if revision is passed in."""
    status = self._create_status()

    # Set a new value, update with correct specified revision.
    status.set('status://int', 10, revision=1)
    self.assertEqual(status.revision(), 2)

    # Set a new value, update with incorrect specified revision.
    # Should raise exception, and modify nothing.
    self.assertRaises(monitor.status.RevisionMismatch,
                      status.set, 'status://int', 20, revision=1)
    self.assertEqual(status.get('status://int'), 10)
    self.assertEqual(status.revision(), 2)


class TestStatusDeferred(monitor.util.test_base.TestBase):


  def test_deferred_class(self):
    status = self._create_status()

    deferred = monitor.status.Status._Deferred(
        status,
        url='status://dict/sub1')

    # Test when status has not been updated at all.
    self.assertFalse(deferred.changed())
    self.assertEqual(deferred.value(),
                     {'revision': 1, 'url': 'status://dict/sub1', 'status': 3})

    # Test when status has an unreleated change.
    status.set('status://int', 12)
    self.assertFalse(deferred.changed())
    self.assertEqual(deferred.value(),
                     {'revision': 2, 'url': 'status://dict/sub1', 'status': 3})

    # Test when status has a releated noop change.
    status.set('status://dict/sub1', 3)
    self.assertFalse(deferred.changed())
    self.assertEqual(deferred.value(),
                     {'revision': 2, 'url': 'status://dict/sub1', 'status': 3})

    # Test when status has a releated change.
    status.set('status://dict/sub1', 4)
    self.assertTrue(deferred.changed())
    self.assertEqual(deferred.value(),
                     {'revision': 3, 'url': 'status://dict/sub1', 'status': 4})

  def test_mismatch_revision_no_url(self):
    status = self._create_status({ 'int': 2 })

    d = status.deferred(0)
    d.addCallback(self.assertEquals,
                  { 'revision': 1, 'url': 'status://', 'status':{ 'int': 2 } })

  def test_mismatch_revision_with_url(self):
    status = self._create_status({ 'int': 2 })

    url = 'status://int'
    d = status.deferred(0, url=url)
    d.addCallback(self.assertEquals,
                  { 'revision': 1, 'url': url, 'status': 2})

  def test_single_change_no_url(self):
    status = self._create_status({ 'int': 2 })

    # Test that the expected notification fires after we make a change.
    url = 'status://int'
    d = status.deferred()
    status.set(url, 3)
    d.addCallback(self.assertEquals,
                  { 'revision': 2, 'url': 'status://', 'status': {'int': 3} })

  def test_no_change(self):
    status = self._create_status({ 'int': 2 })

    d = status.deferred(revision=1)
    self.assertFalse(d.called)

  def test_default_revision(self):
    status = self._create_status({ 'int': 2 })

    d = status.deferred()
    self.assertFalse(d.called)

  def test_noop_change(self):
    status = self._create_status({ 'int': 2 })

    # Make a couple of changes rapidly, and ensure we only fire once.
    d = status.deferred(revision=1)
    status.set('status://int', 2)
    self.assertFalse(d.called)

  def test_url(self):
    status = self._create_status()

    # Ask for a specialized notification.
    url = 'status://int'
    d = status.deferred(revision=1, url=url)
    status.set(url, 3)
    d.addCallback(self.assertEquals,
                  { 'revision': 2, 'url': url, 'status': 3 })

  def test_url_not_updated(self):
    status = self._create_status({ 'foo': 1, 'bar': 2 })

    # Ask for a specialized notification.
    d = status.deferred(revision=1, url='status://bar')
    status.set('status://int', 3)
    self.assertFalse(d.called)

  def test_non_existent_url(self):
    status = self._create_status()

    # Ask for a specialized notification.
    url = 'status://foo'
    d = status.deferred(url=url)
    status.set(url, 3)
    d.addCallback(self.assertEquals,
                  { 'revision': 2, 'url': url, 'status': 3 })


if __name__ == '__main__':
  unittest.main()
