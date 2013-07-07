#!/usr/bin/python

import monitor.web_resources

import unittest
import mock

import twisted.trial.unittest
import twisted.internet
from twisted.internet import defer
from twisted.internet import reactor
from twisted.web import server
from twisted.web.test.test_web import DummyRequest

import monitor.util.test_base

# pylint: disable=W0212

class TestWebResourcesButton(monitor.util.test_base.TestBase):

  def _test_button_helper(self, status, request, expected_actions, time_uri):
    patch = mock.patch('monitor.actions.handle_action', autospec=True)
    mocked = patch.start()

    # The resource to test.
    resource = monitor.web_resources.Button(status)

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')

      # Test pushed time was set. Any current time is > 100.
      self.assertTrue(status.get(time_uri) > 100)

      # Assert that no action handler was invoked.
      mocked.assert_has_calls(expected_actions)
      patch.stop()
    d.addCallback(rendered)
    return d

  def test_unknown_button(self):
    status = self._create_status({ 'button': { 'foo': {}} })

    # Setup
    request_unknown = DummyRequest('unknown')
    request_malformed = DummyRequest('foo/bar')
    resource = monitor.web_resources.Button(status)

    # Ensure these fail.
    self.assertRaises(KeyError, self._render, resource, request_unknown)
    self.assertRaises(AssertionError, self._render, resource, request_malformed)

  def test_button_no_action(self):
    status = self._create_status({ 'button': { 'foo': {}} })

    request = DummyRequest('foo')
    expected_actions = []
    return self._test_button_helper(status, request, expected_actions,
                                    'status://button/foo/pushed')

  def test_button_no_action(self):
    status = self._create_status({ 'button': { 'foo': {}} })

    request = DummyRequest('foo')
    expected_actions = []
    return self._test_button_helper(status, request, expected_actions,
                                    'status://button/foo/pushed')

  def test_button_action(self):
    status = self._create_status({ 'button': { 'foo':
                                               { 'action': 'action_pushed',
                                                 'pushed': 4 }}})

    request = DummyRequest('foo')
    expected_actions = [mock.call(status, 'status://button/foo/action')]
    return self._test_button_helper(status, request, expected_actions,
                                    'status://button/foo/pushed')


class TestWebResourcesHost(monitor.util.test_base.TestBase):

  def _test_host_helper(self, status, request, expected_actions):
    patch = mock.patch('monitor.actions.handle_action', autospec=True)
    mocked = patch.start()

    # The resource to test.
    resource = monitor.web_resources.Host(status)

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      # Assert that no action handler was invoked.
      mocked.assert_has_calls(expected_actions)
      patch.stop()
    d.addCallback(rendered)
    return d

  def test_unknown_host(self):
    status = self._create_status(
        { 'host': { 'foo': { 'actions': { 'bar': 'action_bar' }}}})

    # Setup
    request_unknown = DummyRequest('unknown')
    request_malformed = DummyRequest('foo/bar')
    resource = monitor.web_resources.Button(status)

    # Ensure these fail.
    self.assertRaises(KeyError, self._render, resource, request_unknown)
    self.assertRaises(AssertionError, self._render, resource, request_malformed)

  def test_host_no_action(self):
    status = self._create_status(
        { 'host': { 'foo': { 'actions': { 'bar': 'action_bar' }}}})

    request = DummyRequest('foo')
    expected_actions = []

    return self._test_host_helper(status, request, expected_actions)

  def test_host_explicit_action(self):
    status = self._create_status(
        { 'host': { 'foo': { 'actions': { 'bar': 'action_bar' }}}})

    request = DummyRequest('foo')
    request.addArg('action', 'bar')
    expected_actions = [mock.call(status, 'status://host/foo/actions/bar')]

    return self._test_host_helper(status, request, expected_actions)


class TestWebResourcesStatus(monitor.util.test_base.TestBase):

  def test_status(self):
    status = self._create_status({ 'int': 2 })

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = DummyRequest('')

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n    "int": 2, \n    "revision": 1\n}')
    d.addCallback(rendered)
    return d

  def test_status_wrong_version(self):
    status = self._create_status({ 'int': 2 })

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = DummyRequest('')
    request.addArg('revision', '123')

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n    "int": 2, \n    "revision": 1\n}')
    d.addCallback(rendered)
    return d

  def test_status_current_version(self):
    status = self._create_status({ 'int': 2 })

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = DummyRequest('')
    request.addArg('revision', '1')

    # Create and validate the response.
    d = self._render(resource, request)
    self._add_assert_timeout(d)
    return d

  def test_status_current_version_with_update(self):
    status = self._create_status({ 'int': 2 })

    # The resource to test.
    resource = monitor.web_resources.Status(status)

    # The request to make.
    request = DummyRequest('')
    request.addArg('revision', '1')

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written),
                        '{\n    "int": 3, \n    "revision": 2\n}')
    d.addCallback(rendered)

    status.set('status://int', 3)
    return d


class TestWebResourcesRestart(monitor.util.test_base.TestBase):
  def test_restart(self):
    status = self._create_status()

    # The resource to test.
    resource = monitor.web_resources.Restart(status)

    # The request to make.
    request = DummyRequest('')

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


class TestWebResourcesWake(monitor.util.test_base.TestBase):
  def test_wake(self):
    status = self._create_status()

    # The resource to test.
    resource = monitor.web_resources.Wake(status)

    # The request to make.
    request = DummyRequest('')
    request.addArg('target', '11:22:33:44:55:66')

    patch = mock.patch('monitor.util.wake_on_lan.wake_on_lan',
                       autospec=True)
    mocked = patch.start()

    # Create and validate the response.
    d = self._render(resource, request)
    def rendered(_):
      self.assertEquals(request.responseCode, 200)
      self.assertEquals(''.join(request.written), 'Success')
      mocked.assert_called_once_with('11:22:33:44:55:66')
      patch.stop()
    d.addCallback(rendered)
    return d


if __name__ == '__main__':
  unittest.main()
