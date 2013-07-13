#!/usr/bin/python

import unittest

import twisted.trial.unittest
from twisted.internet import defer
from twisted.internet import reactor
from twisted.web import server

import monitor.web_resources

class TestBase(twisted.trial.unittest.TestCase):

  def _create_status(self, values=None):
    if values is None:
      values = {
        'int': 2,
        'list': [],
        'dict': {'sub1': 3, 'sub2': 4},
      }

    return monitor.status.Status(values)

  def _add_assert_timeout(self, d):
    # timeout is a unique object guaranteed different from any other result.
    timeout = object()
    d.addCallback(self.assertIs, timeout)
    reactor.callLater(0.1, d.callback, timeout)

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


if __name__ == '__main__':
  unittest.main()
