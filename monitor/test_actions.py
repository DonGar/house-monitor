#!/usr/bin/python

import mock
import unittest

from twisted.internet import defer

import monitor.actions
import monitor.status

import monitor.util.action
import monitor.util.test_base
import monitor.util.wake_on_lan

STATUS_VALUES = {
  'server': {
    'email_address': 'default@address.com',
    'downloads': '/downloads',
  },

  'reference_indirect': 'status://url',
  'url': 'http://some/url',

  'value': 'status_value',
}


class TestActionHandlers(monitor.util.test_base.TestBase):

  def __init__(self, *args, **kwargs):
    super(TestActionHandlers, self).__init__(*args, **kwargs)

    self.status = self._create_status(STATUS_VALUES)

  def test_handle_action_delayed(self):
    """Verify handle_action with a delayed action."""

    action_delayed = {
      'action': 'delayed',
      'seconds': 1,
      'delayed_action': {
          'action': 'wol',
          'mac': '11:22:33:44:55:66',
        }
    }

    patch = mock.patch('monitor.util.wake_on_lan.wake_on_lan',
                       autospec=True)
    mocked = patch.start()

    def verify_delayed_action(_):
      mocked.assert_called_once_with('11:22:33:44:55:66')
      patch.stop()

    d = monitor.actions.handle_action(self.status, action_delayed)
    d.addCallback(verify_delayed_action)
    return d

  def test_handle_action_url(self):
    """Verify handle_action with status and http URL strings."""

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, 'http://some/url')
      mocked.assert_called_once_with('http://some/url')

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, 'https://some/url')
      mocked.assert_called_with('https://some/url')

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, 'status://url')
      mocked.assert_called_with('http://some/url')

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, 'status://reference_indirect')
      mocked.assert_called_with('http://some/url')

  def test_handle_action_list(self):
    """Verify handle_action with lists of actions.."""

    action_list = ['http://some/url', 'http://some/other/url']
    expected_actions = [mock.call('http://some/url'),
                        mock.call('http://some/other/url')]

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, action_list)
      mocked.assert_has_calls(expected_actions)

    nest_action_list = ['http://some/url',
                        ['http://other/url', 'http://third/url']]
    nest_expected_actions = [mock.call('http://some/url'),
                             mock.call('http://other/url'),
                             mock.call('http://third/url')]

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, nest_action_list)
      mocked.assert_has_calls(nest_expected_actions)


  def test_handle_action_fetch(self):
    """Verify handle_action with JSON fetch action nodes."""

    action_fetch = {
      'action': 'fetch_url',
      'url': 'http://some/url',
    }

    with mock.patch('monitor.util.action.get_page_wrapper',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, action_fetch)
      mocked.assert_called_once_with('http://some/url')

    action_fetch_download = {
      'action': 'fetch_url',
      'url': 'http://some/url',
      'download_name': 'my_download_name'
    }

    with mock.patch('monitor.util.action.download_page_wrapper',
                    autospec=True) as mocked:
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

    with mock.patch('monitor.util.wake_on_lan.wake_on_lan',
                    autospec=True) as mocked:
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
                    return_value='ping_result',
                    autospec=True) as mocked:
      monitor.actions.handle_action(self.status, action_ping)
      mocked.assert_called_once_with('foo')
      self.assertEqual(self.status.get('status://target'), 'ping_result')

  def test_handle_action_email_default(self):
    """Verify handle_action with JSON email action nodes."""

    action_email = {
      'action': 'email'
    }

    with mock.patch('monitor.util.sendemail.email', autospec=True) as mocked:
      monitor.actions.handle_action(self.status, action_email)
      mocked.assert_called_once_with(self.status,
                                     'default@address.com',
                                     '',
                                     '',
                                     [])

  def test_handle_action_email_explicit(self):
    action_email = {
      'action': 'email',

      'to': 'to@address.com',
      'subject': 'subject line',
      'body': 'message body',
    }

    with mock.patch('monitor.util.sendemail.email', autospec=True) as mocked:
      monitor.actions.handle_action(self.status, action_email)
      mocked.assert_called_once_with(self.status,
                                     'to@address.com',
                                     'subject line',
                                     'message body',
                                     [])

  def test_handle_action_email_attachments(self):
    """Verify handle_action with JSON email action nodes."""

    url_preserve = 'http://resource/url/preserve'
    file_preserve = '/downloads/foo_preserve.jpg'

    url_temp = 'http://resource/url/temp'
    file_temp = '/tmpdir/foo_temp.jpg'

    url_default = 'http://resource/url/default'
    file_default = '/tmpdir/foo_default.jpg'

    action_email = {
      'action': 'email',

      'to': 'to@address.com',
      'subject': 'subject line',
      'body': 'message body',
      'attachments': [
        {
          'url': url_preserve,
          'download_name': 'foo_preserve.jpg',
          'preserve': True
        },
        {
          'url': url_temp,
          'download_name': 'foo_temp.jpg',
          'preserve': False
        },
        {
          'url': url_default,
          'download_name': 'foo_default.jpg'
        }
      ]
    }

    download_deferreds = []

    def downlad_page_side_effect(*_args, **_kwargs):
      d = defer.Deferred()
      download_deferreds.append(d)
      return d

    with mock.patch('tempfile.mkdtemp', return_value='/tmpdir'):
      with mock.patch('shutil.rmtree') as rmtree:
        with mock.patch('monitor.util.sendemail.email',
                        autospec=True) as email:
          with mock.patch('monitor.util.action.download_page_wrapper',
                          autospec=True,
                          side_effect=downlad_page_side_effect) as download:

            # Run the initial handling.
            monitor.actions.handle_action(self.status, action_email)

            # Check that the downloads were setup as expected.
            download.assert_has_calls([mock.call(url_preserve, file_preserve),
                                       mock.call(url_temp, file_temp),
                                       mock.call(url_default, file_default)])

            # 'Complete' the downloads.
            self.assertEqual(3, len(download_deferreds))
            for d in download_deferreds:
              d.callback(None)

          # Ensure we 'sent' the mail.
          email.assert_called_once_with(self.status,
                                        'to@address.com',
                                        'subject line',
                                        'message body',
                                        [file_preserve,
                                         file_temp,
                                         file_default])

        # Ensure we cleanup.
        rmtree.assert_called_once_with('/tmpdir')

if __name__ == '__main__':
  unittest.main()
