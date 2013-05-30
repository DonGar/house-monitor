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


from twisted.web.client import getPage
from twisted.internet import base
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet import task
from twisted.python.urlpath import URLPath
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.util import redirectTo


from monitor.util import wake_on_lan


class _ConfigHandler(Resource):
  """Create a handler that records a button push."""
  isLeaf = True

  def __init__(self, status):
    Resource.__init__(self)
    self.status = status

  def render_GET(self, request):
    return self.render_POST(request)


class _ConfigActionHandler(_ConfigHandler):
  """Create a handler that records a button push."""

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    item_id = request.args['id'][0]
    action = request.args.get('action', [None])[0]

    redirect = self.handle_action(request, item_id, action)

    if redirect:
      return redirectTo(redirect.encode('ascii'), request)

    return 'Success'

  def handle_action(self, request, _item_id, _action):
    raise Exception('handle_action not implemented.')


class Button(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, request, item_id, action):

    # Rmember when the button was pushed
    status_pushed_uri = 'status://buttons/%s/pushed' % item_id
    self.status.set(status_pushed_uri, int(time.time()))

    if action is None:
      action = 'pushed'

    action_to_take = None
    try:
      action_uri = 'status://buttons/%s/action/%s' % (item_id, action)
      action_look_up_uri = self.status.get(action_uri)
      action_uri_full = URLPath.fromRequest(request).click(action_look_up_uri)
      print 'Performing action %s' % action_uri_full
      getPage(str(action_uri_full))
    except KeyError:
      pass # The action doesn't exist


class Email(_ConfigHandler):

  def __init__(self, status):
    _ConfigHandler.__init__(self, status)

  def render_POST(self, request):
    item_id = request.args['id'][0]
    uri = 'status://emails/%s' % item_id

    server_config = self.status.get_config()['server']['email']
    email_config = self.status.get(uri)
    attachements_config = email_config.get('attachment', [])

    email_server = server_config['server']
    port = int(server_config['port'])

    user = server_config['user']
    password = server_config['password']

    e_from = server_config['from']
    to = email_config.get('to', server_config['to'])
    subject = email_config.get('subject', '')
    body = email_config.get('body', '')

    # Download attachements
    for attachment_config in attachements_config:
      pass

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
    #                 'attachment; filename='%s'' % os.path.basename(attach))
    # msg.attach(part)

    mailServer = smtplib.SMTP(email_server, port)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(user, password)
    mailServer.sendmail(e_from, to, msg.as_string())
    mailServer.quit()

    return 'Success'


class Host(_ConfigActionHandler):
  """Create a handler that records a button push."""

  def handle_action(self, request, item_id, action):
    assert action in (None, 'sleep', 'wake')

    uri = 'status://hosts/%s' % item_id
    node = self.status.get(uri)

    # See if there is an action to take.
    if action and 'action' in node and action in node['action']:
      return node['action'][action]


class Log(_ConfigHandler):

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(status.get_log(), sort_keys=True, indent=4))
    request.finish()
    return status


class Restart(_ConfigHandler):

  def render_POST(self, _request):
    reactor.stop()
    return 'Success'


class Status(_ConfigHandler):

  def render_POST(self, request):
    logging.info('Request: %s', request.uri)

    # args['revision'] -> ['123'] if present at all
    revision = int(request.args.get('revision', [0])[0])

    notification = self.status.createNotification(revision)
    notification.addCallback(self.send_update, request)
    request.notifyFinish().addErrback(notification.errback)
    return server.NOT_DONE_YET

  def send_update(self, status, request):
    request.setHeader('content-type', 'application/json')
    request.write(json.dumps(status.get(), sort_keys=True, indent=4))
    request.finish()
    return status


class Wake(_ConfigHandler):

  def render_POST(self, request):
    for mac in request.args['target']:
      logging.info('received request for: %s', mac)
      wake_on_lan.wake_on_lan(mac)
    return 'Success'
