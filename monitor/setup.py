#!/usr/bin/python

import copy
import datetime
import json
import logging
import os
import sys
import StringIO
import time
import urllib

from twisted.python import log
from twisted.web.client import downloadPage
from twisted.web.client import getPage
from twisted.internet import reactor
from twisted.web.static import File
from twisted.web.server import Site

from monitor.rules_engine import RulesEngine
from monitor.util import action
from monitor.util import repeat
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


def setup_requests(status):
  # Directory in which downloaded files are saved.
  config = status.get_config()
  server = config['server']

  download_dir = server['downloads']
  latitude = float(server['latitude'])
  longitude = float(server['longitude'])

  for request in config.get('requests', []):
    if request['interval'] == 'daily':
      # Once a day.
      if request['time'] == 'sunset':
        delay_helper = repeat.sunset_helper(latitude, longitude)
      elif request['time'] == 'sunrise':
        delay_helper = repeat.sunset_helper(latitude, longitude)
      elif 'time' in request:
        hours, minutes, seconds = [int(i) for i in request['time'].split(':')]
        time_of_day = datetime.time(hours, minutes, seconds)
        delay_helper = repeat.daily_helper(time_of_day)
      else:
        raise Exception('Unknown requests time %s.' % request['time'])

    elif request['interval'] == 'interval':
      # Multiple times a day.
      if 'time' in request:
        hours, minutes, seconds = [int(i) for i in request['time'].split(':')]
        interval = datetime.timedelta(hours=hours,
                                      minutes=minutes,
                                      seconds=seconds)
        delay_helper = repeat.interval_helper(interval)
    else:
      raise Exception('Unknown requests interval %s.' % request['interval'])

    if 'download_name' in request:
      download_pattern = os.path.join(download_dir, request['download_name'])
      repeat.call_repeating(delay_helper,
                            action.download_page_wrapper,
                            status,
                            download_pattern,
                            request['url'].encode('ascii'))
    else:
      repeat.call_repeating(delay_helper,
                            action.get_page_wrapper,
                            status,
                            request['url'].encode('ascii'))


def setupLogging():

  formatter = logging.Formatter(
      '%(asctime)s %(levelname)s %(module)s:%(lineno)d - %(message)s',
      '%H:%M:%S')

  # Setup stdout logging
  stdout_handler = logging.StreamHandler(sys.stdout)
  stdout_handler.setLevel(logging.INFO)
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
  status = Status(config, log_handler, log_buffer)
  engine = RulesEngine(status)

  setup_requests(status)
  monitor.up.setup(status)

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("button", monitor.web_resources.Button(status))
  root.putChild("email", monitor.web_resources.Email(status))
  root.putChild("host", monitor.web_resources.Host(status))
  root.putChild("log_handler", monitor.web_resources.Log(status))
  root.putChild("restart", monitor.web_resources.Restart(status))
  root.putChild("status_handler", monitor.web_resources.Status(status))
  root.putChild("wake_handler", monitor.web_resources.Wake(status))

  reactor.listenTCP(config['server'].get('port', 8080),
                    Site(root))
