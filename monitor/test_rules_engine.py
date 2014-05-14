#!/usr/bin/python

import datetime
import unittest

import monitor.rules_engine
import monitor.status
import monitor.util.test_base


from twisted.internet import defer
from twisted.internet import task
from twisted.internet import reactor


# pylint: disable=W0212

class TestRulesEngine(monitor.util.test_base.TestBase):

  def _setup_status_engine(self, rules, utc_nows=()):

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

    # mutable version of times list we received.
    nows = list(utc_nows)

    # An identical engine, except it sequentially uses our defined times.
    class TestEngine(monitor.rules_engine.RulesEngine):
      def utc_now(self):
        return nows.pop(0)

    return status, TestEngine(status, monitor.test_actions.MockActionManager())

  def _test_actions_fired(self, engine, expected_actions, delay=0.01):
    # This deferred fires when the test is complete, and
    # the engine has shutdown.
    test_finished = defer.Deferred()

    def actions_fired_test():
      try:
        # Test results of test.
        self.assertEqual(engine._action_manager.actions, expected_actions)
      finally:
        # Shutdown rules engine.
        engine.stop().chainDeferred(test_finished)

    # Delay long enough for all processing callbacks to finish.
    task.deferLater(reactor, delay, actions_fired_test)

    return test_finished

  def test_rules_helper(self):
    """Can our test_helper base class start and stop?"""

    # Uses 'None' for the engine. A bit brittle.
    h = monitor.rules_engine._RuleHelper(None,
                                         self._create_status(),
                                         'helper_name',
                                         {'behavior': 'test'})
    h.start()
    h.stop()

  def test_no_rules(self):
    """Verify handle_action with status and http URL strings."""
    _status, engine = self._setup_status_engine({})

    self.assertEquals(len(engine._helpers), 0)

    return self._test_actions_fired(engine, [])

  #
  # Watch Rule Tests
  #

  def test_watch_rule_create_shutdown(self):
    """Setup the rules engine with a single watch rule and shut it down."""
    _status, engine = self._setup_status_engine({
        'watch_test': {
            'behavior': 'watch',
            'value': 'status://values/one',
            'action': 'take_action'
        }
    })

    self.assertEquals(len(engine._helpers), 1)
    return self._test_actions_fired(engine, [])

  def test_watch_rule_fired(self):
    """Setup and fire a single watch rule in the rules_engine."""
    status, engine = self._setup_status_engine({
        'watch_test': {
            'behavior': 'watch',
            'value': 'status://values/one',
            'action': 'take_action'
        }
    })

    expected_actions = ['status://config/rule/watch_test/action']
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/one', 2)

    return d

  def test_watch_rule_value_cleared(self):
    """Setup and clear value a watch rule watches."""
    status, engine = self._setup_status_engine({
        'watch_test': {
            'behavior': 'watch',
            'value': 'status://values/one',
            'action': 'take_action'
        }
    })

    # If a value is cleared, we shouldn't fire at all.
    expected_actions = []
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values', {})

    return d

  def test_watch_rule_fired_twice(self):
    """Setup and fire a single watch rule in the rules_engine twice."""
    status, engine = self._setup_status_engine({
        'watch_test': {
            'behavior': 'watch',
            'value': 'status://values/one',
            'action': 'take_action'
        }
    })

    expected_actions = ['status://config/rule/watch_test/action',
                        'status://config/rule/watch_test/action']
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/one', 2)
    status.set('status://values/one', 3)

    return d

  def test_watch_rules_fired(self):
    """Setup and fire two watch rules in the rules_engine."""
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

    expected_actions = ['status://config/rule/watch_test1/action',
                        'status://config/rule/watch_test2/action']
    d = self._test_actions_fired(engine, expected_actions)

    status.set('status://values/one', 2)
    status.set('status://values/two', 2)

    return d

  #
  # Daily Rule Tests
  #

  def test_daily_rule_create_shutdown(self):
    """Setup the rules engine with a single daily rule and shut it down."""
    # time is hours before the rule should fire.
    time1 = datetime.datetime(2000, 1, 2, 3, 4, 5, 0)
    time2 = time1 + datetime.timedelta(hours=1)

    _status, engine = self._setup_status_engine(
        {
            'daily_test': {
                'behavior': 'daily',
                'time': '12:34:56',
                'action': 'take_action'
            }
        },
        utc_nows=(time1, time2)
    )

    self.assertEquals(len(engine._helpers), 1)
    return self._test_actions_fired(engine, [])

  def test_daily_rule_time_fire(self):
    """Setup the rules engine with a single daily rule and shut it down."""
    # time1 0.005 seconds before rule should fire.
    time1 = datetime.datetime(2000, 1, 2, 3, 4, 5, 995000)
    time2 = time1 + datetime.timedelta(hours=1)

    _, engine = self._setup_status_engine(
        {
            'daily_test': {
                'behavior': 'daily',
                'time': '19:04:06',
                'action': 'take_action'
            }
        },
        utc_nows=(time1, time2)
    )

    return self._test_actions_fired(
        engine,
        ['status://config/rule/daily_test/action'])

  def test_daily_rule_sunrise_fire(self):
    """Setup the rules engine with a single daily rule and shut it down."""
    # time1 ~0.005 seconds before rule should fire.
    time1 = datetime.datetime(2000, 1, 2, 15, 47, 48, 310000)
    time2 = time1 + datetime.timedelta(hours=1)

    _, engine = self._setup_status_engine(
        {
            'daily_test_sunrise': {
                'behavior': 'daily',
                'time': 'sunrise',
                'action': 'take_action'
            }
        },
        utc_nows=(time1, time2)
    )

    return self._test_actions_fired(
        engine,
        ['status://config/rule/daily_test_sunrise/action'],
        delay=0.2)

  def test_daily_rule_sunset_fire(self):
    """Setup the rules engine with a single daily rule and shut it down."""
    # time1 ~0.005 seconds before rule should fire.
    time1 = datetime.datetime(2000, 1, 2, 4, 58, 50, 570000)
    time2 = time1 + datetime.timedelta(hours=1)

    _, engine = self._setup_status_engine(
        {
            'daily_test_sunset': {
                'behavior': 'daily',
                'time': 'sunset',
                'action': 'take_action'
            }
        },
        utc_nows=(time1, time2)
    )

    return self._test_actions_fired(
        engine,
        ['status://config/rule/daily_test_sunset/action'],
        delay=0.2)

  #
  # Interval Rule Tests
  #

  def test_interval_rule_create_shutdown(self):
    """Setup the rules engine with a single interval rule and shut it down."""
    # time1 ~0.005 seconds before rule should fire.
    time1 = datetime.datetime(2000, 1, 2, 3, 4, 5, 0)
    time2 = time1 + datetime.timedelta(minutes=1)

    # Create a rule on 5 minute intervals.
    _status, engine = self._setup_status_engine(
        {
            'interval_test_shutdown': {
                'behavior': 'interval',
                'time': '00:05:00',
                'action': 'take_action'
            }
        },
        utc_nows=(time1, time2)
    )

    self.assertEquals(len(engine._helpers), 1)
    return self._test_actions_fired(engine, [])

  def test_interval_rule_time_fire(self):
    """Setup the rules engine with a single interval rule and shut it down."""
    # time1 ~0.005 seconds before rule should fire.
    time1 = datetime.datetime(2000, 1, 2, 3, 4, 59, 995000)
    time2 = time1 + datetime.timedelta(minutes=1)

    # Create a rule on 5 minute intervals.
    _, engine = self._setup_status_engine(
        {
            'interval_test': {
                'behavior': 'interval',
                'time': '00:05:00',
                'action': 'take_action'
            }
        },
        utc_nows=(time1, time2)
    )

    return self._test_actions_fired(
        engine,
        ['status://config/rule/interval_test/action'])


if __name__ == '__main__':
  unittest.main()
