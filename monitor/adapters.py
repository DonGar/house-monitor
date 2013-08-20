#!/usr/bin/python

import json
import logging
import os

from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import serialport

BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))


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
    self.status.set(self.url, self.parse_config_file(self.filename))

  def parse_config_file(self, filename):
    """Parse a config file in .json format."""
    config_file = os.path.join(BASE_DIR, filename)
    logging.info('Reading config %s', config_file)
    if os.path.exists(config_file):
      with open(config_file, 'r') as f:
        return json.load(f)


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

class IOGearAdapter(Adapter, protocol.Protocol):

  def setup(self):
    # Read our file, and attach it to the status.
    self.port = self.adapter_json.get('port')
    self.name = self.adapter_json.get('name', 'iogear')

    logging.info('IOGear %s on port %s', self.name, self.port)

    # Active stores which port is active.
    self.active_url = os.path.join(self.url, 'iogear', self.name, 'active')
    self.target_url = os.path.join(self.url, 'iogear', self.name, 'target')

    # Setup our state values with None.
    self.status.set(self.active_url, None)
    self.status.set(self.target_url, None)

    self.serial_port = serialport.SerialPort(self, self.port, reactor)

    # Send a bogus message. This will get a reponse to dataReceived and populate
    # the active_url.
    self.sendData('u')

    # Start watching target.
    self.status.deferred(url=self.target_url).addCallback(self._target_updated)

  def dataReceived(self, data):
    """Receive serial data from the IOGear Arduino hardware."""
    print "Received: %s" % data
    self.status.set(self.active_url, data.strip())

  def sendData(self, data):
    """Send serial data to the IOGear Arduino hardware."""
    print "Sending: %s" % data
    return self.transport.writeSequence(data.encode('ascii'))

  def _target_updated(self, status_update):
    # If the target exists, send it to the serial port, then
    # clear the target.
    target = status_update['status']
    if target is not None:
      self.sendData(target)
      self.status.set(self.target_url, None)

    # Find out about the next update.
    self.status.deferred(url=self.target_url).addCallback(self._target_updated)
