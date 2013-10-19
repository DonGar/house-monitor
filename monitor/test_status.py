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
    contents = {
          'int': 2,
          'string': 'foo',
          'list': [],
          'dict': {'sub1': 3, 'sub2': 4},
        }

    status = self._create_status(contents)

    self.assertEqual(status.get('status://'), contents)
    self.assertEqual(status.get('status://nonexistant'), None)
    self.assertEqual(status.get('status://nonexistant', 'default'), 'default')
    self.assertEqual(status.get('status://int'), 2)
    self.assertEqual(status.get('status://string'), 'foo')
    self.assertEqual(status.get('status://string/foo'), None)
    self.assertEqual(status.get('status://list'), [])
    self.assertEqual(status.get('status://dict'), {'sub1': 3, 'sub2': 4})
    self.assertEqual(status.get('status://dict/sub1'), 3)

    # Ensure values copied out are copied, not referenced.
    l = status.get('status://list')
    l.append(1)
    self.assertEqual(status.get('status://list'), [])

  def test_get_matching(self):
    contents = {
      'match1': { 'foo': 1 },
      'match2': { 'foo': 2 },
      'solo1': { 'bar': 3 },
      'deep1': { 'sub_deep1': { 'foo': 4 },
                 'sub_deep2': { 'foo': 5 } },
      'deep2': { 'sub_deep1': { 'foo': 6 } },
      'string': 'foo',
      'list': []
    }

    status = self._create_status(contents)

    def _validate_result(url, expected_urls, expected_values):
      self.assertEqual(sorted(status.get_matching_urls(url)),
                       sorted(expected_urls))
      self.assertEqual(status.get_matching_values(url),
                       expected_values)

    _validate_result('status://',
                     ['status://'],
                     contents)
    _validate_result('status://string',
                     ['status://string'],
                     {'string': 'foo'})
    _validate_result('status://string/*',
                     [],
                     {})
    _validate_result('status://list',
                     ['status://list'],
                     {'list': []})
    _validate_result('status://list/*',
                     [],
                     {})
    _validate_result('status://match1',
                     ['status://match1'],
                     {'match1': {'foo': 1}})
    _validate_result('status://match1/foo',
                     ['status://match1/foo'],
                     {'match1': {'foo': 1}})
    _validate_result('status://*/foo',
                     ['status://match1/foo', 'status://match2/foo'],
                     {'match1': {'foo': 1}, 'match2': {'foo': 2}})
    _validate_result('status://*/bar',
                     ['status://solo1/bar'],
                     {'solo1': {'bar': 3}})
    _validate_result('status://*/sub_deep1/foo',
                     ['status://deep1/sub_deep1/foo',
                      'status://deep2/sub_deep1/foo'],
                     {'deep1': {'sub_deep1': {'foo': 4}},
                      'deep2': {'sub_deep1': {'foo': 6}}})
    _validate_result('status://deep1/*/foo',
                     ['status://deep1/sub_deep1/foo',
                      'status://deep1/sub_deep2/foo'],
                     {'deep1': {'sub_deep1': {'foo': 4},
                                'sub_deep2': {'foo': 5}}})
    _validate_result('status://*/*/foo',
                     ['status://deep1/sub_deep1/foo',
                      'status://deep1/sub_deep2/foo',
                      'status://deep2/sub_deep1/foo'],
                     {'deep1': {'sub_deep1': {'foo': 4},
                                'sub_deep2': {'foo': 5}},
                      'deep2': {'sub_deep1': {'foo': 6}}})

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

  def test_helpers(self):
    status = self._create_status(
        {
          'int': 2,
          'list': [],
          'dict': {'sub1': 3, 'sub2': 4},
          'nested': {'sub1': {'subsub1': 5, 'subsub2':6},
                     'sub2': {'subsub1': 7, 'subsub2':8}},
        })

    # _validate_url
    status._validate_url('status://')
    status._validate_url('status://foo')
    status._validate_url('status://foo/bar/widget')
    status._validate_url('status://*')
    status._validate_url('status://*/bar/widget/*')

    # _parse_url
    self.assertEqual(status._parse_url('status://'),
                     [])
    self.assertEqual(status._parse_url('status://foo'),
                     ['foo'])
    self.assertEqual(status._parse_url('status://foo/bar/widget'),
                     ['foo', 'bar', 'widget'])
    self.assertEqual(status._parse_url('status://*'),
                     ['*'])
    self.assertEqual(status._parse_url('status://*/bar/widget/*'),
                     ['*', 'bar', 'widget', '*'])

    # _join_url
    self.assertEqual(status._join_url([]),
                     'status://')
    self.assertEqual(status._join_url(['foo']),
                     'status://foo')
    self.assertEqual(status._join_url(['foo', 'bar', 'widget']),
                     'status://foo/bar/widget')
    self.assertEqual(status._join_url(['*']),
                     'status://*')
    self.assertEqual(status._join_url(['*', 'bar', 'widget', '*']),
                     'status://*/bar/widget/*')

    # _expand_wildcards
    self.assertEqual(status._expand_wildcards('status://'),
                     ['status://'])
    self.assertEqual(status._expand_wildcards('status://int'),
                     ['status://int'])
    self.assertEqual(status._expand_wildcards('status://not/present'),
                     [])
    self.assertEqual(status._expand_wildcards('status://not/present/*'),
                     [])
    self.assertEqual(status._expand_wildcards('status://int/*'),
                     [])
    self.assertEqual(sorted(status._expand_wildcards('status://*')),
                     sorted(['status://int',
                             'status://list',
                             'status://dict',
                             'status://nested']))
    self.assertEqual(sorted(status._expand_wildcards('status://dict/*')),
                     sorted(['status://dict/sub1',
                             'status://dict/sub2']))
    self.assertEqual(sorted(status._expand_wildcards('status://nested/*/*')),
                     sorted(['status://nested/sub1/subsub1',
                             'status://nested/sub1/subsub2',
                             'status://nested/sub2/subsub1',
                             'status://nested/sub2/subsub2']))
    self.assertEqual(
        sorted(status._expand_wildcards('status://nested/*/subsub1')),
        sorted(['status://nested/sub1/subsub1',
                'status://nested/sub2/subsub1']))


class TestStatusDeferred(monitor.util.test_base.TestBase):

  def test_mismatch_revision_no_url(self):
    status = self._create_status({ 'int': 2 })

    d = status.deferred(0)
    d.addCallback(self.assertEquals, ['status://'])

  def test_mismatch_revision_with_url(self):
    status = self._create_status({ 'int': 2 })

    url = 'status://int'
    d = status.deferred(0, url=url)
    d.addCallback(self.assertEquals, [url])

  def test_single_change_no_url(self):
    status = self._create_status({ 'int': 2 })

    # Test that the expected notification fires after we make a change.
    url = 'status://int'
    d = status.deferred()
    status.set(url, 3)
    d.addCallback(self.assertEquals, ['status://'])

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
    d.addCallback(self.assertEquals, [url])

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
    d.addCallback(self.assertEquals, [url])


if __name__ == '__main__':
  unittest.main()
