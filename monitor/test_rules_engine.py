#!/usr/bin/python

import mock
import unittest

import monitor.rules_engine
import monitor.status
import monitor.util.test_base


from twisted.internet import defer
from twisted.internet import task
from twisted.internet import reactor


# pylint: disable=W0212

import twisted.internet.base
twisted.internet.base.DelayedCall.debug = True

class TestRulesEngine(monitor.util.test_base.TestBase):

  def _setup_status_engine(self, rules):
    status = self._create_status({
          'server': {
            'latitude': '37.3861',
            'longitude': '-122.0839',
            'email_address': 'default@address.com',
          },
          'config': {
            'rule': rules
          },
          'values': {
            'set': 1
          }
        })

    engine = monitor.rules_engine.RulesEngine(status)

    return status, engine

  def _test_actions_fired(self, engine, expected_actions):
    patch = mock.patch('monitor.actions.handle_action', autospec=True)
    mocked = patch.start()

    # This deferred fires when the test is complete, and
    # the engine has shutdown.
    test_finished = defer.Deferred()

    def actions_fired_test():
      try:
        # Test results of test.
        mocked.assert_has_calls(expected_actions)
      finally:
        # Remove mock patch, and shutdown rules engine.
        patch.stop()
        engine.stop()
        #engine.stop().chainDeferred(test_finished)
        task.deferLater(reactor, 0.1, test_finished.callback, None)

    # Delay long enough for all processing callbacks to finish.
    task.deferLater(reactor, 0.1, actions_fired_test)

    return test_finished

  def test_no_rules(self):
    """Verify handle_action with status and http URL strings."""

    _status, engine = self._setup_status_engine({})

    self.assertEquals(len(engine._watch_rules), 0)
    self.assertEquals(len(engine._daily_rules), 0)
    self.assertEquals(len(engine._interval_rules), 0)
    self.assertEquals(len(engine._watch_helpers), 0)

    return self._test_actions_fired(engine, [])

  def test_watch_rule_create_shutdown(self):
    """Verify handle_action with status and http URL strings."""

    _status, engine = self._setup_status_engine({
                         'watch_test': {
                           'behavior': 'watch',
                           'value': 'status://values/set',
                           'action': 'take_action'
                         }
                       })

    self.assertEquals(len(engine._watch_rules), 1)
    self.assertEquals(len(engine._daily_rules), 0)
    self.assertEquals(len(engine._interval_rules), 0)
    self.assertEquals(len(engine._watch_helpers), 1)

    return self._test_actions_fired(engine, [])

  def test_watch_rule_fired(self):
    """Verify handle_action with status and http URL strings."""

    status, engine = self._setup_status_engine({
                         'watch_test': {
                           'behavior': 'watch',
                           'value': 'status://values/set',
                           'action': 'take_action'
                         }
                       })

    expected_actions = [mock.call(status, 'take_action')]
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/set', 2)

    return d

if __name__ == '__main__':
  unittest.main()
