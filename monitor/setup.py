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

import monitor.actions
import monitor.adapter
import monitor.iogear_adapter
import monitor.snmp_adapter
import monitor.sonos_adapter
import monitor.rules_engine
import monitor.status
import monitor.web_resources

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

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


def setupAdapters(status):
  adapters = status.get('status://server/adapters')

  adapter_types = {
      'file': monitor.adapter.FileAdapter,
      'iogear': monitor.iogear_adapter.IOGearAdapter,
      'snmp': monitor.snmp_adapter.SnmpAdapter,
      'sonos': monitor.sonos_adapter.SonosAdapter,
      'web': monitor.adapter.WebAdapter,
  }

  for name, settings in adapters.iteritems():
    adapter_type = settings['type']
    adapter_url = 'status://%s' % name

    assert adapter_type in adapter_types, ('Unknown adapter types %s' %
                                           adapter_type)
    adapter_class = adapter_types[settings['type']]

    # Instantiate the adapter. It'll setup whatever it needs persisted.
    adapter_class(status, adapter_url, name, settings)

def setup():
  log_handler, log_buffer = setupLogging()

  status = monitor.status.Status()

  # Create our global shared status. Sort of a hard coded file adapter.
  config_file = os.path.join(BASE_DIR, 'server.json')
  with open(config_file, 'r') as f:
    status.set('status://server', json.load(f))

  # Setup the normal adapters.
  setupAdapters(status)

  # Create the manager for performing actions.
  action_manager = monitor.actions.ActionManager(status)

  # Instantiating the engine sets up the deferreds needed to keep it running.
  monitor.rules_engine.RulesEngine(status, action_manager)

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("button", monitor.web_resources.Button(status))
  root.putChild("log", monitor.web_resources.Log(log_handler, log_buffer))
  root.putChild("restart", monitor.web_resources.Restart(status))
  root.putChild("status", monitor.web_resources.Status(status))

  reactor.listenTCP(status.get('status://server/port', 8080),
                    Site(root))
