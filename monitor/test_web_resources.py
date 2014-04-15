#!/usr/bin/python

import monitor.web_resources

import unittest
import mock

from twisted.web.test.test_web import DummyRequest
from twisted.python.urlpath import URLPath

import monitor.adapter
import monitor.util.test_base

# pylint: disable=W0212

class TestWebResourcesButton(monitor.util.test_base.TestBase):
  """Test /button handler."""

  def _test_button_helper(self, status, request, time_uri):
    # The resource to test.
    resource = monitor.web_resources.Button(status)

    # Create and validate the response.
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      # Test pushed time was set. Any current time is > 100.
      self.assertTrue(status.get(time_uri) > 100)

    d = self._render(resource, request)
    d.addCallback(rendered)
    return d

  def test_unknown_button(self):
    status = self._create_status({'adapter': {'button': {'foo': {}}}})

    # Setup
    request_unknown = DummyRequest(['unknown'])
    request_malformed = DummyRequest(['foo', 'bar'])
    resource = monitor.web_resources.Button(status)

    # Ensure these fail.
    self.assertRaises(monitor.web_resources.UnknownComponent,
                      self._render, resource, request_unknown)
    self.assertRaises(AssertionError,
                      self._render, resource, request_malformed)

  def test_button(self):
    status = self._create_status({'adapter': {'button': {'foo':
                                     {'action': 'action_pushed',
                                      'pushed': 4}}}})

    request = DummyRequest(['foo'])
    return self._test_button_helper(status, request,
                                    'status://adapter/button/foo/pushed')


class TestWebResourcesStatus(monitor.util.test_base.TestBase):
  """Test /status handler."""

  def _dummy_request_get(self,
                         url='http://example/status',
                         path=None,
                         revision=None):
    if path is None:
      path = []

    # The request to make.
    request = DummyRequest(path)
    request.URLPath = lambda: URLPath.fromString(url)

    if revision is not None:
      request.addArg('revision', str(revision))

    return request

  def _dummy_request_put(self,
                         url='http://example/status',
                         path=None,
                         revision=None,
                         content=None):
    request = self._dummy_request_get(url, path, revision)

    # The request to make.
    request.method = 'PUT'

    if content is not None:
      request.content = mock.NonCallableMagicMock()
      request.content.getvalue = mock.Mock(return_value=content)

    return request

  def test_status(self):
    status = self._create_status({'int': 2})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_get()

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n'
                        '    "revision": 1, \n'
                        '    "status": {\n'
                        '        "int": 2\n'
                        '    }, \n'
                        '    "url": "http://example/status"\n'
                        '}')
    d.addCallback(rendered)
    return d

  def test_status_wrong_version(self):
    status = self._create_status({'int': 2})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_get(revision=123)

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n'
                        '    "revision": 1, \n'
                        '    "status": {\n'
                        '        "int": 2\n'
                        '    }, \n'
                        '    "url": "http://example/status"\n'
                        '}')
    d.addCallback(rendered)
    return d

  def test_status_current_version(self):
    status = self._create_status({'int': 2})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_get(revision=1)

    # Create and validate the response.
    d = self._render(resource, request)
    self._add_assert_timeout(d)
    return d

  def test_status_current_version_with_update(self):
    status = self._create_status({'int': 2})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_get(revision=1)

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n'
                        '    "revision": 2, \n'
                        '    "status": {\n'
                        '        "int": 3\n'
                        '    }, \n'
                        '    "url": "http://example/status"\n'
                        '}')
    d.addCallback(rendered)

    status.set('status://int', 3)
    return d

  def test_status_path(self):
    status = self._create_status({'int': 2,
                                   'sub1': {'sub2': {}}})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_get(path=['sub1', 'sub2'])

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n'
                        '    "revision": 1, \n'
                        '    "status": {}, \n'
                        '    "url": "http://example/status/sub1/sub2"\n'
                        '}')
    d.addCallback(rendered)
    return d

  def test_status_path_revision_path_not_modified(self):
    status = self._create_status({'int': 2,
                                   'sub1': {'sub2': {}}})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_get(path=['sub1', 'sub2'], revision=1)

    # Create and validate the response.
    d = self._render(resource, request)

    # Modify AFTER our request is in place.
    status.set('status://int', 3)

    # Since the branch we are watching wasn't modified, we shouldn't be
    # notified.
    self._add_assert_timeout(d)
    return d

  def test_post_simple(self):
    monitor.adapter.WebAdapter._test_clear_state()
    status = self._create_status({})

    # Create a web adapter for /web.
    monitor.adapter.WebAdapter(status, 'status://web', 'web', {})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_put(path=['web'],
                                      content='{"inserted": "value" }')

    #      Create and validate the response.
    d = self._render(resource, request)

    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      self.assertEquals(status.get(), {'web': {'inserted': 'value'}})

    d.addCallback(rendered)
    return d

  def test_post_nested(self):
    monitor.adapter.WebAdapter._test_clear_state()
    status = self._create_status({})

    # Create a web adapter for /web.
    monitor.adapter.WebAdapter(status, 'status://web', 'web', {})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_put(path=['web', 'sub', 'sub2'],
                                      content='{"inserted": "value" }')

    # Create and validate the response.
    d = self._render(resource, request)

    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      self.assertEquals(status.get(), {'web': {'sub': {'sub2':
                                          {'inserted': 'value'}}}})

    d.addCallback(rendered)
    return d

  def test_post_invalid(self):
    monitor.adapter.WebAdapter._test_clear_state()
    status = self._create_status({})

    # Create a web adapter for /web.
    monitor.adapter.WebAdapter(status, 'status://web', 'web', {})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_put(path=['unknown'],
                                      content='{"inserted": "value" }')

    # Create and validate the response.
    self.assertRaises(AssertionError,
                      self._render, resource, request)

  def test_post_revision(self):
    monitor.adapter.WebAdapter._test_clear_state()
    status = self._create_status({})

    # Create a web adapter for /web.
    monitor.adapter.WebAdapter(status, 'status://web', 'web', {})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_put(path=['web'],
                                      content='{"inserted": "value" }',
                                      revision=2)

    # Create and validate the response.
    d = self._render(resource, request)

    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      self.assertEquals(status.get(), {'web': {'inserted': 'value'}})

    d.addCallback(rendered)
    return d

  def test_post_bad_revision(self):
    monitor.adapter.WebAdapter._test_clear_state()
    status = self._create_status({})

    # Create a web adapter for /web.
    monitor.adapter.WebAdapter(status, 'status://web', 'web', {})

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = self._dummy_request_put(path=['web'],
                                      content='{"inserted": "value" }',
                                      revision=23)

    # Create and validate the response.
    d = self._render(resource, request)

    def rendered(_):
      self.assertEquals(request.responseCode, 412)  # Precondition Failure
      self.assertEquals(''.join(request.written), 'Revision mismatch.')
      self.assertEquals(status.get(), {'web': {}})

    d.addCallback(rendered)
    return d


class TestWebResourcesRestart(monitor.util.test_base.TestBase):
  """Test /restart handler."""
  def test_restart(self):
    status = self._create_status()

    # The resource to test.
    resource = monitor.web_resources.Restart(status)

    # The request to make.
    request = DummyRequest([])

    patch = mock.patch('twisted.internet.reactor.stop', autospec=True)
    mocked = patch.start()

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      mocked.assert_called_once_with()
      patch.stop()
    d.addCallback(rendered)
    return d


if __name__ == '__main__':
  unittest.main()
