#!/usr/bin/python

import json
import unittest

import monitor.status
import monitor.util.test_base

# pylint: disable=protected-access

class TestNode(monitor.util.test_base.TestBase):

  def test_identity(self):
    """Test that we can put values into Nodes, and get the same values back."""
    def ident_helper(value):
      node = monitor.status._Node(12, value)
      self.assertEqual(node.revision, 12)
      extract = node.to_value()
      self.assertEqual(extract, value)

    ident_helper(None)
    ident_helper(14)
    ident_helper('foo')
    ident_helper([1, 2, 3])
    ident_helper({})
    ident_helper({'foo': 1, 'bar': 2})
    ident_helper({'foo': 1, 'sub': {'subsub': 'inner_value'}})
    ident_helper({'foo': 1, 'sub': {'subsub': {'subsubsub': None}}})
    ident_helper({'foo': 1, 'sub': {'subsub': {'subsubsub': None,
                                               'subsubsub2': 3}}})
    ident_helper({'server': {'email_address': 'server@address.com'}})

  def test_json_identity(self):
    """Json types can be a little different. Make sure we don't care."""
    contents_str = """
    {
        "none": null,
        "int": 2,
        "string": "foo",
        "list": [5, 6, 7],
        "dict": {"sub1": 3, "sub2": 4}
    }
    """
    contents_parsed = json.loads(contents_str)
    contents_node = monitor.status._Node(12, contents_parsed)

    # Make sure the contents decode the way we expect.
    self.assertEqual(
        contents_node.to_value(),
        {
            'none': None,
            'int': 2,
            'string': 'foo',
            'list': [5, 6, 7],
            'dict': {'sub1': 3, 'sub2': 4},
        })

    # Make sure we can look up from a standard string name.
    self.assertEqual(contents_node.child('int').to_value(), 2)

  def test_is_dict(self):
    self.assertTrue(monitor.status._Node(12, {}).is_dict())
    self.assertFalse(monitor.status._Node(12, 1).is_dict())
    self.assertFalse(monitor.status._Node(12, []).is_dict())
    self.assertFalse(monitor.status._Node(12, 'foo').is_dict())
    self.assertFalse(monitor.status._Node(12, None).is_dict())

  def test_node_child_methods(self):
    # Create an empty node to test with.
    node = monitor.status._Node(12, {})
    self.assertEqual(node.children(), [])
    self.assertEqual(node.revision, 12)

    # Test adding a child to an empty node.
    node.add_child('foo', 1)
    self.assertEqual(node.to_value(), {'foo': 1})
    self.assertEqual(node.child('foo').to_value(), 1)
    self.assertEqual(node.child('foo').revision, node.revision)
    self.assertEqual(node.children(), ['foo'])

    # Add a second child.
    node.add_child('bar', 2)
    self.assertEqual(node.to_value(), {'foo': 1, 'bar': 2})
    self.assertEqual(node.child('foo').to_value(), 1)
    self.assertEqual(node.child('bar').to_value(), 2)
    self.assertEqual(node.child('foo').revision, node.revision)
    self.assertEqual(node.child('bar').revision, node.revision)
    self.assertEqual(node.children(), ['foo', 'bar'])

    # Replace a child.
    node.add_child('bar', 3)
    self.assertEqual(node.to_value(), {'foo': 1, 'bar': 3})
    self.assertEqual(node.child('foo').to_value(), 1)
    self.assertEqual(node.child('bar').to_value(), 3)
    self.assertEqual(node.child('foo').revision, node.revision)
    self.assertEqual(node.child('bar').revision, node.revision)
    self.assertEqual(node.children(), ['foo', 'bar'])

    # Remove a child.
    node.remove_child('bar')
    self.assertEqual(node.to_value(), {'foo': 1})
    self.assertEqual(node.child('foo').to_value(), 1)
    self.assertEqual(node.child('foo').revision, node.revision)
    self.assertEqual(node.children(), ['foo'])

    # Remove a non-existent child.
    self.assertRaises(KeyError, node.remove_child, 'bar')
    self.assertEqual(node.to_value(), {'foo': 1})
    self.assertEqual(node.child('foo').to_value(), 1)
    self.assertEqual(node.child('foo').revision, node.revision)
    self.assertEqual(node.children(), ['foo'])

    # Try to fetch a non-existent child.
    self.assertRaises(KeyError, node.child, 'nonexistant')

    # None of these operations should have modified the base revision.
    self.assertEqual(node.revision, 12)


class TestStatus(monitor.util.test_base.TestBase):

  def test_creation(self):
    """Verify handle_action with status and http URL strings."""
    status = self._create_status({})

    # If we start with nothing, we should end up with nothing but a revision
    # of 1.
    self.assertEqual(status.revision(), 1)
    self.assertEqual(status.get(), {})

  def test_get(self):
    contents = {
        'int': 2,
        'string': 'foo',
        'list': [5, 6, 7],
        'dict': {'sub1': 3, 'sub2': 4},
    }

    status = self._create_status(contents)

    self.assertEqual(status.get('status://'), contents)
    self.assertEqual(status.get('status://nonexistant'), None)
    self.assertEqual(status.get('status://nonexistant', 'default'), 'default')
    self.assertEqual(status.get('status://dict/nonexistant', 'default'),
                     'default')
    self.assertEqual(status.get('status://int'), 2)
    self.assertEqual(status.get('status://string'), 'foo')
    self.assertEqual(status.get('status://list'), [5, 6, 7])
    self.assertEqual(status.get('status://dict'), {'sub1': 3, 'sub2': 4})
    self.assertEqual(status.get('status://dict/sub1'), 3)

    self.assertRaises(monitor.status.BadUrl,
                      status.get, 'status://string/foo')
    self.assertRaises(monitor.status.BadUrl,
                      status.get, 'status://string/foo', None)
    self.assertRaises(monitor.status.BadUrl,
                      status.get, 'status://list/1')


    # Ensure values copied out are copied, not referenced.
    l = status.get('status://list')
    l.append(1)
    self.assertEqual(status.get('status://list'), [5, 6, 7])

  def test_get_matching(self):
    contents = {
        'match1': {'foo': 1},
        'match2': {'foo': 2},
        'solo1': {'bar': 3},
        'deep1': {'sub_deep1': {'foo': 4},
                  'sub_deep2': {'foo': 5}},
        'deep2': {'sub_deep1': {'foo': 6}},
        'string': 'foo',
        'list': []
    }

    status = self._create_status(contents)

    def _validate_result(url, expected_urls, _expected_values):
      self.assertEqual(sorted(status.get_matching_urls(url)),
                       sorted(expected_urls))
      # self.assertEqual(status.get_matching_values(url),
      #                  expected_values)

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
                     {'nest2': {'nest3': 'foo'}})
    self.assertEqual(status.revision(), 5)

    # Clear an existing value.
    status.set('status://dict/sub1', None)
    self.assertEqual(status.get('status://dict'),
                     {'sub2': 4})
    self.assertEqual(status.revision(), 6)

    # Clear a sub-tree
    status.set('status://nest1', None)
    self.assertEqual(status.get('status://'),
                     {'dict': {'sub2': 4},
                      'int': 10,
                      'list': [],
                      'list2': []})
    self.assertEqual(status.revision(), 7)

    # Clear a nonexitent value
    status.set('status://nonexistent', None)
    self.assertEqual(status.get('status://'),
                     {'dict': {'sub2': 4},
                      'int': 10,
                      'list': [],
                      'list2': []})
    self.assertEqual(status.revision(), 7)



  def test_nested_revisions(self):
    """Test Status.revision() handles nested revision numbers."""

    # Make Sure initial revisions match expectations.
    status = self._create_status({
        'int': 1,
        'string': 'foo',
        'list': [],
        'deep1': {'foo': 2},
        'deep2': {'sub_deep1': {'foo': 3},
                  'sub_deep2': {'foo': 4}},
    })

    self.assertEqual(status.revision(), 1)
    self.assertEqual(status.revision('status://int'), 1)
    self.assertEqual(status.revision('status://string'), 1)
    self.assertEqual(status.revision('status://list'), 1)
    self.assertEqual(status.revision('status://deep1'), 1)
    self.assertEqual(status.revision('status://deep1/foo'), 1)
    self.assertEqual(status.revision('status://deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep1'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep1/foo'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2/foo'), 1)

    self.assertRaises(monitor.status.UnknownUrl,
                      status.revision, 'status://nonexistent')

    # Make a simple update.
    status.set('status://int', 10)

    self.assertEqual(status.revision(), 2)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://string'), 1)
    self.assertEqual(status.revision('status://list'), 1)
    self.assertEqual(status.revision('status://deep1'), 1)
    self.assertEqual(status.revision('status://deep1/foo'), 1)
    self.assertEqual(status.revision('status://deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep1'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep1/foo'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2/foo'), 1)

    # Make a nested update.
    status.set('status://deep1/foo', 20)

    self.assertEqual(status.revision(), 3)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://string'), 1)
    self.assertEqual(status.revision('status://list'), 1)
    self.assertEqual(status.revision('status://deep1'), 3)
    self.assertEqual(status.revision('status://deep1/foo'), 3)
    self.assertEqual(status.revision('status://deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep1'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep1/foo'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2/foo'), 1)

    # Make a deeper nested update.
    status.set('status://deep2/sub_deep1/foo', 30)

    self.assertEqual(status.revision(), 4)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://string'), 1)
    self.assertEqual(status.revision('status://list'), 1)
    self.assertEqual(status.revision('status://deep1'), 3)
    self.assertEqual(status.revision('status://deep1/foo'), 3)
    self.assertEqual(status.revision('status://deep2'), 4)
    self.assertEqual(status.revision('status://deep2/sub_deep1'), 4)
    self.assertEqual(status.revision('status://deep2/sub_deep1/foo'), 4)
    self.assertEqual(status.revision('status://deep2/sub_deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2/foo'), 1)

    # Replace a sub-tree
    status.set('status://deep2/sub_deep1', {'foo': 40, 'bar': 50})

    self.assertEqual(status.revision(), 5)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://string'), 1)
    self.assertEqual(status.revision('status://list'), 1)
    self.assertEqual(status.revision('status://deep1'), 3)
    self.assertEqual(status.revision('status://deep1/foo'), 3)
    self.assertEqual(status.revision('status://deep2'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep1'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep1/foo'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep1/bar'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2/foo'), 1)

    # Replace a sub-tree, unchanged.
    status.set('status://deep2/sub_deep1', {'foo': 40, 'bar': 50})

    self.assertEqual(status.revision(), 5)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://string'), 1)
    self.assertEqual(status.revision('status://list'), 1)
    self.assertEqual(status.revision('status://deep1'), 3)
    self.assertEqual(status.revision('status://deep1/foo'), 3)
    self.assertEqual(status.revision('status://deep2'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep1'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep1/foo'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep1/bar'), 5)
    self.assertEqual(status.revision('status://deep2/sub_deep2'), 1)
    self.assertEqual(status.revision('status://deep2/sub_deep2/foo'), 1)

  def test_set_revision(self):
    """Test Status.set() if revision is passed in."""

    # Make Sure initial revisions match expectations.
    status = self._create_status()

    # Set a new value, update with correct specified revision.
    status.set('status://int', 10, revision=1)
    self.assertEqual(status.revision(), 2)
    self.assertEqual(status.revision('status://int'), 2)

    # Update an existing value with correct specified revision.
    status.set('status://int', 20, revision=2)
    self.assertEqual(status.revision(), 3)
    self.assertEqual(status.revision('status://int'), 3)

    # Set a new value, update with incorrect specified revision.
    # Should raise exception, and modify nothing.
    self.assertRaises(monitor.status.RevisionMismatch,
                      status.set, 'status://int', 30, revision=1)
    self.assertEqual(status.get('status://int'), 20)
    self.assertEqual(status.revision(), 3)
    self.assertEqual(status.revision('status://int'), 3)

    # Set a new value, update with a future version.
    self.assertRaises(monitor.status.RevisionMismatch,
                      status.set, 'status://int', 30, revision=100)
    self.assertEqual(status.get('status://int'), 20)
    self.assertEqual(status.revision(), 3)
    self.assertEqual(status.revision('status://int'), 3)

  def test_set_revision_nested(self):
    """Test Status.set() if revision is passed in."""

    # Make Sure initial revisions match expectations.
    status = self._create_status({
        'int': 1,
        'deep': {'foo': 2},
    })

    # Update one section.
    status.set('status://int', 10, revision=1)
    self.assertEqual(status.revision(), 2)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://deep'), 1)
    self.assertEqual(status.revision('status://deep/foo'), 1)

    # Ensure old section can still update using original revision.
    status.set('status://deep/foo', 20, revision=1)
    self.assertEqual(status.revision(), 3)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://deep'), 3)
    self.assertEqual(status.revision('status://deep/foo'), 3)

    # Ensure new creation works with nested revisions.
    status.set('status://deep/bar', 30, revision=3)
    self.assertEqual(status.revision(), 4)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://deep'), 4)
    self.assertEqual(status.revision('status://deep/foo'), 3)
    self.assertEqual(status.revision('status://deep/bar'), 4)

    # Ensure value can be updated using a parents revision.
    status.set('status://deep/foo', 21, revision=4)
    self.assertEqual(status.revision(), 5)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://deep'), 5)
    self.assertEqual(status.revision('status://deep/foo'), 5)
    self.assertEqual(status.revision('status://deep/bar'), 4)

    # Ensure new creation works with updated revisions.
    status.set('status://deep/bar', 31, revision=4)
    self.assertEqual(status.revision(), 6)
    self.assertEqual(status.revision('status://int'), 2)
    self.assertEqual(status.revision('status://deep'), 6)
    self.assertEqual(status.revision('status://deep/foo'), 5)
    self.assertEqual(status.revision('status://deep/bar'), 6)

    # Ensure value can be updated using a parents revision.
    status.set('status://int', 11, revision=6)
    status.set('status://int', 12, revision=7)
    self.assertEqual(status.revision(), 8)
    self.assertEqual(status.revision('status://int'), 8)
    self.assertEqual(status.revision('status://deep'), 6)
    self.assertEqual(status.revision('status://deep/foo'), 5)
    self.assertEqual(status.revision('status://deep/bar'), 6)

    # Ensure value can NOT be updated using an outdated parent version.
    self.assertRaises(
        monitor.status.RevisionMismatch,
        status.set, 'status://deep/foo', 21, revision=7)

    self.assertEqual(status.revision(), 8)
    self.assertEqual(status.revision('status://int'), 8)
    self.assertEqual(status.revision('status://deep'), 6)
    self.assertEqual(status.revision('status://deep/foo'), 5)
    self.assertEqual(status.revision('status://deep/bar'), 6)

  def test_helpers(self):
    status = self._create_status({
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
    status = self._create_status({'int': 2})

    d = status.deferred(0)
    d.addCallback(self.assertEquals, ['status://'])
    self.assertTrue(d.called)

  def test_mismatch_revision_with_url(self):
    status = self._create_status({'int': 2})

    url = 'status://int'
    d = status.deferred(0, url=url)
    d.addCallback(self.assertEquals, [url])
    self.assertTrue(d.called)

  def test_single_change_no_url(self):
    status = self._create_status({'int': 2})

    # Test that the expected notification fires after we make a change.
    url = 'status://int'
    d = status.deferred()
    status.set(url, 3)
    d.addCallback(self.assertEquals, ['status://'])
    self.assertTrue(d.called)

  def test_double_change_no_url(self):
    """Ensure the deferred does not fire on a non-meaningful change."""
    status = self._create_status({'int': 2})

    d = status.deferred(revision=1)
    status.set('status://int', 3)
    status.set('status://int', 4)
    d.addCallback(self.assertEquals, ['status://'])
    self.assertTrue(d.called)

  def test_no_change(self):
    status = self._create_status({'int': 2})

    d = status.deferred(revision=1)
    self.assertFalse(d.called)

  def test_default_revision(self):
    status = self._create_status({'int': 2})

    d = status.deferred()
    self.assertFalse(d.called)

  def test_noop_change(self):
    """Ensure the deferred does not fire on a non-meaningful change."""
    status = self._create_status({'int': 2})

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
    self.assertTrue(d.called)

  def test_url_double_updated(self):
    status = self._create_status()

    # Ask for a specialized notification.
    url = 'status://int'
    d = status.deferred(revision=1, url=url)
    d.addCallback(self.assertEquals, [url])
    status.set(url, 3)
    status.set(url, 4)
    self.assertTrue(d.called)

  def test_url_nested_updates(self):
    status = self._create_status()
    url = 'status://int'

    def callback(value, new_int):
      status.set(url, new_int)
      return value

    d = status.deferred(url=url)
    d.addCallback(callback, 4)
    d.addCallback(callback, 5)
    status.set(url, 3)
    self.assertTrue(d.called)

  def test_url_circular_deferreds(self):
    status = self._create_status({'foo': 1, 'bar': 1})

    url_foo = 'status://foo'
    url_bar = 'status://bar'

    d_foo = status.deferred(url=url_foo)
    d_bar = status.deferred(url=url_bar)

    def callback(value, new_url, new_int):
      status.set(new_url, new_int)
      return value

    d_foo.addCallback(callback, url_bar, 3)
    d_bar.addCallback(callback, url_foo, 3)

    status.set(url_foo, 2)
    status.set(url_bar, 2)

    self.assertTrue(d_foo.called)
    self.assertTrue(d_bar.called)

  def test_url_not_updated(self):
    status = self._create_status({'foo': 1, 'bar': 2})

    # Ask for a specialized notification.
    d = status.deferred(revision=1, url='status://bar')
    status.set('status://int', 3)
    self.assertFalse(d.called)

  def test_url_parent_revision(self):
    status = self._create_status({'foo': 1, 'bar': 2})
    status.set('status://foo', 3)

    self.assertEqual(status.revision(), 2)
    self.assertEqual(status.revision('status://bar'), 1)

    # Ask for a specialized notification with the parents revision, not
    # the revision of the url.
    d = status.deferred(revision=2, url='status://bar')
    status.set('status://int', 3)
    self.assertTrue(d.called)

  def test_url_parent_different_revision(self):
    status = self._create_status({'foo': 1, 'bar': 2})
    status.set('status://foo', 3)

    self.assertEqual(status.revision(), 2)
    self.assertEqual(status.revision('status://bar'), 1)

    # Ask for a specialized notification with the parents revision, not
    # the revision of the url.
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
    self.assertTrue(d.called)

  def test_find_revisions(self):
    status = self._create_status({'sub1': 1, 'sub2': {'subsub': 2}})

    url = 'status://sub1'
    d = status.deferred(url=url)
    self.assertEqual(d._find_revisions(),
                     {'status://sub1': 1})

    url = 'status://*/subsub'
    d = status.deferred(url=url)
    self.assertEqual(d._find_revisions(),
                     {'status://sub2/subsub': 1})

    url = 'status://nonexistent'
    d = status.deferred(url=url)
    self.assertEqual(d._find_revisions(),
                     {})

    url = 'status://*/nonexistent'
    d = status.deferred(url=url)
    self.assertEqual(d._find_revisions(),
                     {})



if __name__ == '__main__':
  unittest.main()
