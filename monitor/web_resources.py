#!/usr/bin/python

import json
import logging
import time

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders
import os


from twisted.internet import base
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet import task
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.util import redirectTo




from monitor.util import wake_on_lan


class _ConfigHandler(Resource):
  """Create a handler that records a button push."""
  isLeaf = True

  def render_GET(self, request):
    return self.render_POST(request)


class _ConfigActionHandler(_ConfigHandler):
  """Create a handler that records a button push."""
  def __init__(self, status):
    self.status = status

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    id = request.args['id'][0]
    action = request.args.get('action', [None])[0]

    redirect = self.handle_action(id, action)

    if redirect:
      return redirectTo(redirect.encode('ascii'), request)

    return "Success"

  def handle_action(self, id, action):
    raise Exception('handle_action not implemented.')


class Button(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, id, action):
    if action is None:
      action = 'on'

    assert action in ('on', 'off')

    uri = 'status://buttons/%s' % id
    node = self.status.get(uri)

    # Rmember when the button was pushed
    status_pushed = 'status://buttons/%s/pushed' % id
    self.status.set(status_pushed, int(time.time()))

    # Remember if it was turned on or off.
    button_state = 'status://buttons/%s/state' % id
    self.status.set(button_state, action == 'on')


class Email(_ConfigHandler):

  def __init__(self, email_config, status):
    self.email_config = email_config
    self.status = status

  def render_POST(self, request):
    id = request.args['id'][0]
    uri = 'status://emails/%s' % id
    node = self.status.get(uri)

    server, port = self.email_config['server'].split(':')
    port = int(port)

    user = self.email_config['user']
    password = self.email_config['password']

    e_from = self.email_config['from']
    to = node.get('to', self.email_config['to'])
    subject = node.get('subject', '')
    body = node.get('body', '')
    attachements = node.get('attachment', [])

    # Send the mail.
    msg = MIMEMultipart()

    msg['From'] = e_from
    msg['To'] = to
    msg['Subject'] = subject

    msg.attach(MIMEText(body))

    # part = MIMEBase('application', 'octet-stream')
    # part.set_payload(open(attach, 'rb').read())
    # Encoders.encode_base64(part)
    # part.add_header('Content-Disposition',
    #                 'attachment; filename="%s"' % os.path.basename(attach))
    # msg.attach(part)

    mailServer = smtplib.SMTP(server, port)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(user, password)
    mailServer.sendmail(e_from, to, msg.as_string())
    mailServer.quit()


class Host(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, id, action):
    assert action in (None, 'sleep', 'wake')

    uri = 'status://hosts/%s' % id
    node = self.status.get(uri)

    # See if there is an action to take.
    if action and 'action' in node and action in node['action']:
      return node['action'][action]


class Log(_ConfigHandler):

  def __init__(self, status):
    self.status = status

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader("content-type", "application/json")
    request.write(json.dumps(status.get_log(), sort_keys=True, indent=4))
    request.finish()
    return status


class Restart(_ConfigHandler):

  def render_POST(self, request):
    reactor.stop()
    return "Success"


class Status(_ConfigHandler):

  def __init__(self, status):
    self.status = status

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader("content-type", "application/json")
    request.write(json.dumps(status.get(), sort_keys=True, indent=4))
    request.finish()
    return status


class Wake(_ConfigHandler):

  def render_POST(self, request):
    for mac in request.args["target"]:
      logging.info('received request for: %s', mac)
      wake_on_lan(mac)
    return "Success"
