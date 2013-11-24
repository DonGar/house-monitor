#!/usr/bin/python

import logging
import os

from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import serialport

import monitor.adapter

# A lot of variables get defined inside setup, called from init.
# pylint: disable=W0201


class IOGearAdapter(monitor.adapter.Adapter, protocol.Protocol):

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

    # Send a query message. This will get a reponse to dataReceived and populate
    # the active_url.
    self.sendData('?')

    # Start watching target.
    self.status.deferred(url=self.target_url).addCallback(self._target_updated)

  def dataReceived(self, data):
    """Receive serial data from the IOGear Arduino hardware."""
    self.status.set(self.active_url, data.strip())

  def sendData(self, data):
    """Send serial data to the IOGear Arduino hardware."""
    return self.transport.writeSequence(data.encode('ascii'))

  def _target_updated(self, _status_update):
    # If the target exists, send it to the serial port, then
    # clear the target.
    target = self.status.get(self.target_url)
    if target is not None:
      self.sendData(target)
      self.status.set(self.target_url, None)

    # Find out about the next update.
    self.status.deferred(url=self.target_url).addCallback(self._target_updated)
