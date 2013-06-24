#!/usr/bin/python

import mock
import unittest

import monitor.rules_engine
import monitor.status


# pylint: disable=W0212

class TestRulesEngine(unittest.TestCase):

  def __init__(self, *args, **kwargs):
    unittest.TestCase.__init__(self, *args, **kwargs)

    status_values = {
      'server': {
        'latitude': '37.3861',
        'longitude': '-122.0839',
        'email_address': 'default@address.com',
      },
    }

    self.status = monitor.status.Status(status_values, None, None)

  def test_no_rules(self):
    """Verify handle_action with status and http URL strings."""
    engine = monitor.rules_engine.RulesEngine(self.status)

    self.assertEquals(len(engine._watch_rules), 0)
    self.assertEquals(len(engine._daily_rules), 0)
    self.assertEquals(len(engine._interval_rules), 0)

    self.assertEquals(len(engine._watch_last_seen), 0)

if __name__ == '__main__':
  unittest.main()
