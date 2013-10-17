#!/usr/bin/python

import json
import logging
import os
import time

from twisted.internet import defer
from twisted.internet import reactor
from twisted.web import server
from twisted.web.resource import Resource

import monitor.actions

from monitor.util import wake_on_lan

class UnknownComponent(Exception):
  pass

class _ConfigHandler(Resource):
  """Create a handler uses the POST handler for GET requests."""
  isLeaf = True

  def __init__(self, status):
    Resource.__init__(self)
    self.status = status

  def render_GET(self, request):
    return self.render_POST(request)

  def render_POST(self, _request):
    raise Exception('render_POST not implemented.')


class _ConfigActionHandler(_ConfigHandler):
  """Create a handler that parses arguments and hands off the action request."""

  def render_POST(self, request):

    # If postpath ended with /, there is a trailing empty string. Ditch it.
    if request.postpath and request.postpath[-1] == '':
      request.postpath.pop()

    # Expecting 'adapter/id'. Anything else is bad
    assert len(request.postpath) == 1, request.postpath

    component_id = request.postpath[0]
    return self.render_action(request, component_id)

  def render_action(self, _request, _component_id):
    raise Exception('render_action not implemented.')


class Button(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def render_action(self, request, component_id):

    # Remember when the button was pushed.
    # Convert to a generic action.

    button_search_url = os.path.join('status://*/button', component_id)
    buttons = self.status.get_matching(button_search_url)

    if not buttons:
      raise UnknownComponent(component_id)

    for button in buttons:
      url = button['url']

      # Update when the button was pushed.
      pushed_url = os.path.join(url, 'pushed')
      self.status.set(pushed_url, int(time.time()))

      # Run the default action, if present.
      action_uri = os.path.join(url, 'action')
      if self.status.get(action_uri, None):
        monitor.actions.handle_action(self.status, action_uri)

    request.setResponseCode(200)
    return 'Success'


class Host(_ConfigActionHandler):
  """Create a handler that records a request host action."""

  def render_action(self, request, component_id):


    host_search_url = os.path.join('status://*/host', component_id)
    hosts = self.status.get_matching(host_search_url)

    if not hosts:
      raise UnknownComponent(component_id)

    for host in hosts:
      url = host['url']

      action = request.args.get('action', [None])[0]

      if action:
        action_uri = os.path.join(url, 'actions', action)
        monitor.actions.handle_action(self.status, action_uri)

    request.setResponseCode(200)
    return 'Success'


class Log(Resource):

  def __init__(self, log_handler, log_buffer):
    Resource.__init__(self)
    self._log_handler = log_handler
    self._log_buffer = log_buffer

  def get_log(self):
    self._log_handler.flush()
    log = self._log_buffer.getvalue().split('\n')

    return {
      'revision': len(log),
      'log': log,
    }

  def render_GET(self, request):
    return self.render_POST(request)

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    if revision == 0:
      delay = 0
    else:
      delay = 10

    # Pretend we have a real deferred to tell us logs were updated.
    notify = reactor.callLater(delay, self._send_update, request)

    # If we get cut off while waiting to respond, it's pretty normal. Don't
    # error out.
    finish_deferred = request.notifyFinish()
    finish_deferred.addErrback(lambda _err: notify.cancel())

    return server.NOT_DONE_YET

  def _send_update(self, request):
    request.setResponseCode(200)
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(self.get_log(), sort_keys=True, indent=4))
    request.finish()


class Restart(_ConfigHandler):

  def render_POST(self, request):
    reactor.stop()
    request.setResponseCode(200)
    return 'Success'


class Status(Resource):

  isLeaf = True

  def __init__(self, status):
    Resource.__init__(self)
    self.status = status

  def render_GET(self, request):
    logging.info('GET Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])
    status_url = os.path.join('status://', *request.postpath)

    def _send_update(value):
      # To re-request this status value, re-request the same URL.
      value['url'] = os.path.join(str(request.URLPath()), *request.postpath)

      request.setResponseCode(200)
      request.setHeader('content-type', 'application/json')
      request.write(json.dumps(value, sort_keys=True, indent=4))
      request.finish()
      return value

    def cancel_ok(failure):
      failure.trap(defer.CancelledError)

    # Setup deferreds to notify us if the connection is closed, or if the
    # status we are watching is updated.
    finish_deferred = request.notifyFinish()
    notification = self.status.deferred(revision, status_url)

    # If the connection closes, cancel the status notification.
    finish_deferred.addErrback(lambda _err: notification.cancel())

    # If we get a status notification, tell our web client, and accept cancels.
    notification.addCallbacks(_send_update, cancel_ok)

    return server.NOT_DONE_YET

  def render_PUT(self, request):
    logging.info('PUT Request: %s', request.uri)

    status_url = os.path.join('status://', *request.postpath)

    assert monitor.adapters.WebAdapter.web_updatable(status_url)

    logging.info('PUT args: %s', request.args)
    logging.info('PUT content: %s', request.content.getvalue())

    # If a revision number was passed in, verify it matches our current
    # revision number. It would be better to verify that the value in question
    # hasn't been updated since the revision that was passed in, but that's
    # not currently possible.
    if 'revision' in request.args:
      revision = int(request.args['revision'][0])

      if revision != self.status.revision():
        request.setResponseCode(412) # Precondition Failure
        return 'Revision mismatch.'

    value_str = request.content.getvalue()
    value_parsed = json.loads(value_str)

    # Do the actual PUT.
    self.status.set(status_url, value_parsed)

    request.setResponseCode(200)
    return 'Success'


class Wake(_ConfigHandler):

  def render_POST(self, request):
    for mac in request.args['target']:
      logging.info('received request for: %s', mac)
      wake_on_lan.wake_on_lan(mac)

    request.setResponseCode(200)
    return 'Success'
