#!/usr/bin/python

import time

from twisted.internet import base
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from monitor.util import wake_on_lan

class Clock(Resource):
  """Create a handler that returns the current time once a second."""
  isLeaf = True

  def render_GET(self, request):
    print "Connected: %s" % request
    loopingCall = task.LoopingCall(self.__print_time, request)
    loopingCall.start(1, False)
    request.notifyFinish().addErrback(self._disconnect, loopingCall)

    return server.NOT_DONE_YET

  def _disconnect(self, err, loopingCall):
    print "Disconnected: %s" % loopingCall
    loopingCall.stop()

  def __print_time(self, request):
    request.write('<b>%s</b>' % (time.ctime(),))


class Doorbell(Resource):
  """Create a handler that records a doorbell push."""
  isLeaf = True

  def __init__(self, status):
    self.status = status

  def render_GET(self, request):
    self.status.update({'doorbell' : str(time.time())})
    return "Success"


class Status(Resource):
  isLeaf = True
  
  def __init__(self, status):
    self.status = status
  
  def render_GET(self, request):
    print "Request: %s" % request.uri
  
    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])
  
    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET
  
  def send_update(self, status, request):
    # TODO: if the request is already closed, exit cleanly
    request.setHeader("content-type", "application/json")
    request.write(status.get_json())
    request.finish()
    return status


class Wake(Resource):
  isLeaf = True
  
  def render_POST(self, request):
    for mac in request.args["target"]:
      print "received request for: %s" % mac
      wake_on_lan(mac)
    return redirectTo(request.getHeader("Referer"), request)


class Restart(Resource):
  isLeaf = True

  def render_GET(self, request):
    reactor.stop()  
    return "Success"
