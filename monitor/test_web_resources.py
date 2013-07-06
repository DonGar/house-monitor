#!/usr/bin/python

import unittest
import mock

import twisted.trial.unittest
import twisted.internet
from twisted.internet import defer
from twisted.web import server
from twisted.web.test.test_web import DummyRequest

import monitor.web_resources

# pylint: disable=W0212

class TestWebResources(twisted.trial.unittest.TestCase):

  def _create_status(self, values=None):
    if values is None:
      values = {
        'int': 2,
      }

    return monitor.status.Status(values, None, None)

  def _render(self, resource, request):
    result = resource.render(request)
    if isinstance(result, str):
      request.write(result)
      request.finish()
      return defer.succeed(None)
    elif result is server.NOT_DONE_YET:
      if request.finished:
        return defer.succeed(None)
      else:
        return request.notifyFinish()
    else:
      raise ValueError("Unexpected return value: %r" % (result,))

  def test_status(self):
    status = self._create_status()

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
