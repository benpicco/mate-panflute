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
Interface translator for MPD.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import gobject
import mpd
import os
import socket
import threading


class Connector (panflute.daemon.connector.PollingConnector):
    """
    Connection manager for MPD.
    """

    from panflute.util import log


    def __init__ (self):
        panflute.daemon.connector.PollingConnector.__init__ (self, "mpd", "MPD")

        self.__create_clients ()


    def root (self, **kwargs):
        return Root (self, self.__active, **kwargs)


    def track_list (self, **kwargs):
        # TODO: Implement for real
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (self, self.__active, self.__idle, **kwargs)


    def __create_clients (self):
        """
        Create the pair of MPD client objects.

        This might need to happen more than once, since they can't be reused
        after a connection is established and then closes.
        """

        self.__active = mpd.MPDClient ()
        self.__idle = mpd.MPDClient ()

        # python-mpd 0.14.x doesn't understand the "idle" command, even though
        # MPD 0.14 does.  Add its definition to the idle connection.
        if "idle" not in self.__idle._commands:
            self.__idle._commands["idle"] = self.__idle._getobject


    def try_connect (self):
        """
        Attempt to connect to the MPD daemon.
        """

        try:
            host = os.getenv ("MPD_HOST", "localhost")
            if "@" in host:
                host = (host.split ("@", 1))[1]
            port = os.getenv ("MPD_PORT", 6600)

            self.log.debug ("Attempting to connect to {0}:{1}".format (host, port))

            self.__active.connect (host, port)
            self.__idle.connect (host, port)
            # TODO: Authenticate to the daemon, if necessary

            self.log.debug ("Connection established")
            self.props.connected = True

        except socket.error:
            self.log.debug ("Connection failed")


    def _connection_lost (self, conn):
        """
        Discard the current connection, after being notified by one of the
        MPRIS objects that it lost the connection to the daemon.
        """

        if conn is self.__active or conn is self.__idle:
            self.log.debug ("Giving up on the current connection")

            self.__create_clients ()
            self.props.connected = False


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for MPD.
    """

    def __init__ (self, owner, active, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "MPD", **kwargs)
        self.__owner = owner
        self.__active = active


    def do_Quit (self):
        try:
            self.__active.kill ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for MPD.
    """

    # The lock is required in anything that can trigger D-Bus signals to be
    # sent or logs to be written, since those are resources shared between
    # the two threads.

    from panflute.util import log

    PING_INTERVAL = 30000


    def __init__ (self, owner, active, idle, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetStatus", "GetMetadata",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet", "PositionSet", "VolumeGet", "VolumeSet"]:
            self.register_feature (feature)
        self.__owner = owner
        self.__active = active
        self.__songid = None

        self.__idle_thread = IdleThread (owner, idle, self)
        self.__idle_thread.start ()

        self.__ping_source = gobject.timeout_add (self.PING_INTERVAL, self.__ping_cb)

        self.cached_caps.all = panflute.mpris.CAN_PLAY    | \
                               panflute.mpris.CAN_GO_NEXT | \
                               panflute.mpris.CAN_GO_PREV

        self._refresh_status ()


    def remove_from_connection (self):
        if self.__ping_source is not None:
            gobject.source_remove (self.__ping_source)
            self.__ping_source = None
        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        try:
            self.__active.next ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_Prev (self):
        try:
            self.__active.previous ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_Pause (self):
        try:
            if self.cached_status.state == panflute.mpris.STATE_PLAYING:
                self.__active.pause (1)
            elif self.cached_status.state == panflute.mpris.STATE_PAUSED:
                self.__active.pause (0)
            else:
                self.__active.play ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_Stop (self):
        try:
            self.__active.stop ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_Play (self):
        try:
            if self.cached_status.state != panflute.mpris.STATE_STOPPED:
                self.__active.seekid (self.__songid, 0)
            self.__active.play ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_PositionGet (self):
        try:
            status = self.__active.status ()
            if status.has_key ("elapsed"):
                # XXX: Verify that this is milliseconds
                return status["elapsed"]
            elif status.has_key ("time"):
                seconds = (status["time"].split (":"))[0]
                return int (seconds) * 1000
            else:
                return 0
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_PositionSet (self, position):
        try:
            if self.__songid is not None:
                self.__active.seekid (self.__songid, position // 1000)
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_VolumeGet (self):
        try:
            status = self.__active.status ()
            return int (status.get ("volume", "0"))
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def do_VolumeSet (self, volume):
        try:
            self.__active.setvol (volume)
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def _refresh_status (self):
        """
        Query MPD for its current state, and cache it.
        """

        states = { "play":  panflute.mpris.STATE_PLAYING,
                   "pause": panflute.mpris.STATE_PAUSED,
                   "stop":  panflute.mpris.STATE_STOPPED
                 }

        try:
            status = self.__active.status ()

            if status.has_key ("state"):
                state_name = status["state"]
                if state_name in states:
                    self.cached_status.state = states[state_name]
                    if self.cached_status.state == panflute.mpris.STATE_PLAYING:
                        self.start_polling_for_time ()
                    else:
                        self.stop_polling_for_time ()
                else:
                    self.log.warn ("Unrecognized state \"{0}\"".format (state_name))

            if status.has_key ("repeat"):
                if int (status["repeat"]):
                    self.cached_status.future = panflute.mpris.FUTURE_CONTINUE
                else:
                    self.cached_status.future = panflute.mpris.FUTURE_STOP

            if status.has_key ("songid"):
                self.__songid = status["songid"]
            else:
                self.__songid = None

            song = self.__active.currentsong ()
            metadata = {}

            if song.has_key ("file"):
                # MPD only reports paths relative to the library root, and doesn't
                # offer a command that says where the root actually is, so we're
                # stuck with a relative path.
                metadata["location"] = panflute.util.make_url (song["file"])

            if song.has_key ("title"):
                metadata["title"] = song["title"]
            elif song.has_key ("name"):
                metadata["title"] = song["name"]

            if song.has_key ("artist"):
                metadata["artist"] = song["artist"]
            elif song.has_key ("performer"):
                metadata["artist"] = song["performer"]
            elif song.has_key ("composer"):
                metadata["artist"] = song["composer"]

            if song.has_key ("album"):
                metadata["album"] = song["album"]

            if song.has_key ("track"):
                metadata["tracknumber"] = song["track"]

            if song.has_key ("time"):
                metadata["time"] = song["time"]
                metadata["mtime"] = int (song["time"]) * 1000

            if song.has_key ("genre"):
                metadata["genre"] = song["genre"]

            if song.has_key ("date"):
                metadata["year"] = song["date"]

            self.__utf8_decode (metadata)

            self.cached_metadata = metadata
            self.cached_caps.pause = (metadata.get ("mtime", 0) > 0)
            self.cached_caps.seek = (metadata.get ("mtime", 0) > 0)
            self.cached_caps.provide_metadata = (len (metadata) > 0)

        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)


    def __utf8_decode (self, metadata):
        """
        Decode all UTF-8-encoded strings in the metadata, so that later
        sanitization of them won't fail.  Without this, Python will
        wrongly treat the strings as ASCII.  See lp:596514
        """

        for key in metadata:
            if type (metadata[key]) == str:
                metadata[key] = unicode (metadata[key], "UTF-8")


    def __ping_cb (self):
        """
        MPD closes the connection if no commands are sent after a few
        minutes, so periodically ping it to keep the connection alive.
        """

        try:
            self.log.debug ("Keep-alive ping")
            self.__active.ping ()
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__active)
        finally:
            return True


class IdleThread (threading.Thread):
    """
    Thread used to repeatedly call MPD's "idle" command to wait for something
    to change, and alert the main thread if action is needed.

    Signalling to the main thread is done by adding a one-shot idle handler to
    the event loop; the handler will then be run in the main thread when
    nothing else is happening.
    """

    from panflute.util import log


    def __init__ (self, owner, idle, player):
        threading.Thread.__init__ (self, name = "MPD Idle")
        self.daemon = True
        self.__owner = owner
        self.__idle = idle
        self.__player = player


    def run (self):
        try:
            while True:
                self.log.debug ("Sleeping")
                self.__idle.idle ("player", "options")
                self.log.debug ("Woke up")
                gobject.idle_add (lambda: self.__player._refresh_status () and False)
        except mpd.ConnectionError, e:
            self.log.debug ("ConnectionError: {0}".format (e))
            self.__owner._connection_lost (self.__idle)
        except Exception, e:
            self.log.error ("Unknown exception: {0}".format (e))
        finally:
            self.log.debug ("Thread exiting")
