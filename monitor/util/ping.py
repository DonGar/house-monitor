#!/usr/bin/python

import logging
import subprocess

def ping(hostname, attempts=3):

  logging.debug('Pinging %s', hostname)

  with open('/dev/null', 'w') as FNULL:
    result = subprocess.call(['ping', '-q', '-c', str(attempts), hostname],
                             stdout=FNULL,
                             stderr=FNULL)

  # External process returns 0 on success
  return result == 0

if __name__ == "__main__":
  # Convert true for success to 0 exit code
  exit(not ping('localhost'))
