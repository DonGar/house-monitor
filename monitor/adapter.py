#!/usr/bin/python

import json
import logging
import os

from twisted.internet import inotify
from twisted.python import filepath

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))


# A lot of variables get defined inside setup, called from init.
# pylint: disable=W0201


class Adapter(object):
  def __init__(self, status, url, name, adapter_json):
    self.status = status
    self.url = url
    self.name = name
    self.adapter_json = adapter_json

    self.setup()

  def setup(self):
    assert False, 'setup not defined.'

  def stop(self):
    self.status.set(self.url, {})

class FileAdapter(Adapter):
  """This adapter is simple. It inserts a parsed JSON file into Status."""

  def setup(self):
    # Read our file, and attach it to the status.
    self.filename = self.adapter_json.get('filename', '%s.json' % self.name)
    self.filename = os.path.join(BASE_DIR, self.filename)

    # Perform the initial config file read.
    self.update_config_file()

    # Start watching the config file for updates.
    self.setup_notify()

  def update_config_file(self):
    logging.info('Adapting %s -> %s', self.filename, self.url)
    try:
      self.status.set(self.url, self.parse_config_file(self.filename))
    except ValueError:
      logging.info('ERROR Parsing %s', self.filename)


  def parse_config_file(self, filename):
    """Parse a config file in .json format."""
    config_file = os.path.join(BASE_DIR, filename)
    logging.info('Reading config %s', config_file)
    if os.path.exists(config_file):
      with open(config_file, 'r') as f:
        return json.load(f)

  def setup_notify(self):

    def notify(_ignored, updated_file, _mask):
      # Make sure it's actually the config file that was updated.
      if updated_file == filepath.FilePath(self.filename):
        self.update_config_file()

    logging.info('Watching for changes: %s', self.filename)
    self.notifier = inotify.INotify()
    self.notifier.startReading()
    self.notifier.watch(path=filepath.FilePath(os.path.dirname(self.filename)),
                        callbacks=[notify])

class WebAdapter(Adapter):

  _web_adapters = []

  def setup(self):
    self._web_adapters.append(self)
    self.status.set(self.url, {})

  @classmethod
  def web_updatable(cls, url):

    # Is the status URL to be updated inside a web adapter area.
    for adapter in cls._web_adapters:
      if url.startswith(adapter.url):
        return True

    return False

  @classmethod
  def _test_clear_state(cls):
    del cls._web_adapters[:]
