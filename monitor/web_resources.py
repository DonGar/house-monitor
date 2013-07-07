#!/usr/bin/python

import json
import logging
import time

import smtplib
import email
import os

from twisted.web.client import getPage
from twisted.internet import base
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet import task
from twisted.python.urlpath import URLPath
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.util import redirectTo

import monitor.actions

from monitor.util import wake_on_lan


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

    # Expecting 'button', not 'button/stuff'

    item_id = request.postpath
    assert item_id.find('/') == -1
    return self.render_action(request, item_id)

  def render_action(self, _request, _item_id):
    raise Exception('render_action not implemented.')


class Button(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def render_action(self, request, item_id):

    # Rmember when the button was pushed.
    # Convert to a generic action?
    status_pushed_uri = 'status://button/%s/pushed' % item_id
    self.status.set(status_pushed_uri, int(time.time()))

    # Run the default action, if present.
    action_uri = 'status://button/%s/action' % item_id
    if self.status.get(action_uri, None):
      monitor.actions.handle_action(self.status, action_uri)

    request.setResponseCode(200)
    return 'Success'


class Host(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def render_action(self, request, item_id):
    action = request.args.get('action', [None])[0]
    if action:
      action_uri = 'status://host/%s/actions/%s' % (item_id, action)
      monitor.actions.handle_action(self.status, action_uri)
    request.setResponseCode(200)
    return 'Success'


class Log(_ConfigHandler):

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setResponseCode(200)
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(status.get_log(), sort_keys=True, indent=4))
    request.finish()
    return status


class Restart(_ConfigHandler):

  def render_POST(self, request):
    reactor.stop()
    request.setResponseCode(200)
    return 'Success'


class Status(_ConfigHandler):

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    return server.NOT_DONE_YET

  def send_update(self, value, request):
    request.setResponseCode(200)
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(value, sort_keys=True, indent=4))
    request.finish()
    return value


class Wake(_ConfigHandler):

  def render_POST(self, request):
    for mac in request.args['target']:
      logging.info('received request for: %s', mac)
      wake_on_lan.wake_on_lan(mac)

    request.setResponseCode(200)
    return 'Success'
