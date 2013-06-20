#!/usr/bin/python

import unittest
import mock

import monitor.status


class TestStatus(unittest.TestCase):

  def __init__(self, *args, **kwargs):
    unittest.TestCase.__init__(self, *args, **kwargs)

    status_values = {
      'server': {
        'email_address': 'default@address.com'
      },
    }

    self.status = monitor.status.Status(status_values, None, None)

  def test_stuff(self):
    """Verify handle_action with status and http URL strings."""
    pass


if __name__ == '__main__':
  unittest.main()
