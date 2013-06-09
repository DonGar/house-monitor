#!/usr/bin/python

import copy
import datetime
import json
import logging
import os
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


def get_page_wrapper(url, **kwargs):
  logging.info('Started requet %s', url)

  def print_success(_):
    logging.info('Downloaded %s.', url)

  def print_error(error):
    logging.error('FAILED download %s: %s.', url, error)

  d = getPage(url.encode('ascii'), **kwargs)
  d.addCallbacks(print_success, print_error)


def download_page_wrapper(download_pattern, url, **kwargs):
  download_name = download_pattern.format(time=int(time.time()))

  logging.info('Started download %s -> %s', url, download_name)

  def print_success(_):
    logging.info('Downloaded %s -> %s.', url, download_name)

  def print_error(error):
    logging.error('FAILED download %s -> %s: %s.', url, download_name, error)

  d = downloadPage(url, download_name, **kwargs)
  d.addCallbacks(print_success, print_error)


def setup_requests(status):
  # Directory in which downloaded files are saved.
  config = status.get_config()
  server = config['server']

  download_dir = server['downloads']
  latitude = float(server['latitude'])
  longitude = float(server['longitude'])

  for request in config['requests']:
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
                            download_page_wrapper,
                            download_pattern,
                            bytes(request['url']))
    else:
      repeat.call_repeating(delay_helper,
                            get_page_wrapper,
                            bytes(request['url']))


def setupLogging():
  # Direct twisted logs into the standard Python logging.
  observer = log.PythonLoggingObserver()
  observer.start()

  stream = StringIO.StringIO()
  handler = logging.StreamHandler(stream)

  logger = logging.getLogger()
  logger.addHandler(handler)

  return handler, stream


def setup():
  log_handler, log_stream = setupLogging()

  # Create our global shared status
  config = parse_config_file()
  status = Status(config, log_handler, log_stream)
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
