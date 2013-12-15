#!/usr/bin/python

import datetime
import logging
import os

from pysnmp.entity.rfc3413.oneliner import cmdgen

from twisted.internet import protocol
from twisted.internet import threads

import monitor.adapter

from monitor.util import repeat

# A lot of variables get defined inside setup, called from init.
# pylint: disable=W0201


class SnmpError(Exception):
  pass


class SnmpAdapter(monitor.adapter.Adapter, protocol.Protocol):

  def setup(self):
    # We expect to receive a list of host names here.
    self._hosts = self.adapter_json.get('hosts')

    self.status.set(self.url, {})

    # Start refreshing SNMP information every 10 seconds.
    timing_helper = repeat.interval_helper(datetime.timedelta(seconds=15))
    repeat.call_repeating(timing_helper, self.update_hosts)

  def update_hosts(self):
    for host in self._hosts:
      self.find_host_values(host)

  def find_host_values(self, host):
    host_url = os.path.join(self.url, host)

    def handle_error(e):
      logging.error(e.getTraceback())
      self.status.set(host_url, {'error': e.getErrorMessage()})

    d = threads.deferToThread(self.read_host_values, host)
    d.addCallbacks(lambda v: self.status.set(host_url, v), handle_error)

  def read_host_values(self, host):
    cmdGen = cmdgen.CommandGenerator()

    errorIndication, errorStatus, errorIndex, varBindTable = cmdGen.nextCmd(
        cmdgen.CommunityData('public'),
        cmdgen.UdpTransportTarget((host, 161)),
        cmdgen.MibVariable('IF-MIB', '').loadMibs(),
        lexicographicMode=True, maxRows=100,
        ignoreNonIncreasingOid=True,
        lookupNames=True,
        lookupValues=True
    )

    if errorIndication:
      raise SnmpError('%s: %s' % (host, errorIndication))

    if errorStatus:
      raise SnmpError('SNMP Walk on %s: %s at %s' % (
          host,
          errorStatus.prettyPrint(),
          errorIndex and varBindTable[-1][int(errorIndex)-1] or '?'))

    values = {}

    for varBindTableRow in varBindTable:
      for name, val in varBindTableRow:
        values[name.prettyPrint()] = val.prettyPrint()

    return values
