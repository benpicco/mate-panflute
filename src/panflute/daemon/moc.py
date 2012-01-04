#! /usr/bin/env python

# Panflute
# Copyright (C) 2010 Paul Kuliniewicz <paul@kuliniewicz.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02111-1301, USA.

"""
Interface translator for MOC.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import mateconf
import glib
import os
import pyinotify
import Queue
import re
import subprocess
import threading


class Connector (panflute.daemon.connector.Connector):
    """
    Connection manager for MOC.
    """

    from panflute.util import log


    def __init__ (self):
        panflute.daemon.connector.Connector.__init__ (self, "moc", "MOC")

        wm = pyinotify.WatchManager ()
        mask = pyinotify.IN_CREATE | pyinotify.IN_DELETE
        listener = NotifyListener (self)

        self.__notifier = pyinotify.ThreadedNotifier (wm, listener)
        self.__notifier.daemon = True
        self.__notifier.start ()

        wm.add_watch (os.path.expanduser ("~/.moc"), mask)
        self.props.connected = os.path.exists (os.path.expanduser ("~/.moc/socket2"))


    def root (self, **kwargs):
        return Root (**kwargs)


    def track_list (self, **kwargs):
        # TODO: Implement for real
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


    def launch (self):
        run_ignoring_output ("-S")
        return True


class NotifyListener (pyinotify.ProcessEvent):
    """
    Listen for creation or deletion of the MOC socket to detect when MOC is
    running.
    """

    def __init__ (self, connector):
        pyinotify.ProcessEvent.__init__ (self)
        self.__connector = connector


    def process_IN_CREATE (self, event):
        if event.name == "socket2":
            glib.idle_add (lambda: self.__notify (True))


    def process_IN_DELETE (self, event):
        if event.name == "socket2":
            glib.idle_add (lambda: self.__notify (False))


    def __notify (self, connected):
        """
        Set the connection manager's state in the main thread.
        """

        self.__connector.props.connected = connected
        return False


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for MOC.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "MOC", **kwargs)


    def do_Quit (self):
        run_ignoring_output ("-x")


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for MOC.
    """

    from panflute.util import log

    POLL_INTERVAL = 1000


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Play", "Stop", "Pause", "Prev", "Next",
                        "PositionGet", "PositionSet"]:
            self.register_feature (feature)
        self.__elapsed = 0

        self.__command_thread = CommandThread (self)
        self.__command_thread.start ()

        self.__poll_source = glib.timeout_add (self.POLL_INTERVAL, self.__poll_cb)
        self.__poll_cb ()

        self.cached_caps.go_next = True
        self.cached_caps.go_prev = True
        self.cached_caps.play = True


    def remove_from_connection (self):
        self.__command_thread.enqueue ("")
        if self.__poll_source is not None:
            glib.source_remove (self.__poll_source)
            self.__poll_source = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Play (self):
        run_ignoring_output ("-p")


    def do_Stop (self):
        run_ignoring_output ("-s")


    def do_Pause (self):
        run_ignoring_output ("-G")


    def do_Prev (self):
        run_ignoring_output ("-r")


    def do_Next (self):
        run_ignoring_output ("-f")


    def do_PositionGet (self):
        # Rely on the polling to update the value.
        return self.__elapsed


    def do_PositionSet (self, position):
        delta = (position - self.__elapsed) // 1000
        run_ignoring_output ("-k {0}".format (delta))


    def __poll_cb (self):
        """
        Poll for MOC's current status.
        """

        self.__command_thread.enqueue ("-i")
        return True


    def parse_info (self, info_text):
        """
        Parse and process the status info returned from MOC.
        """

        states = { "STOP": panflute.mpris.STATE_STOPPED,
                   "PAUSE": panflute.mpris.STATE_PAUSED,
                   "PLAY": panflute.mpris.STATE_PLAYING
                 }
        metadata = {}

        for line in info_text.split ("\n"):
            if line != "":
                key, value = line.split (": ", 1)
                if key == "State":
                    if states.has_key (value):
                        self.cached_status.state = states[value]
                        self.cached_caps.pause = (value != "STOP")
                        self.cached_caps.seek = (value != "STOP")
                    else:
                        self.log.warn ("Unrecognized state {0}".format (value))
                elif key == "File":
                    metadata["location"] = panflute.util.make_url (value)
                elif key == "SongTitle":
                    metadata["title"] = value
                elif key == "Artist":
                    metadata["artist"] = value
                elif key == "Album":
                    metadata["album"] = value
                elif key == "TotalSec":
                    metadata["time"] = int (value)
                    metadata["mtime"] = int (value) * 1000
                elif key == "CurrentSec":
                    elapsed = int (value) * 1000
                    if elapsed != self.__elapsed:
                        self.__elapsed = elapsed
                        self.do_PositionChange (elapsed)
                elif key == "AvgBitrate":
                    match = re.match ("^(\d+)([KM]?)bps$", value)
                    if match:
                        if match.group (2) == "K":
                            modifier = 1000
                        elif match.group (2) == "M":
                            modifier = 1000000
                        else:
                            modifier = 1
                        metadata["audio-bitrate"] = int (match.group (1)) * modifier
                    else:
                        self.log.warn ("Unrecognized bitrate {0}".format (value))
                elif key == "Rate":
                    match = re.match ("^(\d+)([KM]?)Hz$", value)
                    if match:
                        if match.group (2) == "K":
                            modifier = 1000
                        elif match.group (2) == "M":
                            modifier = 1000000
                        else:
                            modifier = 1
                        metadata["audio-samplerate"] = int (match.group (1)) * modifier
                    else:
                        self.log.warn ("Unrecognized samplerate {0}".format (value))

        self.cached_metadata = metadata
        self.cached_caps.provide_metadata = (len (metadata) > 0)
        return False


class CommandThread (threading.Thread):
    """
    Thread used to run MOC commands and read back its output.  The output is
    then handed off to a callback function in the main thread.

    Doing the actual read in this thread prevents blocking the GUI during a
    read.
    """

    from panflute.util import log


    def __init__ (self, owner):
        threading.Thread.__init__ (self, name = "MOC Command")
        self.daemon = True
        self.__queue = Queue.Queue (-1)
        self.__owner = owner


    def enqueue (self, arg_string):
        """
        Called by the main thread to add a task to the queue.
        """

        self.__queue.put (arg_string)


    def run (self):
        while True:
            try:
                arg_string = self.__queue.get ()
                if arg_string == "":
                    break
                command = moc_command (arg_string)
                with open ("/dev/null", "r+") as null:
                    proc = subprocess.Popen (command, shell = True, close_fds = True, preexec_fn = os.setsid,
                                             stdin = null, stdout = subprocess.PIPE, stderr = null)
                    out, err = proc.communicate ()
                    glib.idle_add (lambda: self.__owner.parse_info (out))
            except Exception, e:
                self.log.error ("Command failed: {0}".format (e))


def moc_command (arg_string):
    """
    Return a command line for invoking MOC.
    """

    client = mateconf.client_get_default ()
    base_command = client.get_string ("/apps/panflute/daemon/moc/command")
    return "{0} {1}".format (base_command, arg_string)


def run_ignoring_output (arg_string):
    """
    Run a MOC command and ignore any output it generates.
    """

    command = moc_command (arg_string)
    with open ("/dev/null", "r+") as null:
        subprocess.Popen (command, shell = True, close_fds = True, preexec_fn = os.setsid,
                          stdin = null, stdout = null, stderr = null)
