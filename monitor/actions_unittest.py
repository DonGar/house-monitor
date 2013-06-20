#!/usr/bin/python

import mock
import unittest

import monitor.actions
import monitor.status

import monitor.util.action
import monitor.util.wake_on_lan


class TestActionHandlers(unittest.TestCase):

  def __init__(self, *args, **kwargs):
    unittest.TestCase.__init__(self, *args, **kwargs)

    status_values = {
      'server': {
        'email_address': 'default@address.com',
        'downloads': '/downloads',
      },

      'reference_indirect': 'status://url',
      'url': 'http://some/url',

      'value': 'status_value',
    }

    self.status = monitor.status.Status(status_values, None, None)

  def test_handle_action_url(self):
    """Verify handle_action with status and http URL strings."""

    with mock.patch('monitor.util.action.get_page_wrapper') as mocked:
      monitor.actions.handle_action(self.status, 'http://some/url')
      mocked.assert_called_once_with('http://some/url')

    with mock.patch('monitor.util.action.get_page_wrapper') as mocked:
      monitor.actions.handle_action(self.status, 'https://some/url')
      mocked.assert_called_with('https://some/url')

    with mock.patch('monitor.util.action.get_page_wrapper') as mocked:
      monitor.actions.handle_action(self.status, 'status://url')
      mocked.assert_called_with('http://some/url')

    with mock.patch('monitor.util.action.get_page_wrapper') as mocked:
      monitor.actions.handle_action(self.status, 'status://reference_indirect')
      mocked.assert_called_with('http://some/url')

  def test_handle_action_fetch(self):
    """Verify handle_action with JSON fetch action nodes."""

    action_fetch = {
      'action': 'fetch_url',
      'url': 'http://some/url',
    }

    with mock.patch('monitor.util.action.get_page_wrapper') as mocked:
      monitor.actions.handle_action(self.status, action_fetch)
      mocked.assert_called_once_with('http://some/url')

    action_fetch_download = {
      'action': 'fetch_url',
      'url': 'http://some/url',
      'download_name': 'my_download_name'
    }

    with mock.patch('monitor.util.action.download_page_wrapper') as mocked:
      monitor.actions.handle_action(self.status, action_fetch_download)
      mocked.assert_called_once_with('http://some/url',
                                     '/downloads/my_download_name')

  def test_handle_action_set(self):
    """Verify handle_action with JSON set action nodes."""

    action_set_value = {
      'action': 'set',
      'value': True,
      'dest': 'status://target',
    }

    monitor.actions.handle_action(self.status, action_set_value)
    self.assertEqual(self.status.get('status://target'), True)

    action_set_complex = {
      'action': 'set',
      'value': { 'foo': 'bar'},
      'dest': 'status://target',
    }

    monitor.actions.handle_action(self.status, action_set_complex)
    self.assertEqual(self.status.get('status://target'), { 'foo': 'bar'})

    action_set_src = {
      'action': 'set',
      'src': 'status://value',
      'dest': 'status://target',
    }

    monitor.actions.handle_action(self.status, action_set_src)
    self.assertEqual(self.status.get('status://target'), 'status_value')

  def test_handle_action_wol(self):
    """Verify handle_action with JSON wol action nodes."""

    action_wol = {
      'action': 'wol',
      'mac': '11:22:33:44:55:66',
    }

    with mock.patch('monitor.util.wake_on_lan.wake_on_lan') as mocked:
      monitor.actions.handle_action(self.status, action_wol)
      mocked.assert_called_once_with('11:22:33:44:55:66')

  def test_handle_action_ping(self):
    """Verify handle_action with JSON ping action nodes."""

    action_ping = {
      'action': 'ping',
      'hostname': 'foo',
      'dest': 'status://target',
    }

    with mock.patch('monitor.util.ping.ping',
                    return_value='ping_result') as mocked:
      monitor.actions.handle_action(self.status, action_ping)
      mocked.assert_called_once_with('foo')
      self.assertEqual(self.status.get('status://target'), 'ping_result')

  def test_handle_action_email(self):
    """Verify handle_action with JSON email action nodes."""

    action_email_simple = {
      'action': 'email'
    }

    with mock.patch('monitor.util.sendemail.email') as mocked:
      monitor.actions.handle_action(self.status, action_email_simple)
      mocked.assert_called_once_with('default@address.com', '', '')

    action_email_complex = {
      'action': 'email',

      'to': 'to@address.com',
      'subject': 'subject line',
      'body': 'message body',
    }

    with mock.patch('monitor.util.sendemail.email') as mocked:
      monitor.actions.handle_action(self.status, action_email_complex)
      mocked.assert_called_once_with('to@address.com',
                                     'subject line',
                                     'message body')


  def test_handle_action_email_attachmehnts(self):
    """Verify handle_action with JSON email action nodes."""

    action_email = {
      'action': 'email',

      'to': 'to@address.com',
      'subject': 'subject line',
      'body': 'message body',
      'attachements': [
        {
          'url': 'http://resource/url',
          'download_name': 'foo.jpg',
          'preserve': True
        },
        {
          'url': 'http://resource/url',
          'download_name': 'foo.jpg',
          'preserve': False
        },
        {
          'url': 'http://resource/url',
          'download_name': 'foo.jpg',
        },
      ]
    }

    with mock.patch('monitor.util.sendemail.email') as mocked:
      monitor.actions.handle_action(self.status, action_email)
      mocked.assert_called_once_with('to@address.com',
                                     'subject line',
                                     'message body')


if __name__ == '__main__':
  unittest.main()
