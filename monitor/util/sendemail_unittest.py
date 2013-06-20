#!/usr/bin/python

import mock
import unittest

import monitor.util.sendemail


class TestEmailUtil(unittest.TestCase):

  def __init__(self, *args, **kwargs):
    unittest.TestCase.__init__(self, *args, **kwargs)

    status_values = {
      'server': {
        'email_address': 'default@address.com',
      },
    }

    self.status = monitor.status.Status(status_values, None, None)

  def test_email(self):
    """Test Sending Email."""
    to = 'dest@address.com'
    subject = 'msg subject'
    body = 'msg body'
    attachments = []

    with mock.patch('smtplib.SMTP.sendmail') as mocked:
      monitor.util.sendemail.email(self.status, to, subject, body, attachments)


if __name__ == '__main__':
  unittest.main()
