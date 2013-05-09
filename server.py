#!/usr/bin/python

from twisted.internet import reactor

import monitor.setup

monitor.setup.setup()
reactor.run()
