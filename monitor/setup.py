#!/usr/bin/python

import datetime
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

def findDownloadDir():
  result = os.path.realpath(os.path.join(os.path.dirname(__file__),
                            '..', '..',
                            'Downloads'))
  if os.path.exists(result):
    return result
  else:
    return None


def download_file(download_dir, download_pattern, url, **kwargs):
  download_name = download_pattern % time.time()
  download_file = os.path.join(download_dir, download_name)

  print "Started download %s -> %s" % (url, download_name)

  def print_success(_):
    print 'Downloaded %s -> %s.' % (url, download_name)

  def print_error(error):
    print 'FAILED download %s -> %s: %s.' % (url, download_name, error)

  d = downloadPage(url, download_file, **kwargs)
  d.addCallbacks(print_success, print_error)


def setup_camera_events(status_state, download_dir):
  camera_auth = urllib.urlencode({ 'user' : 'guest', 'pwd' : '' })

  # Turn camera IR lights on/off
  kitchen_ir_off = 'http://kitchen/decoder_control.cgi?user=admin&pwd=oOcSR0kd&command=94'
  kitchen_ir_on = 'http://kitchen/decoder_control.cgi?user=admin&pwd=oOcSR0kd&command=95'
  garage_ir_off = 'http://garage/decoder_control.cgi?user=admin&pwd=oOcSR0kd&command=94'
  garage_ir_on = 'http://garage/decoder_control.cgi?user=admin&pwd=oOcSR0kd&command=95'

  repeat.call_repeating(repeat.next_sunrise, getPage,
                        kitchen_ir_off, postdata=camera_auth)

  repeat.call_repeating(repeat.next_sunset, getPage,
                        kitchen_ir_on, postdata=camera_auth)

  repeat.call_repeating(repeat.next_sunset, getPage,
                        garage_ir_on, postdata=camera_auth)

  # Every five minute call into download_file to get a kitchen snapshot
  repeat.call_repeating(lambda utc_now: repeat.next_interval(utc_now,
                                                             interval_minutes=5),
                        download_file,
                        download_dir, "front_door_tracker.%d.jpg",
                        'http://kitchen/snapshot.cgi?user=guest&pwd=')

  # At noon every day, take a snapshot from both the kitchen and garage cameras
  repeat.call_repeating(repeat.next_daily,
                        download_file,
                        download_dir, "front_door_daily.%d.jpg",
                        'http://kitchen/snapshot.cgi?user=guest&pwd=')

  repeat.call_repeating(repeat.next_daily,
                        download_file,
                        download_dir, "garage_daily.%d.jpg",
                        'http://garage/snapshot.cgi?user=guest&pwd=')


def setup():
  # Create our global shared status
  status_state = status.Status()

  # Find our directory for Downloads, if it exists
  download_dir = findDownloadDir()

  if download_dir:
    setup_camera_events(status_state, download_dir)

  # Setup pings for various machines
  up.setup(status_state, ['vinge', 'niven', 'stross', 'stumpy',
                          'tv', 'pi', 'bone'])

  # Assemble the factory for our web server.
  # Serve the standard static web content, overlaid with our dynamic content
  root = File("./static")
  root.putChild("clock", web_resources.Clock())
  root.putChild("doorbell", web_resources.Doorbell(status_state))
  root.putChild("status_handler", web_resources.Status(status_state))
  root.putChild("wake_handler", web_resources.Wake())
  root.putChild("restart", web_resources.Restart())

  reactor.listenTCP(8080, Site(root))
