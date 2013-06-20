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
    logging.info('Request: %s', request.uri)

    item_id = request.args['id'][0]
    action = request.args.get('action', [None])[0]

    redirect = self.handle_action(request, item_id, action)

    if redirect:
      return redirectTo(redirect.encode('ascii'), request)

    return 'Success'

  def handle_action(self, _request, _item_id, _action):
    raise Exception('handle_action not implemented.')


class Button(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, _request, item_id, action):

    # Rmember when the button was pushed.
    # Convert to a generic action?
    status_pushed_uri = 'status://buttons/%s/pushed' % item_id
    self.status.set(status_pushed_uri, int(time.time()))

    if action is None:
      action = 'pushed'

    action_uri = 'status://buttons/%s/actions/%s' % (item_id, action)
    monitor.actions.handle_action(self.status, action_uri)


class Host(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, _request, item_id, action):
    if action:
      action_uri = 'status://hosts/%s/actions/%s' % (item_id, action)
      monitor.actions.handle_action(self.status, action_uri)


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
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(status.get_log(), sort_keys=True, indent=4))
    request.finish()
    return status


class Restart(_ConfigHandler):

  def render_POST(self, _request):
    reactor.stop()
    return 'Success'


class Status(_ConfigHandler):

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(status.get(), sort_keys=True, indent=4))
    request.finish()
    return status


class Wake(_ConfigHandler):

  def render_POST(self, request):
    for mac in request.args['target']:
      logging.info('received request for: %s', mac)
      wake_on_lan.wake_on_lan(mac)
    return 'Success'
