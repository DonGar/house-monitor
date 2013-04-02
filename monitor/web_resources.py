#!/usr/bin/python

import json
import logging
import time

from twisted.internet import base
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet import task
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from monitor.util import wake_on_lan

class _ConfigActionHandler(Resource):
  """Create a handler that records a button push."""
  isLeaf = True

  def __init__(self, status):
    self.status = status

  def render_GET(self, request):
    return self.render_POST(request)

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    id = request.args['id'][0]
    action = request.args.get('action', [None])[0]

    redirect = self.handle_action(id, action)

    if redirect:
      return redirectTo(redirect.encode('ascii'), request)

    return "Success"

  def handle_action(self, id, action):
    raise Exception('handle_action not implemented.')


class Host(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, id, action):
    assert action in (None, 'sleep', 'wake')

    uri = 'status://hosts/%s' % id
    node = self.status.get(uri)

    # See if there is an action to take.
    if action in node['action']:
      return node['action'][action]


class Button(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, id, action):
    if action is None:
      action is 'on'

    assert action in ('on', 'off')

    uri = 'status://buttons/%s' % id
    node = self.status.get(uri)

    uri = 'status://buttons/%s/pushed' % id
    self.status.set(uri, str(time.time()))

    # See if there is an action to take.
    if action in node['action']:
      return node['action'][action]


class Status(Resource):
  isLeaf = True

  def __init__(self, status):
    self.status = status

  def render_GET(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader("content-type", "application/json")
    request.write(json.dumps(status.get(), sort_keys=True, indent=4))
    request.finish()
    return status


class Log(Resource):
  isLeaf = True

  def __init__(self, status):
    self.status = status

  def render_GET(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader("content-type", "application/json")
    request.write(json.dumps(status.get_log(), sort_keys=True, indent=4))
    request.finish()
    return status


class Wake(Resource):
  isLeaf = True

  def render_GET(self, request):
    return self.render_POST(request)

  def render_POST(self, request):
    for mac in request.args["target"]:
      logging.info('received request for: %s', mac)
      wake_on_lan(mac)
    return "Success"


class Restart(Resource):
  isLeaf = True

  def render_GET(self, request):
    reactor.stop()
    return "Success"
