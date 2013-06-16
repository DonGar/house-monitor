#!/usr/bin/python

import logging
import urlparse

import monitor.status
import monitor.util.action
import monitor.util.ping
import monitor.util.wake_on_lan


class Error(Exception):
  pass

class InvalidAction(Error):
  pass


def _handle_fetch_action(status, action):
  uri = action['uri'].encode('ascii')

  if 'download_name' in action:
    return monitor.util.action.download_page_wrapper(
        status, action['download_name'], uri)
  else:
    return monitor.util.action.get_page_wrapper(
        status, uri)


def _handle_set_action(status, action):
  if 'src' in action:
    logging.debug('Action: Set %s -> %s', action['src'], action['src'])
    status.set(action['dest'], status.get(action['src']))

  if 'value' in action:
    logging.debug('Action: Set %s -> %s', action['value'], action['src'])
    status.set(action['dest'], action['value'])

  raise InvalidAction(action)


def _handle_wol_action(_status, action):
  logging.debug('Action: WOL %s', action['mac'])
  monitor.util.wake_on_lan.wake_on_lan(action['mac'])


def _handle_ping_action(status, action):
  logging.debug('Action: Pinging %s -> %s',
                action['hostname'], action['store'])

  result = monitor.util.ping.ping(action['hostname'])
  status.set(action['store'], result)


def _handle_email_action(status, action):
  default_to = status.get('status://server/default_destination', None)
  to = action.get('to', default_to)
  subject = action.get('subject', '')
  body = action.get('body', '')
  attachements = action.get('attachemens', None)

  logging.debug('Action: Email %s about %s with %s, %s',
                to, subject, body, attachements)

  # monitor.util.mail(destination, subject, body)


def handle_action(status, action):
  """Perform the action specified by the json node 'action'.

  action can be a variety of things which are handled differently.

    A status URL: 'status://foo/bar'
    A standard URL: 'http://foo/bar'
    A dictionary: {''}
    http://url/path
    [<action>,...]
    { 'action': '', ...}
  """
  # If action is a URL.
  parsed_url = None
  try:
    parsed_url = urlparse.urlparse(action)
  except TypeError:
    # This means the node isn't a string, and thus not a URL.
    pass

  # If it's a status://url fetch the new node and act on it.
  if parsed_url and parsed_url.scheme == 'status':
    return handle_action(status, status.get(action))

  # If it's any other type of url, fetch it.
  if parsed_url:
    return monitor.util.action.get_page_wrapper(status, action.encode('ascii'))

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
    action_mapping = {
      'fetch_url': _handle_fetch_action,
      'set': _handle_set_action,
      'wol': _handle_wol_action,
      'ping': _handle_ping_action,
      'email': _handle_email_action,
    }
    return action_mapping[action_type](status, action)

  # We now assume it's a list, and recurse on each element.
  for a in action:
    handle_action(status, a)
