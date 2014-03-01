#!/usr/bin/python

import logging
import os
import time

from twisted.web.client import downloadPage
from twisted.web.client import getPage

def attach_logging_callbacks(deferred, description):
  """Attach SUCCESS/FAILURE logs to a deferred."""
  def log_success(result):
    logging.info('SUCCESS: {}'.format(description))
    return result

  def log_error(error):
    logging.error('FAILURE: {}: {}.'.format(description, error))
    return error

  deferred.addCallbacks(log_success, log_error)
  logging.info('STARTED: {}'.format(description))

def get_page_wrapper(url):
  """Start a download (not to disk). Return a deferred for it's completion."""

  description = 'Request {}'.format(url)

  # Start the download
  d = getPage(url.encode('ascii'))
  attach_logging_callbacks(d, description)
  return d

def find_download_name(status, download_pattern, download_dir=None):
  if not download_dir:
    download_dir = status.get('status://server/downloads')

  # This dictionary defines the field values that can be filled in.
  pattern_values = {'time': int(time.time())}
  download_name = download_pattern.format(**pattern_values)

  # Make sure the downloads dir can't be escaped.
  base_name = os.path.basename(download_name)
  return os.path.join(download_dir, base_name)

def download_page_wrapper(url, file_name):
  """Start a download (to disk). Return a deferred for it's completion."""

  description = 'Download %s -> %s' % (url, os.path.basename(file_name))
  logging.info('REQUESTING: %s', description)

  # Start the download
  d = downloadPage(url.encode('ascii'), file_name)
  attach_logging_callbacks(d, description)
  return d
