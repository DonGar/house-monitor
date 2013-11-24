#!/usr/bin/python

import logging
import os

from pysnmp.entity.rfc3413.oneliner import cmdgen

from twisted.internet import protocol

import monitor.adapter

# A lot of variables get defined inside setup, called from init.
# pylint: disable=W0201


class SnmpError(Exception):
  pass


class SnmpAdapter(monitor.adapter.Adapter, protocol.Protocol):

  def setup(self):
    # We expect to receive a list of host names here.
    self._hosts = self.adapter_json.get('hosts')

    self.status.set(self.url, {})

    for host in self._hosts:
      host_url = os.path.join(self.url, host)
      self.status.set(host_url, {})

      self.host_update(host)

  def host_update(self, host):
    host_url = os.path.join(self.url, host)

    try:
      self.status.set(host_url, self.read_host_values(host))
    except SnmpError as e:
      logging.error(e)
      self.status.set(host_url, {})

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
