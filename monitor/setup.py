#!/usr/bin/python

import json
import logging
import os
import sys
import StringIO

from twisted.python import log
from twisted.internet import reactor
from twisted.web.static import File
from twisted.web.server import Site

from monitor.rules_engine import RulesEngine
from monitor.status import Status
import monitor.up
import monitor.web_resources

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))


def parse_config_file():
  """Parse a config file in .json format."""
  config_file = os.path.join(BASE_DIR, 'config.json')
  logging.info('Reading config %s', config_file)
  if os.path.exists(config_file):
    with open(config_file, 'r') as f:
      return json.load(f)


def setupLogging():

  formatter = logging.Formatter(
      '%(asctime)s %(levelname)s %(module)s:%(lineno)d - %(message)s',
      '%H:%M:%S')

  # Setup stdout logging
  stdout_handler = logging.StreamHandler(sys.stdout)
  stdout_handler.setLevel(logging.DEBUG)
  stdout_handler.setFormatter(formatter)

  # Setup buffer logging (for web display)
  log_buffer = StringIO.StringIO()
  buffer_handler = logging.StreamHandler(log_buffer)
  buffer_handler.setLevel(logging.WARNING)
  buffer_handler.setFormatter(formatter)

  # Setup the root logger to use both handlers.
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)
  logger.addHandler(stdout_handler)
  logger.addHandler(buffer_handler)

  # Direct twisted logs into the standard Python logging.
  observer = log.PythonLoggingObserver()
  observer.start()

  return buffer_handler, log_buffer


def setup():
  log_handler, log_buffer = setupLogging()

  # Create our global shared status
  config = parse_config_file()
  status = Status(config)

  # pylint: disable=W0612
  engine = RulesEngine(status)

  monitor.up.setup(status)

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("button", monitor.web_resources.Button(status))
  root.putChild("host", monitor.web_resources.Host(status))
  root.putChild("log", monitor.web_resources.Log(log_handler, log_buffer))
  root.putChild("restart", monitor.web_resources.Restart(status))
  root.putChild("status", monitor.web_resources.Status(status))
  root.putChild("wake_handler", monitor.web_resources.Wake(status))

  reactor.listenTCP(config['server'].get('port', 8080),
                    Site(root))
