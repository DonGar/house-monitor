#!/usr/bin/python

import unittest

import monitor.rules_engine
import monitor.status
import monitor.util.test_base
from twisted.internet import task
from twisted.internet import reactor


# pylint: disable=W0212

class TestRulesEngine(monitor.util.test_base.TestBase):

  def test_no_rules(self):
    """Verify handle_action with status and http URL strings."""
    status = self._create_status({
          'server': {
            'latitude': '37.3861',
            'longitude': '-122.0839',
            'email_address': 'default@address.com',
          },
        })

    engine = monitor.rules_engine.RulesEngine(status)

    self.assertEquals(len(engine._watch_rules), 0)
    self.assertEquals(len(engine._daily_rules), 0)
    self.assertEquals(len(engine._interval_rules), 0)

    self.assertEquals(len(engine._watch_helpers), 0)

    engine.stop()

  def test_watch_rule(self):
    """Verify handle_action with status and http URL strings."""
    status = self._create_status({
          'server': {
            'latitude': '37.3861',
            'longitude': '-122.0839',
            'email_address': 'default@address.com',
          },
          'config': {
            'rule': {
              'watch_test': {
                'behavior': 'watch',
                'value': 'status://values/set',
                'action': 'take_action'
              }
            }
          },
          'values': {
            'set': 1
          }
        })

    engine = monitor.rules_engine.RulesEngine(status)

    self.assertEquals(len(engine._watch_rules), 1)
    self.assertEquals(len(engine._daily_rules), 0)
    self.assertEquals(len(engine._interval_rules), 0)

    self.assertEquals(len(engine._watch_helpers), 1)

    engine.stop()

    # Delay long enough for cancelleds to take effect.
    return task.deferLater(reactor, 0.1, lambda : None)

if __name__ == '__main__':
  unittest.main()
