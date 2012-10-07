#!/usr/bin/python

from twisted.internet import reactor

import monitor

monitor.setup()
reactor.run()
