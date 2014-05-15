#!/usr/bin/python

import mock
import unittest

import monitor.adapter
import monitor.setup
import monitor.status
import monitor.util.test_base


# pylint: disable=W0212

class TestFileAdapter(monitor.util.test_base.TestBase):

  def test_default_filename(self):
    status = self._create_status({})
    url = 'status://foo'
    name = 'foo'
    json = {'type': 'file'}

    monitor.adapter.BASE_DIR = '/tmp'

    # We don't test anything but the file name.
    with mock.patch('monitor.adapter.FileAdapter.setup_notify', autospec=True):
      with mock.patch('monitor.adapter.FileAdapter.update_config_file',
                      autospec=True):
        a = monitor.adapter.FileAdapter(status, url, name, json)
        self.assertEqual(a.filename, '/tmp/foo.json')


  def test_explicit_filename(self):
    status = self._create_status({})
    url = 'status://foo'
    name = 'foo'
    json = {'type': 'file', 'filename': 'bar.json'}

    monitor.adapter.BASE_DIR = '/tmp'

    # We don't test anything but the file name.
    with mock.patch('monitor.adapter.FileAdapter.setup_notify',
                    autospec=True):
      with mock.patch('monitor.adapter.FileAdapter.update_config_file',
                      autospec=True):
        a = monitor.adapter.FileAdapter(status, url, name, json)
        self.assertEqual(a.filename, '/tmp/bar.json')


class TestWebAdapter(monitor.util.test_base.TestBase):

  def test_web_adapter(self):
    status = self._create_status({})
    json = {'type': 'web'}

    monitor.adapter.WebAdapter(status, 'status://foo', 'foo', json)
    monitor.adapter.WebAdapter(status, 'status://bar', 'bar', json)

    self.assertEqual(status.get('status://foo'), {})
    self.assertEqual(status.get('status://bar'), {})

    # Web Updatable Paths
    self.assertTrue(monitor.adapter.WebAdapter.web_updatable('status://foo'))
    self.assertTrue(monitor.adapter.WebAdapter.web_updatable('status://bar'))
    self.assertTrue(monitor.adapter.WebAdapter.web_updatable(
        'status://foo/other'))

    # Not Web Updatable Paths
    self.assertFalse(monitor.adapter.WebAdapter.web_updatable('status://other'))
    self.assertFalse(monitor.adapter.WebAdapter.web_updatable(
        'status://other/foo'))
    self.assertFalse(monitor.adapter.WebAdapter.web_updatable('status://fo'))


if __name__ == '__main__':
  unittest.main()
