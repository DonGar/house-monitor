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

from monitor.engine import Engine
from monitor.util import repeat
from monitor.status import Status
from monitor import up
from monitor import web_resources

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
  download_name = download_pattern % time.time()

  logging.info('Started download %s -> %s', url, download_name)

  def print_success(_):
    logging.info('Downloaded %s -> %s.', url, download_name)

  def print_error(error):
    logging.error('FAILED download %s -> %s: %s.', url, download_name, error)

  d = downloadPage(url, download_name, **kwargs)
  d.addCallbacks(print_success, print_error)


def setup_url_events(config):
  # Directory in which downloaded files are saved.
  download_dir = config['downloads']
  timezone = config['timezone']
  latitude = float(config['latitude'])
  longitude = float(config['longitude'])

  for request in config['requests']:
    if request['interval'] == 'daily':
      # Once a day.
      if request['time'] == 'sunset':
        delay_iter = repeat.next_sunset(latitude, longitude)
      elif request['time'] == 'sunrise':
        delay_iter = repeat.next_sunrise(latitude, longitude)
      elif 'time' in request:
        hours, minutes, seconds = [int(i) for i in request['time'].split(':')]
        delay_iter = repeat.next_daily(datetime.time(hours, minutes, seconds))
      else:
        raise Exception('Unknown requests time %s.' % request['time'])

    elif request['interval'] == 'interval':
      # Multiple times a day.
      if 'time' in request:
        hours, minutes, seconds = [int(i) for i in request['time'].split(':')]
        delay_iter = repeat.next_interval(datetime.timedelta(hours=hours,
                                                           minutes=minutes,
                                                           seconds=seconds))

    else:
      raise Exception('Unknown requests interval %s.' % request['interval'])

    if 'download_name' in request:
      download_pattern = os.path.join(download_dir, request['download_name'])
      repeat.call_repeating(delay_iter,
                            download_page_wrapper,
                            download_pattern,
                            bytes(request['url']))
    else:
      repeat.call_repeating(delay_iter,
                            get_page_wrapper,
                            (request['url']))


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
  status = Status(log_handler, log_stream)
  config = parse_config_file()

  if config:
    # Copy select parts of the config into the status.
    for tag in ('buttons', 'hosts', 'cameras', 'rules'):
      uri = 'status://%s' % tag
      status.set(uri, config.get(tag, {}))

    setup_url_events(config)
    up.setup(status)

  engine = Engine(status)

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("button", web_resources.Button(status))
  root.putChild("host", web_resources.Host(status))
  root.putChild("status_handler", web_resources.Status(status))
  root.putChild("log_handler", web_resources.Log(status))
  root.putChild("wake_handler", web_resources.Wake())
  root.putChild("restart", web_resources.Restart())

  reactor.listenTCP(8080, Site(root))
