house-monitor
=============

Twisted web server used to inside my house. Mostly a learning exercise to help with home automation. 


The basic design is to have a JSON data structure that represents the state of the house. This data structure contains
'action' definitions of things that can be done, and rules definitions for when to take those actions.

The whole thing is a web server that gives a (not yet very) friendly interface for the whole thing, and which accepts
requests from external software.

I'm currently have a couple of Raspberry Pi devices that turn button pushes into web requests for this server. They
should soon be able to monitor the central state and take appropriate actions as needed.

Eventually, I plan to add a number of adapters to make external systems (Sonos, Mi Casa Verde, etc) act as part of this
same structure.

