#!/usr/bin/python

import datetime
import json
import os
import time
import urllib

from twisted.web.client import downloadPage
from twisted.web.client import getPage
from twisted.internet import reactor
from twisted.web.static import File
from twisted.web.server import Site

from monitor.util import repeat
from monitor import status
from monitor import up
from monitor import web_resources

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

def parse_config_file():
  """Parse a config file in .json format."""
  config_file = os.path.join(BASE_DIR, 'config.json')
  print 'Reading config %s' % config_file
  if os.path.exists(config_file):
    with open(config_file, 'r') as f:
      return json.load(f)

def get_page_wrapper(url, **kwargs):
  print "Started requet %s" % (url,)

  def print_success(_):
    print 'Downloaded %s.' % (url,)

  def print_error(error):
    print 'FAILED download %s: %s.' % (url, error)

  d = getPage(url, **kwargs)
  d.addCallbacks(print_success, print_error)

def download_page_wrapper(download_pattern, url, **kwargs):
  download_name = download_pattern % time.time()

  print "Started download %s -> %s" % (url, download_name)

  def print_success(_):
    print 'Downloaded %s -> %s.' % (url, download_name)

  def print_error(error):
    print 'FAILED download %s -> %s: %s.' % (url, download_name, error)

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

def setup():
  # Create our global shared status
  status_state = status.Status()
  config = parse_config_file()

  if config:
    setup_url_events(config)
    up.setup(status_state, config['monitor']['ping'])

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("doorbell", web_resources.Doorbell(status_state))
  root.putChild("status_handler", web_resources.Status(status_state))
  root.putChild("wake_handler", web_resources.Wake())
  root.putChild("restart", web_resources.Restart())

  reactor.listenTCP(8080, Site(root))
