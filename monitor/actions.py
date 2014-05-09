#!/usr/bin/python

import logging
import shutil
import tempfile
import urlparse

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task

import monitor.status
import monitor.util.action
import monitor.util.sendemail
import monitor.util.ping
import monitor.util.wake_on_lan


class Error(Exception):
  pass


class InvalidAction(Error):
  pass


class UnknownAction(Error):
  pass


class ActionManager(object):
  """Manager for performing 'actions'."""

  def __init__(self, status):
    self.status = status
    self.action_mapping = {
        'delayed': self._handle_delayed_action,
        'fetch_url': self._handle_fetch_action,
        'set': self._handle_set_action,
        'increment': self._handle_increment_action,
        'wol': self._handle_wol_action,
        'ping': self._handle_ping_action,
        'email': self._handle_email_action,
    }

  def handle_action(self, action):
    """Perform the action specified by the json node 'action'.

    action can be a variety of things which are handled differently.

      A status URL: 'status://foo/bar'
      A standard URL: 'http://foo/bar'
      [<action>,...]
      { 'action': '', ...}
    """

    try:
      # If action is a URL.
      parsed_url = None
      try:
        parsed_url = urlparse.urlparse(action)
      except (TypeError, AttributeError):
        # This means the node isn't a string, and thus not a URL.
        pass

      # If it's a status://url fetch the new node and act on it.
      if parsed_url and parsed_url.scheme == 'status':
        referenced_action = self.status.get(action)
        if referenced_action is None:
          raise InvalidAction('Status URL: %s failed to resolve.' % action)
        return self.handle_action(referenced_action)

      # If it's any other type of url, fetch it.
      if parsed_url:
        return monitor.util.action.get_page_wrapper(action)

      # If it's a dictionary, act based on the 'action' key's contents.
      action_type = None
      try:
        # 'action' is a required value in all dictionary actions.
        action_type = action['action']
      except TypeError:
        # This means it's not a dictionary, and not a dictionary type action.
        # Notice that we do NOT catch KeyError which would mean 'action' wasn't
        # present in the dictionary.
        pass

      if action_type:
        if action_type not in self.action_mapping:
          raise UnknownAction('action: %s is unknown.' % action_type)

        return self.action_mapping[action_type](action)

      # We now assume it's a list, and recurse on each element.
      for a in action:
        self.handle_action(a)
    except Exception as e:
      logging.error('handle_action raised: %s', e)
      raise

  def _handle_delayed_action(self, action):
    logging.debug('Action: Delayed %s',
                  action['seconds'])

    return task.deferLater(reactor,
                           action['seconds'],
                           self.handle_action,
                           action['delayed_action'])


  def _handle_fetch_action(self, action):
    url = action['url']

    if 'download_name' in action:
      file_name = monitor.util.action.find_download_name(
          self.status,
          action['download_name'])
      monitor.util.action.download_page_wrapper(url, file_name)
    else:
      monitor.util.action.get_page_wrapper(url)


  def _handle_set_action(self, action):
    if 'src' in action:
      logging.debug('Action: Set %s -> %s', action['src'], action['dest'])
      self.status.set(action['dest'], self.status.get(action['src']))
      return

    if 'value' in action:
      logging.debug('Action: Set %s -> %s', action['value'], action['dest'])
      self.status.set(action['dest'], action['value'])
      return

    raise InvalidAction(action)


  def _handle_increment_action(self, action):
    logging.debug('Action: Increment %s', action['dest'])
    self.status.set(action['dest'], self.status.get(action['dest'], 0) + 1)
    return


  def _handle_wol_action(self, action):
    logging.debug('Action: WOL %s', action['mac'])
    monitor.util.wake_on_lan.wake_on_lan(action['mac'])


  def _handle_ping_action(self, action):
    logging.debug('Action: Pinging %s -> %s',
                  action['hostname'], action['dest'])

    result = monitor.util.ping.ping(action['hostname'])
    self.status.set(action['dest'], result)


  # pylint: disable=R0914
  def _handle_email_action(self, action):
    default_to = self.status.get('status://server/email_address', None)
    to = action.get('to', default_to)
    subject = action.get('subject', '')
    body = action.get('body', '')
    attachments = action.get('attachments', None)

    description = ('Action: Email %s about %s with %s, %s' %
                   (to, subject, body, attachments))
    logging.debug(description)

    # If there are no attachments, handle that an exit.
    if not attachments:
      monitor.util.sendemail.email(self.status, to, subject, body, [])
      return

    # Setup the downloads.
    tempdir = tempfile.mkdtemp()
    filenames = []
    attachment_deferreds = []

    for attachement in attachments:
      url = attachement['url']

      # Find the name. Path is tempdir, or system downloads directory.
      filename = monitor.util.action.find_download_name(
          self.status,
          attachement['download_name'],
          tempdir if not attachement.get('preserve', False) else None)

      #Schedule the download.
      d = monitor.util.action.download_page_wrapper(url, filename)
      filenames.append(filename)
      attachment_deferreds.append(d)

    # Create handler to send email when downloads compelete.
    def _handle_email_attachments_collected(result):
      for success, _ in result:
        assert success

      monitor.util.sendemail.email(self.status, to, subject, body, filenames)
      return None

    def _cleanup(result):
      shutil.rmtree(tempdir)
      return result

    # Setup deferred for when all downloads complete, and attach handlers.
    collect = defer.DeferredList(attachment_deferreds)
    collect.addCallback(_handle_email_attachments_collected)
    collect.addBoth(_cleanup)
    monitor.util.action.attach_logging_callbacks(collect, description)
