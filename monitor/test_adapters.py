#!/usr/bin/python

import mock
import unittest

import monitor.adapter
import monitor.setup
import monitor.status
import monitor.util.test_base


# pylint: disable=W0212

class TestFileAdapter(monitor.util.test_base.TestBase):

  def test_load_default_filename(self):
    status = self._create_status({})
    url = 'status://foo'
    name = 'foo'
    json = { 'type': 'file' }

    UNIQUE = object()

    with mock.patch('monitor.adapter.FileAdapter.parse_config_file',
                    return_value=UNIQUE,
                    autospec=True) as m_parser:
      with mock.patch('monitor.status.Status.set', autospec=True) as m_set:
        a = monitor.adapter.FileAdapter(status, url, name, json)
        m_parser.assert_called_once_with(a, 'foo.json')
        m_set.assert_called_once_with(status, 'status://foo', UNIQUE)

  def test_load_explicit_filename(self):
    status = self._create_status({})
    url = 'status://foo'
    name = 'foo'
    json = { 'type': 'file', 'filename': 'bar.json' }

    UNIQUE = object()

    with mock.patch('monitor.adapter.FileAdapter.parse_config_file',
                    return_value=UNIQUE,
                    autospec=True) as m_parser:
      with mock.patch('monitor.status.Status.set', autospec=True) as m_set:
        a = monitor.adapter.FileAdapter(status, url, name, json)
        m_parser.assert_called_once_with(a, 'bar.json')
        m_set.assert_called_once_with(status, 'status://foo', UNIQUE)


class TestWebAdapter(monitor.util.test_base.TestBase):

  def test_web_adapter(self):
    status = self._create_status({})
    json = { 'type': 'web' }

    monitor.adapter.WebAdapter(status, 'status://foo', 'foo', json)
    monitor.adapter.WebAdapter(status, 'status://bar', 'bar', json)

    self.assertEqual(status.get('status://foo'), {})
    self.assertEqual(status.get('status://bar'), {})

    # Web Updatable Paths
    self.assertTrue(monitor.adapter.WebAdapter.web_updatable(
                    'status://foo'))
    self.assertTrue(monitor.adapter.WebAdapter.web_updatable(
                    'status://bar'))
    self.assertTrue(monitor.adapter.WebAdapter.web_updatable(
                    'status://foo/other'))

    # Not Web Updatable Paths
    self.assertFalse(monitor.adapter.WebAdapter.web_updatable(
                     'status://other'))
    self.assertFalse(monitor.adapter.WebAdapter.web_updatable(
                     'status://other/foo'))
    self.assertFalse(monitor.adapter.WebAdapter.web_updatable(
                     'status://fo'))


if __name__ == '__main__':
  unittest.main()
