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
Interface translator for Quod Libet.
"""

from __future__ import absolute_import

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import ConfigParser
import dbus
import os


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Quod Libet.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "quod_libet", "Quod Libet",
                                                          "net.sacredchao.QuodLibet")
        self.props.icon_name = "quodlibet"


    def root (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.Root ("Quod Libet", **kwargs)


    def track_list (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for Quod Libet.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet"]:
            self.register_feature (feature)

        # Quod Libet's config file specifies the rating scale being used
        try:
            config = ConfigParser.ConfigParser ()
            config.read (os.path.expanduser ("~/.quodlibet/config"))
            self.__rating_scale = int (config.get ("settings", "ratings"))
        except ConfigParser.NoOptionError:
            self.__rating_scale = 4    # the default

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("net.sacredchao.QuodLibet", "/net/sacredchao/QuodLibet")
        self.__ql = dbus.Interface (proxy, "net.sacredchao.QuodLibet")

        self.__handlers = [
            self.__ql.connect_to_signal ("Paused", self.__paused_cb),
            self.__ql.connect_to_signal ("Unpaused", self.__unpaused_cb),
            self.__ql.connect_to_signal ("SongStarted", self.__song_started_cb),
            self.__ql.connect_to_signal ("SongEnded", self.__song_ended_cb)
        ]

        self.cached_caps.all = panflute.mpris.CAN_GO_NEXT | \
                               panflute.mpris.CAN_GO_PREV | \
                               panflute.mpris.CAN_PLAY

        self.__ql.IsPlaying (reply_handler = self.__is_playing_cb,
                             error_handler = self.log.warn)
        self.__ql.CurrentSong (reply_handler = self.__song_started_cb,
                               error_handler = self.log.warn)


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        self.__ql.Next (reply_handler = lambda: None,
                        error_handler = self.log.warn)


    def do_Prev (self):
        self.__ql.Previous (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_Pause (self):
        self.__ql.PlayPause (reply_handler = lambda was_playing: None,
                             error_handler = self.log.warn)


    def do_Stop (self):
        self.__ql.Pause (reply_handler = lambda: None,
                         error_handler = self.log.warn)


    def do_Play (self):
        self.__ql.Play (reply_handler = lambda: None,
                        error_handler = self.log.warn)


    def do_PositionGet (self):
        return self.__ql.GetPosition ()


    def __is_playing_cb (self, playing):
        if playing:
            self.cached_status.state = panflute.mpris.STATE_PLAYING
            self.start_polling_for_time ()
        else:
            # XXX: Distinguish between PAUSED and STOPPED?
            self.cached_status.state = panflute.mpris.STATE_PAUSED
            self.stop_polling_for_time ()


    def __paused_cb (self):
        self.cached_status.state = panflute.mpris.STATE_PAUSED
        self.stop_polling_for_time ()


    def __unpaused_cb (self):
        self.cached_status.state = panflute.mpris.STATE_PLAYING
        self.start_polling_for_time ()


    def __song_started_cb (self, info):
        if len (info) > 0:
            metadata = {}
            if info.has_key ("title"):
                metadata["title"] = info["title"]
            if info.has_key ("artist"):
                metadata["artist"] = info["artist"]

            if info.has_key ("album"):
                metadata["album"] = info["album"]
            elif info.has_key ("organization"):
                metadata["album"] = info["organization"]

            if info.has_key ("genre"):
                metadata["genre"] = info["genre"]
            if info.has_key ("tracknumber"):
                metadata["tracknumber"] = info["tracknumber"]
            if info.has_key ("~#length"):
                metadata["time"] = int (info["~#length"])
                metadata["mtime"] = metadata["time"] * 1000
            if info.has_key ("description"):
                metadata["comment"] = info["description"]
            if info.has_key ("~#rating"):
                # Quod Libet internally uses a scale of 0.0 to 1.0
                metadata["rating"] = int (float (info["~#rating"]) * self.__rating_scale)
                metadata["panflute rating scale"] = self.__rating_scale
            if info.has_key ("~#bitrate"):
                metadata["audio-bitrate"] = info["~#bitrate"]

            # Fake a location URI since Quod Libet doesn't report one
            pieces = [metadata[key] for key in ["artist", "album", "title"] if key in metadata]
            metadata["location"] = "bogus://" + panflute.util.make_url ("/" + "/".join (pieces))

            self.cached_metadata = metadata
            self.cached_caps.pause = metadata.get ("mtime", 0) > 0
            self.cached_caps.provide_metadata = True
        else:
            self.cached_metadata = {}
            self.cached_caps.pause = False
            self.cached_caps.provide_metadata = False


    def __song_ended_cb (self, info, skipped):
        self.cached_metadata = {}
        self.cached_caps.pause = False
        self.cached_caps.provide_metadata = False
