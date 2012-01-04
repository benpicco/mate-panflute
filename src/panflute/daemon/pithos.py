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
Interface translator for Pithos.
"""

from __future__ import absolute_import

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris

import dbus


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Pithos.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "pithos", "Pithos",
                                                          "net.kevinmehall.Pithos")
        # Pithos's icon isn't put into a common directory


    def root (self, **kwargs):
        return panflute.daemon.mpris.Root ("Pithos", **kwargs)


    def track_list (self, **kwargs):
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.mpris.Player):
    """
    Player object for Pithos.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Next", "Pause", "Stop", "Play"]:
            self.register_feature (feature)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("net.kevinmehall.Pithos", "/net/kevinmehall/Pithos")
        self.__pithos = dbus.Interface (proxy, "net.kevinmehall.Pithos")

        self.cached_caps.all = panflute.mpris.CAN_GO_NEXT |         \
                               panflute.mpris.CAN_PAUSE |           \
                               panflute.mpris.CAN_PLAY |            \
                               panflute.mpris.CAN_PROVIDE_METADATA

        self.__handlers = [
            self.__pithos.connect_to_signal ("PlayStateChanged", self.__play_state_changed_cb),
            self.__pithos.connect_to_signal ("SongChanged", self.__song_changed_cb)
        ]

        self.__pithos.IsPlaying (reply_handler = self.__play_state_changed_cb,
                                 error_handler = self.log.warn)
        self.__pithos.GetCurrentSong (reply_handler = self.__song_changed_cb,
                                      error_handler = self.log.warn)


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = []

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        self.__pithos.SkipSong (reply_handler = lambda: None,
                                error_handler = self.log.warn)


    def do_Pause (self):
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.__pithos.PlayPause (reply_handler = lambda: None,
                                     error_handler = self.log.warn)


    def do_Stop (self):
        self.do_Pause ()


    def do_Play (self):
        if self.cached_status.state != panflute.mpris.STATE_PLAYING:
            self.__pithos.PlayPause (reply_handler = lambda: None,
                                     error_handler = self.log.warn)


    def __play_state_changed_cb (self, playing):
        """
        Called when the playback state changes.
        """

        if playing:
            self.cached_status.state = panflute.mpris.STATE_PLAYING
        else:
            self.cached_status.state = panflute.mpris.STATE_PAUSED


    def __song_changed_cb (self, song):
        """
        Called when the current song changes.
        """

        self.log.debug ("New song: {0}".format (song))
        if song is not None and len (song) > 0:
            metadata = {}
            if "title" in song:
                metadata["title"] = song["title"]
            if "artist" in song:
                metadata["artist"] = song["artist"]
            if "album" in song:
                metadata["album"] = song["album"]
            if "songDetailURL" in song:
                metadata["location"] = song["songDetailURL"]
            self.cached_metadata = metadata
        else:
            self.cached_metadata = {}
