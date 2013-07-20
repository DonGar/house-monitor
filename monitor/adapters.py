#!/usr/bin/python

import logging

import monitor

# A lot of variables get defined inside setup, called from init.
# pylint: disable=W0201


class Adapter:
  def __init__(self, status, url, name, adapter_json):
    self.status = status
    self.url = url
    self.name = name
    self.adapter_json = adapter_json

    self.setup()

  def setup(self):
    assert False, 'setup not defined.'


class FileAdapter(Adapter):
  """This adapter is simple. It inserts a parsed JSON file into Status."""

  def setup(self):
    # Read our file, and attach it to the status.
    self.filename = self.adapter_json.get('filename', '%s.json' % self.name)

    logging.info('Adapting %s -> %s', self.filename, self.url)
    self.status.set(self.url, monitor.setup.parse_config_file(self.filename))


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
