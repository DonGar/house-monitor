#!/usr/bin/python


import logging
import os
import time
import urllib

from twisted.web.client import downloadPage
from twisted.web.client import getPage

def attach_logging_callbacks(deferred, description):
  """Attach SUCCESS/FAILURE logs to a deferred."""
  def log_success(_):
    logging.info('SUCCESS: {}'.format(description))

  def log_error(error):
    logging.error('FAILURE: {}: {}.'.format(description, error))

  deferred.addCallbacks(log_success, log_error)
  logging.info('STARTED: {}'.format(description))

def get_page_wrapper(_status, url):
  """Start a download (not to disk). Return a deferred for it's completion."""

  description = 'Request {}'.format(url)

  # Start the download
  d = getPage(url.encode('ascii'))
  attach_logging_callbacks(d, description)
  return d

def download_page_wrapper(status, download_pattern, url):
  """Start a download (to disk). Return a deferred for it's completion."""

  config = status.get_config()
  server = config['server']
  download_dir = server['downloads']

  # This dictionary defines the field values that can be filled in.
  pattern_values = { 'time': int(time.time()) }
  download_name = download_pattern.format(**pattern_values)

  description = 'Download {} -> {}'.format(url, download_name)
  logging.info('REQUESTING: {}'.format(description))

  # Start the download
  d = downloadPage(url, os.path.join(download_dir, download_name))
  attach_logging_callbacks(d, description)
  return d
