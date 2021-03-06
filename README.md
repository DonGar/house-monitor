#house-monitor

Twisted web server used to inside my house. Mostly a learning exercise to help with home automation.


The basic design is to have a JSON data structure that represents the state of the house. This data structure contains
'action' definitions of things that can be done, and rules definitions for when to take those actions.

The whole thing is a web server that gives a (not yet very) friendly interface for the whole thing, and which accepts
requests from external software.

I'm currently have a couple of Raspberry Pi devices that turn button pushes into web requests for this server. They
should soon be able to monitor the central state and take appropriate actions as needed.

Eventually, I plan to add a number of adapters to make external systems (Sonos, Mi Casa Verde, etc) act as part of this
same structure.

##Installation

In short:

    run_server -setup

In long:

    TODO: Write this.

##Configuration

The main configuration file is "server.json", which must be a valid JSON file.

An example:

    {
      "port": 8081,

      "downloads": "/archive/directory",

      "timezone": "US/Pacific",
      "latitude": "12.123",
      "longitude": "-12.123",

      "email_address": "example@sample.com",

      "adapters": {
        "config": {
          "type": "file",
          "filename": "config.json"
        },
        "control": {
          "type": "web"
        },
        "doorbell": {
          "type": "web"
        },
        "strip": {
          "type": "web"
        }
      }
    }

 * port: is the port number of the web server.
 * downloads: is a directory for archiving downloaded files (like images).
 * timezone: Is the timezone used for time values in the config files.
 * latitude/longitude: These are used to determine sunrise/sunset times.
 * email_address: Is the 'from' address used when sending out email.
 * adapters: contains a dictionary listing and configuring the adapters in use.

###Adapters

  Each adapter entry looks like:

    "<name>": {
      "type": "<type>",
      <type specific values, if any>
    }

  Each adapter will appear in the system status in the location:
  status://<name>/


 * File Adapter

The file adapter reads a json file and loads it's contents. The default file name is "<name>.json", or a "filename" value will be used instead. If the source file is updated while the server is running, the status contents will be replaced (and any dynamic values added to the status will be lost).

If the file doesn't contain valid Json an error value will be loaded.

This type of adapter is most commonly used to load rules, or status components.

 * Web Adapter

The web adapter can have it's contents read or written through REST web requests. I currently use it to interact with remote Raspberry Pi's running software from the "pi-house" project.

Web adapter values can be read with:

    GET http://<server>:<port>/status/<name>
    GET http://<server>:<port>/status/<name>?revision=X

Reads at the current revision will block until there is a change. Reads at any other revision will return right away.

The results will include the current revision.

Web adapter values can be written with:

    PUT http://<server>:<port>/status/<name>
    PUT http://<server>:<port>/status/<name>?revision=X

Writes with a specificed revision will fail if the revision isn't current.

 * IOGear

This adapter uses a virutal serial port to communicate with an arduino wired into an IOGear KVM. The arduino code is in the main project.

The argument "port" specifies the USB port of the IO Gear arduino hardware.

 * SNMP

The argument "hosts" should contain a list of host names ["host1", "host2", etc] which can be queried and walked with SNMP. SNMP values will be read and imported into the status every 15 seconds.

This adapter is pretty ineffcient (it always snmpwalks all values from scratch), and not very configurable.

 * Sonos

This is an adapter to discover remaining Sonos devices in the house, and display the state of all of them.

The argument "root_player" is required which is a hostname or IP address for one of the Sonos devices in the house. Full autodiscovery is not supported.

This adapter is still strictly readonly, and not really ready for real use.

###Components

Components are inside adapter areas, and generally correspond to a real or virtual device. The path for this is:

status://<adapter_name>/<component_type>/<component_name>/

Components are created and maintained by adapters. They contain writable values, and the adapters will respond to changes to writable values.

Components generally contain a number of component type specific values that are readable, and "<value>_target" values that are writable. Adapters will attempt to reach the specified target, and clear it when they are done. However, if the target is updated more than once adpaters may or may not attempt to reach any intermediate states.

 * button
    * pushed - Updated to time of last button push.

 * host - The host name is the DNS name of the host.
    * up - Optional boolean describing last ping status.
    * actions - Optional list of actions associated with the host.

 * camera - A different type of host. No further support.

 * rule - Rules for the Rules Manager (see below).

 * rgb
   * color - RGB color in "0,0,0", "1,1,1" format (no dimming).
   * color_target - Writable value to update color too.

 * bell
   * ring_target - Set any value to ring the bell.

 * iogear
   * active - which KVM port is active.
   * target - which KVM port to switch too.

 * snmp
   * Will contain all discovered SNMP values. Read only.

 * sonos
   * Will contain discovered content. Read only.

###Rules

The "behavior" of a rule says which type of rule it is.

 * Interval - These rules fire at fixed intervals.


        "<name>": {
            "behavior": "internal",
            "time": "<hh:mm:ss>",
            "action": <action>
        },

    * time - How often to fire this rule in hh:mm:ss time. 5:00 = 5 minutes, 1:30:00 = 1.5 hours.
    * action - Action to take when rule fires.


 * Daily - These rules fire once a day.

        "<name>": {
            "behavior": "daily",
            "time": "<hh:mm:ss|sunset|sunrise>",
            "action": <action>
        },

    * time - When to fire this rule. Either an absolute 24 hour time (15:33:22), or "sunset" or "sunrise" which are calculated based on the server latitude/longitude.
    * action - Action to take when rule fires.

 * Watch - These rules fire when a watched value is updated.

        "<name>": {
            "behavior": "watch",
            "value": "<status_uri>",
            "trigger": <value>,
            "action": <action>
        },

    * value - Value to watch. Fire if value changes.
    * trigger - optional. If present, only fire if value matches trigger.
    * action - Action to take when rule fires.

###Actions

There are many types of actions:
 * "status://_status_uri_" - fetch the action referred to and run it.
 * "http(s)://_http_uri_" - fetch the url and throw away the results. Intended to trigger a remote action.
 * [_action_, _action_, ...] - Run each sub-action in turn.
 * { "action": "_type_", .... }

   * delayed - Run the inner action after a time delay.
     * seconds - How long to delay.
     * delayed_action - What action to perform.
   * fetch_url - Fetch the specified URL.
     * url - Url to fetch.
     * download_name - Optional field. Name of file inside system downloads directy in which to store the downloaded value. '{time}' in the name will be filled in with a unique time based number.
   * set - Set a status URI with a value.
     * dest - Status Uri to write value into.
     * src - Optional, src URI to read value from.
     * value - Optional, value to write into dest.
   * increment - Increment a status URI by 1.
     * dest - Status URI to increment by 1. Creates as '1' if non-existent.
   * wol - Issue a Wake On Lan request.
     * mac - Mac address to attempt to wake.
   * ping - Ping a host, and store result.
     * host - Status URI of the host component to ping. Result stored in <host>/up as a boolean. The result is NOT immediately available. Host can contain wildcards in it's path.
   * email - Send email.
     * to - Address to send email too.
     * subject - Optional subject string.
     * body - Optional body string.
     * attachments - List of attachments.
       * url - URL to fetch and attach to email.
       * download_name - Name to download and attach as. Follows same rules as fetch_url:download_name.
       * preserve - optional flag to keep in downloads directory.
