#!/usr/bin/python

import logging
import smtplib
import mimetypes


from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def email(status, to, subject, body, attachments):
  logging.debug('Action: Email %s about %s: %s', to, subject, body)

  me = status.get('status://server/email_address')

  # Create the container (outer) email message.
  msg = MIMEMultipart()
  msg['Subject'] = subject
  msg['From'] = me
  msg['To'] = to

  msg.attach(MIMEText(body, 'plain'))

  # Assume we know that the image files are all in PNG format
  for filename in attachments:
    # Open the files in binary mode.  Let the MIMEImage class automatically
    # guess the specific image type.
    with open(filename, 'rb') as fp:
      img = MIMEImage(fp.read())
    msg.attach(img)

  # Send the email via our own SMTP server.
  s = smtplib.SMTP('localhost')
  s.sendmail(me, to, msg.as_string())
  s.quit()



if __name__ == "__main__":
  email(None, 'dgarrett@acm.org', 'Test Message', 'Boo',
        ['/home/dgarrett/tmp/house/test-1371419850.jpg'])
