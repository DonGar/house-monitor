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
            'one': 1,
            'two': 1
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
        mocked.assert_has_calls(expected_actions, any_order=True)
      finally:
        # Remove mock patch, and shutdown rules engine.
        patch.stop()
        engine.stop().chainDeferred(test_finished)

    # Delay long enough for all processing callbacks to finish.
    task.deferLater(reactor, 0.01, actions_fired_test)

    return test_finished

  def test_no_rules(self):
    """Verify handle_action with status and http URL strings."""

    _status, engine = self._setup_status_engine({})

    self.assertEquals(len(engine._interval_helpers), 0)
    self.assertEquals(len(engine._daily_helpers), 0)
    self.assertEquals(len(engine._watch_helpers), 0)

    return self._test_actions_fired(engine, [])

  def test_watch_rule_create_shutdown(self):
    """Verify handle_action with status and http URL strings."""

    _status, engine = self._setup_status_engine({
                         'watch_test': {
                           'behavior': 'watch',
                           'value': 'status://values/one',
                           'action': 'take_action'
                         }
                       })

    self.assertEquals(len(engine._interval_helpers), 0)
    self.assertEquals(len(engine._daily_helpers), 0)
    self.assertEquals(len(engine._watch_helpers), 1)

    return self._test_actions_fired(engine, [])

  def test_watch_rule_fired(self):
    """Verify handle_action with status and http URL strings."""

    status, engine = self._setup_status_engine({
                         'watch_test': {
                           'behavior': 'watch',
                           'value': 'status://values/one',
                           'action': 'take_action'
                         }
                       })

    expected_actions = [mock.call(status, 'take_action')]
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/one', 2)

    return d

  def test_watch_rule_fired_twice(self):
    """Verify handle_action with status and http URL strings."""

    status, engine = self._setup_status_engine({
                         'watch_test': {
                           'behavior': 'watch',
                           'value': 'status://values/one',
                           'action': 'take_action'
                         }
                       })

    expected_actions = [mock.call(status, 'take_action'),
                        mock.call(status, 'take_action')]
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/one', 2)

    # If we just set the status a second time, the two changes would be
    # collapsed into a single notify. By delaying the second 'set', we
    # ensure the rules engine is notified twice.
    task.deferLater(reactor, 0, status.set, 'status://values/one', 3)

    return d

  def test_watch_rules_fired(self):
    """Verify handle_action with status and http URL strings."""

    status, engine = self._setup_status_engine({
                         'watch_test1': {
                           'behavior': 'watch',
                           'value': 'status://values/one',
                           'action': 'take_action1'
                         },
                         'watch_test2': {
                           'behavior': 'watch',
                           'value': 'status://values/two',
                           'action': 'take_action2'
                         }
                       })

    expected_actions = [mock.call(status, 'take_action1'),
                        mock.call(status, 'take_action2')]
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/one', 2)
    status.set('status://values/two', 2)

    return d


if __name__ == '__main__':
  unittest.main()
