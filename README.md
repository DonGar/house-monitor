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

 * Sonos

This is an adapter to discover remaining Sonos devices in the house, and display the state of all of them.

The argument "root_player" is required which is a hostname or IP address for one of the Sonos devices in the house. Full autodiscovery is not supported.
