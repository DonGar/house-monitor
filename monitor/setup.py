#!/usr/bin/python

from twisted.internet import reactor
from twisted.web.static import File
from twisted.web.server import Site

from monitor import status
from monitor import up
from monitor import web_resources

def setup():
  # Create our global shared status
  status_state = status.Status()

  up.setup(status_state, ['tv', 'vinge', 'stross'])

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("clock", web_resources.Clock())
  root.putChild("doorbell", web_resources.Doorbell(status_state))
  root.putChild("status_handler", web_resources.Status(status_state))
  root.putChild("wake_handler", web_resources.Wake())
  root.putChild("restart", web_resources.Restart())

  reactor.listenTCP(8080, Site(root))
