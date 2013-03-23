#!/usr/bin/python

import json
import logging
import time

from twisted.internet import base
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from monitor.util import wake_on_lan

class Button(Resource):
  """Create a handler that records a button push."""
  isLeaf = True

  def __init__(self, status):
    self.status = status

  def render_GET(self, request):
    return self.render_POST(request)

  def render_POST(self, request):
    for id in request.args["id"]:
      logging.info('Button push for: %s', id)
      redirect = self.status.get_buttons().get(id).encode('ascii')

      if redirect is None:
        return "Unknown Id: %s" % id

      self.status.update({id : str(time.time())})

      if redirect:
        return redirectTo(redirect, request)
      else:
        return "Success"

    return "No Button Id"


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
    # TODO: if the request is already closed, exit cleanly
    request.setHeader("content-type", "application/json")
    request.write(json.dumps(status.get_values()))
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
    # TODO: if the request is already closed, exit cleanly
    request.setHeader("content-type", "application/json")

    logs = status.get_log()
    request.write(json.dumps(logs[-10:]))
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
