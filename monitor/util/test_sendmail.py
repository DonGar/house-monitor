#!/usr/bin/python

import mock
import unittest

import monitor.util.sendemail
import monitor.util.test_base


class TestEmailUtil(monitor.util.test_base.TestBase):

  def __init__(self, *args, **kwargs):
    super(TestEmailUtil, self).__init__(*args, **kwargs)

    status_values = {
      'server': {
        'email_address': 'server@address.com',
      },
    }

    self.status = self._create_status(status_values)

  def test_email(self):
    """Test Sending Email."""
    to = 'dest@address.com'
    subject = 'msg subject'
    body = 'msg body'
    attachments = []

    with mock.patch('smtplib.SMTP.sendmail', autospec=True) as mocked:
      monitor.util.sendemail.email(self.status, to, subject, body, attachments)
      mocked.assert_called_once_with(mock.ANY,
                                     'server@address.com',
                                     ['dest@address.com'],
                                     mock.ANY)

  def test_multi_email(self):
    """Test Sending Email."""
    to = 'dest@address.com, second@address.com'
    subject = 'msg subject'
    body = 'msg body'
    attachments = []

    with mock.patch('smtplib.SMTP.sendmail', autospec=True) as mocked:
      monitor.util.sendemail.email(self.status, to, subject, body, attachments)
      mocked.assert_called_once_with(mock.ANY,
                                     'server@address.com',
                                     ['dest@address.com', 'second@address.com'],
                                     mock.ANY)



if __name__ == '__main__':
  unittest.main()
