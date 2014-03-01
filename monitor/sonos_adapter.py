#!/usr/bin/python

import datetime
import logging
import os
import re
import xml.etree.cElementTree as XML

import requests

from twisted.internet import threads

import monitor.adapter
from monitor.util import repeat

# A lot of variables get defined inside setup, called from init.
# pylint: disable=W0201

class SonosAdapter(monitor.adapter.Adapter):

  def setup(self):
    # Read our file, and attach it to the status.
    self.root = self.adapter_json.get('root_player')
    self.root_soco = SoCo(self.root)

    logging.info('Sonos with root_player %s', self.root)

    # Start refreshing Sonos information every 10 seconds.
    timing_helper = repeat.interval_helper(datetime.timedelta(seconds=10))
    repeat.call_repeating(timing_helper, self.refresh_players)

  def refresh_players(self):

    for ip in self.root_soco.get_speakers_ip():

      def handle_result(info):
        url = os.path.join(self.url, 'sonos_player', info['zone_name'])
        self.status.set(url, info)

      d = threads.deferToThread(self.refresh_player, ip)
      d.addCallback(handle_result)

  def refresh_player(self, ip):
    s = SoCo(ip)
    info = s.get_speaker_info()
    info['track'] = s.get_current_track_info()
    return info


class SoCo(object):
  """A simple class for controlling a Sonos speaker.

  Public functions:
  play -- Plays the currently selected track or a music stream.
  pause -- Pause the currently playing track.
  stop -- Stop the currently playing track.
  next -- Go to the next track.
  previous -- Go back to the previous track.
  mute -- Mute (or unmute) the speaker.
  volume -- Get or set the volume of the speaker.
  bass -- Get or set the speaker's bass EQ.
  treble -- Set the speaker's treble EQ.
  set_loudness -- Turn on (or off) the speaker's loudness compensation.
  switch_to_line_in -- Switch the speaker's input to line-in.
  status_light -- Turn on (or off) the Sonos status light.
  get_current_track_info -- Get information about the currently playing track.
  get_speaker_info -- Get information about the Sonos speaker.
  partymode -- Put all the speakers in the network in the same group,
               a.k.a Party Mode.
  join -- Join this speaker to another "master" speaker.

  """

  TRANSPORT_ENDPOINT = '/MediaRenderer/AVTransport/Control'
  RENDERING_ENDPOINT = '/MediaRenderer/RenderingControl/Control'
  DEVICE_ENDPOINT = '/DeviceProperties/Control'

  def __init__(self, speaker_ip):
    self.speaker_info = {} # Stores information about the current speaker
    self.speakers_ip = [] # Stores the IP addresses of all the speakers
    self.speaker_ip = speaker_ip

  def play(self, uri=''):
    """Play the currently selected track or play a stream.

    Arguments:
    uri -- URI of a stream to be played.

    Returns:
    True if the Sonos speaker successfully started playing the track.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned.

    """
    if uri != '':
      action = '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"'

      body = ('<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:'
              'AVTransport:1"><InstanceID>0</InstanceID><CurrentURI>' + uri +
              '</CurrentURI><CurrentURIMetaData></CurrentURIMetaData>'
              '</u:SetAVTransportURI>')

      response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

      if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                       'envelope/" s:encodingStyle="http://schemas.xmlsoap.'
                       'org/soap/encoding/"><s:Body><u:SetAVTransportURI'
                       'Response xmlns:u="urn:schemas-upnp-org:service:'
                       'AVTransport:1"></u:SetAVTransportURIResponse>'
                       '</s:Body></s:Envelope>')):
        # The track is enqueued, now play it.
        return self.play()
      else:
        return self.__parse_error(response)

    else:
      action = '"urn:schemas-upnp-org:service:AVTransport:1#Play"'

      body = ('<u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
              '<InstanceID>0</InstanceID><Speed>1</Speed></u:Play>')

      response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

      if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                       'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                       'soap/encoding/"><s:Body><u:PlayResponse xmlns:u="urn:'
                       'schemas-upnp-org:service:AVTransport:1"></u:'
                       'PlayResponse></s:Body></s:Envelope>')):
        return True
      else:
        return self.__parse_error(response)

  def pause(self):
    """ Pause the currently playing track.

    Returns:
    True if the Sonos speaker successfully paused the track.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned.

    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#Pause"'

    body = ('<u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><Speed>1</Speed></u:Pause>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:PauseResponse xmlns:u="urn:'
                     'schemas-upnp-org:service:AVTransport:1"></u:'
                     'PauseResponse></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def stop(self):
    """ Stop the currently playing track.

    Returns:
    True if the Sonos speaker successfully stopped the playing track.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned.

    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#Stop"'

    body = ('<u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><Speed>1</Speed></u:Stop>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:StopResponse xmlns:u="urn:'
                     'schemas-upnp-org:service:AVTransport:1"></u:StopResponse'
                     '></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def next(self):
    """ Go to the next track.

    Returns:
    True if the Sonos speaker successfully skipped to the next track.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned. Keep in mind that next() can return errors
    for a variety of reasons. For example, if the Sonos is streaming
    Pandora and you call next() several times in quick succession an error
    code will likely be returned (since Pandora has limits on how many
    songs can be skipped).

    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#Next"'

    body = ('<u:Next xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><Speed>1</Speed></u:Next>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:NextResponse xmlns:u="urn:'
                     'schemas-upnp-org:service:AVTransport:1"></u:NextResponse'
                     '></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def previous(self):
    """ Go back to the previously played track.

    Returns:
    True if the Sonos speaker successfully went to the previous track.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned. Keep in mind that previous() can return errors
    for a variety of reasons. For example, previous() will return an error
    code (error code 701) if the Sonos is streaming Pandora since you can't
    go back on tracks.

    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#Previous"'

    body = ('<u:Previous xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><Speed>1</Speed></u:Previous>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:PreviousResponse xmlns:u='
                     '"urn:schemas-upnp-org:service:AVTransport:1">'
                     '</u:PreviousResponse></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def mute(self, mute):
    """ Mute or unmute the Sonos speaker.

    Arguments:
    mute -- True to mute. False to unmute.

    Returns:
    True if the Sonos speaker was successfully muted or unmuted.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned.

    """
    if mute:
      mute_value = '1'
    else:
      mute_value = '0'

    action = '"urn:schemas-upnp-org:service:RenderingControl:1#SetMute"'

    body = ('<u:SetMute xmlns:u="urn:schemas-upnp-org:service:'
            'RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master'
            '</Channel><DesiredMute>' + mute_value + '</DesiredMute>'
            '</u:SetMute>')

    response = self.__send_command(SoCo.RENDERING_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:SetMuteResponse xmlns:u='
                     '"urn:schemas-upnp-org:service:RenderingControl:1">'
                     '</u:SetMuteResponse></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def volume(self, volume=False):
    """ Get or set the Sonos speaker volume.

    Arguments:
    volume -- A value between 0 and 100.

    Returns:
    If the volume argument was specified: returns true if the Sonos speaker
    successfully set the volume.

    If the volume argument was not specified: returns the current volume of
    the Sonos speaker.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned.

    """
    if volume:
      action = '"urn:schemas-upnp-org:service:RenderingControl:1#SetVolume"'

      body = ('<u:SetVolume xmlns:u="urn:schemas-upnp-org:service:'
              'RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master'
              '</Channel><DesiredVolume>' + repr(volume) +
              '</DesiredVolume></u:SetVolume>')

      response = self.__send_command(SoCo.RENDERING_ENDPOINT, action, body)

      if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                       'envelope/" s:encodingStyle="http://schemas.xmlsoap.org'
                       '/soap/encoding/"><s:Body><u:SetVolumeResponse '
                       'xmlns:u="urn:schemas-upnp-org:service:RenderingControl'
                       ':1"></u:SetVolumeResponse></s:Body></s:Envelope>')):
        return True
      else:
        return self.__parse_error(response)
    else:
      action = '"urn:schemas-upnp-org:service:RenderingControl:1#GetVolume"'

      body = ('<u:GetVolume xmlns:u="urn:schemas-upnp-org:service:'
              'RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master'
              '</Channel></u:GetVolume>')

      response = self.__send_command(SoCo.RENDERING_ENDPOINT, action, body)

      dom = XML.fromstring(response)

      volume = dom.findtext('.//CurrentVolume')

      return int(volume)

  def partymode(self):
    """ Put all the speakers in the network in the same group, a.k.a Party Mode.

    This blog shows the initial research responsible for this:
        http://travelmarx.blogspot.dk/2010/06/exploring-sonos-via-upnp.html

    The trick seems to be (only tested on a two-speaker setup) to tell each
        speaker which to join. There's probably a bit more to it if multiple
        groups have been defined.

        Code contributed by Thomas Bartvig (thomas.bartvig@gmail.com)

    Returns:
    True if partymode is set

        If an error occurs, we'll attempt to parse the error and return a UPnP
        error code. If that fails, the raw response sent back from the Sonos
        speaker will be returned.
    """

    master_speaker_info = self.get_speaker_info()
    ips = self.get_speakers_ip()

    rc = True
    # loop through all IP's in topology and make them join this master
    for ip in ips:
      if ip != self.speaker_ip:
        Slave = SoCo(ip)
        ret = Slave.join(master_speaker_info["uid"])
        if not ret:
          rc = False

    return rc

  def join(self, master_uid):
    """ Join this speaker to another "master" speaker.

    Code contributed by Thomas Bartvig (thomas.bartvig@gmail.com)

    Returns:
    True if this speaker has joined the master speaker

        If an error occurs, we'll attempt to parse the error and return a UPnP
        error code. If that fails, the raw response sent back from the Sonos
        speaker will be returned.
    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"'

    body = ('<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:'
            'AVTransport:1"><InstanceID>0</InstanceID><CurrentURI>x-rincon:' +
            master_uid + '</CurrentURI><CurrentURIMetaData>'
            '</CurrentURIMetaData></u:SetAVTransportURI>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:SetAVTransportURIResponse '
                     'xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
                     '</u:SetAVTransportURIResponse></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def switch_to_line_in(self):
    """ Switch the speaker's input to line-in.

    Returns:
    True if the Sonos speaker successfully switched to line-in.

    If an error occurs, we'll attempt to parse the error and return a UPnP
    error code. If that fails, the raw response sent back from the Sonos
    speaker will be returned. Note, an error will be returned if you try
    to switch to line-in on a device (like the Play:3) that doesn't have
    line-in capability.

    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"'

    self.speaker_info = self.get_speaker_info()

    body = ('<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:'
            'AVTransport:1"><InstanceID>0</InstanceID><CurrentURI>x-rincon-'
            'stream:' + self.speaker_info['uid'] + '</CurrentURI><'
            'CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    if (response == ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/'
                     'envelope/" s:encodingStyle="http://schemas.xmlsoap.org/'
                     'soap/encoding/"><s:Body><u:SetAVTransportURIResponse'
                     ' xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
                     '</u:SetAVTransportURIResponse></s:Body></s:Envelope>')):
      return True
    else:
      return self.__parse_error(response)

  def get_current_track_info(self):
    """ Get information about the currently playing track.

    Returns:
    A dictionary containing the following information about the currently
    playing track: playlist_position, duration, title, artist, album, and
    a link to the album art.

    If we're unable to return data for a field, we'll return an empty
    string. This can happen for all kinds of reasons so be sure to check
    values. For example, a track may not have complete metadata and be
    missing an album name. In this case track['album'] will be an empty string.

    """
    action = '"urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo"'

    body = ('<u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:'
            'AVTransport:1"><InstanceID>0</InstanceID><Channel>Master'
            '</Channel></u:GetPositionInfo>')

    response = self.__send_command(SoCo.TRANSPORT_ENDPOINT, action, body)

    dom = XML.fromstring(response)

    track = {}

    track['playlist_position'] = dom.findtext('.//Track')
    track['duration'] = dom.findtext('.//TrackDuration')
    track['uri'] = dom.findtext('.//TrackURI')

    d = dom.findtext('.//TrackMetaData')

    # If the speaker is playing from the line-in source, querying for track
    # metadata will return "NOT_IMPLEMENTED".
    if d != '' and d != 'NOT_IMPLEMENTED':
      # Track metadata is returned in DIDL-Lite format
      metadata = XML.fromstring(d.encode('utf-8'))

      track['title'] = metadata.findtext(
          './/{http://purl.org/dc/elements/1.1/}title')
      track['artist'] = metadata.findtext(
          './/{http://purl.org/dc/elements/1.1/}creator')
      track['album'] = metadata.findtext(
          './/{urn:schemas-upnp-org:metadata-1-0/upnp/}album')

      album_art = metadata.findtext(
          './/{urn:schemas-upnp-org:metadata-1-0/upnp/}albumArtURI')

      if album_art:
        track['album_art'] = ('http://' + self.speaker_ip + ':1400' +
                              metadata.findtext('.//{urn:schemas-upnp-org:'
                                                'metadata-1-0/upnp/}'
                                                'albumArtURI'))
      else:
        track['album_art'] = ''
    else:
      track['title'] = ''
      track['artist'] = ''
      track['album'] = ''
      track['album_art'] = ''

    return track

  def get_speaker_info(self, refresh=False):
    """ Get information about the Sonos speaker.

    Arguments:
    refresh -- Refresh the speaker info cache.

    Returns:
    Information about the Sonos speaker, such as the UID, MAC Address, and
    Zone Name.

    """
    if self.speaker_info and not refresh:
      return self.speaker_info
    else:
      response = requests.get('http://' + self.speaker_ip + ':1400/status/zp')

      dom = XML.fromstring(response.content)

      self.speaker_info['zone_name'] = dom.findtext('.//ZoneName')
      self.speaker_info['zone_icon'] = dom.findtext('.//ZoneIcon')
      self.speaker_info['uid'] = dom.findtext('.//LocalUID')
      self.speaker_info['serial_number'] = dom.findtext('.//SerialNumber')
      self.speaker_info['software_version'] = dom.findtext('.//SoftwareVersion')
      self.speaker_info['hardware_version'] = dom.findtext('.//HardwareVersion')
      self.speaker_info['mac_address'] = dom.findtext('.//MACAddress')

      return self.speaker_info

  def get_speakers_ip(self, refresh=False):
    """ Get the IP addresses of all the Sonos speakers in the network.

    Code contributed by Thomas Bartvig (thomas.bartvig@gmail.com)

    Arguments:
    refresh -- Refresh the speakers IP cache.

    Returns:
    IP addresses of the Sonos speakers.

    """

    if self.speakers_ip and not refresh:
      return self.speakers_ip
    else:
      response = requests.get('http://' + self.speaker_ip +
                              ':1400/status/topology')
      text = response.text
      grp = re.findall(r'(\d+\.\d+\.\d+\.\d+):1400', text)

      for i in grp:
        response = requests.get('http://' + i + ':1400/status')

        if response.status_code == 200:
          (self.speakers_ip).append(i)

      return self.speakers_ip

  def __send_command(self, endpoint, action, body):
    """ Send a raw command to the Sonos speaker.

    Returns:
    The raw response body returned by the Sonos speaker.

    """
    headers = {
      'Content-Type': 'text/xml',
      'SOAPACTION': action
    }

    soap = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            '<s:Body>' + body + '</s:Body></s:Envelope>')

    r = requests.post('http://' + self.speaker_ip + ':1400' + endpoint,
                      data=soap, headers=headers)

    return r.content

  def __parse_error(self, response):
    """ Parse an error returned from the Sonos speaker.

    Returns:
    The UPnP error code returned by the Sonos speaker.

    If we're unable to parse the error response for whatever reason, the
    raw response sent back from the Sonos speaker will be returned.
    """
    error = XML.fromstring(response)

    errorCode = error.findtext('.//{urn:schemas-upnp-org:control-1-0}errorCode')

    if errorCode != None:
      return int(errorCode)
    else:
      # Unknown error, so just return the entire response
      return response
