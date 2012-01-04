#! /usr/bin/env python

# Panflute
# Copyright (C) 2009 Paul Kuliniewicz <paul@kuliniewicz.org>
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
Interface "translator" for existing MPRIS interfaces.

These do nothing more than add support for the extended Panflute interfaces.
Everything else is directly passed through to the player's own MPRIS
interface.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris

import dbus
import gobject


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for MPRIS-based players.
    """

    def __init__ (self, internal_name, display_name, mpris_name):
        panflute.daemon.connector.DBusConnector.__init__ (self, internal_name, display_name,
                                                          "org.mpris.{0}".format (mpris_name))
        self.__name = mpris_name


    def root (self, **kwargs):
        return Root (self.__name, self.props.display_name, **kwargs)


    def track_list (self, **kwargs):
        return TrackList (self.__name, **kwargs)


    def player (self, **kwargs):
        return Player (self.__name, False, **kwargs)


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS pass-through object.
    """

    from panflute.util import log


    def __init__ (self, mpris_name, display_name, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, display_name, **kwargs)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mpris.{0}".format (mpris_name), "/")
        self._root = dbus.Interface (proxy, panflute.mpris.INTERFACE)


    def do_Quit (self):
        self._root.Quit (reply_handler = lambda: None,
                         error_handler = self.log.warn)


class TrackList (panflute.daemon.mpris.TrackList):
    """
    TrackList MPRIS pass-through object.
    """

    from panflute.util import log


    def __init__ (self, name, **kwargs):
        panflute.daemon.mpris.TrackList.__init__ (self, **kwargs)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mpris.{0}".format (name), "/TrackList")
        self._track_list = dbus.Interface (proxy, panflute.mpris.INTERFACE)

        self.__handlers = [
            self._track_list.connect_to_signal ("TrackListChange", self.do_TrackListChange)
        ]


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = []

        panflute.daemon.mpris.TrackList.remove_from_connection (self)


    def do_GetMetadata (self, index):
        return self._track_list.GetMetadata (index)


    def do_GetCurrentTrack (self):
        return self._track_list.GetCurrentTrack ()


    def do_GetLength (self):
        return self._track_list.GetLength ()


    def do_AddTrack (self, uri, play_immediately):
        return self._track_list.AddTrack (uri, play_immediately)


    def do_DelTrack (self, index):
        self._track_list.DelTrack (index,
                                   reply_handler = lambda: None,
                                   error_handler = self.log.warn)


    def do_SetLoop (self, loop):
        self._track_list.SetLoop (loop,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_SetRandom (self, shuffle):
        self._track_list.SetRandom (shuffle,
                                     reply_handler = lambda: None,
                                     error_handler = self.log.warn)


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS pass-through object, with extended functionality.
    """

    from panflute.util import log

    POLL_INTERVAL = 1000
    METADATA_POLL_INTERVAL = 15000


    def __init__ (self, name, poll_metadata_when_streaming, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        self._register_standard_features ()
        self.__poll_metadata_when_streaming = poll_metadata_when_streaming
        self.__poll_metadata_source = None

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mpris.{0}".format (name), "/Player")
        self._player = dbus.Interface (proxy, panflute.mpris.INTERFACE)

        self.__handlers = [
            self._player.connect_to_signal ("TrackChange", self.do_TrackChange),
            self._player.connect_to_signal ("StatusChange", self.do_StatusChange),
            self._player.connect_to_signal ("CapsChange", self.do_CapsChange)
        ]

        self._player.GetStatus (reply_handler = self._get_status_cb,
                                error_handler = self.log.warn)

        if self.__poll_metadata_when_streaming:
            # Called for the side effect in do_GetMetadata.
            self.GetMetadata ()


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = []

        if self.__poll_metadata_source is not None:
            gobject.source_remove (self.__poll_metadata_source)
            self.__poll_metadata_source = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def _register_standard_features (self):
        """
        Registers the standard set of MPRIS Player features.  Override this if
        for some reason a player that implements MPRIS itself doesn't support
        everything.
        """

        for feature in ["Next", "Prev", "Pause", "Stop", "Play", "Repeat",
                        "GetStatus", "GetMetadata", "GetCaps",
                        "VolumeSet", "VolumeGet", "PositionSet", "PositionGet"]:
            self.register_feature (feature)


    def do_Next (self):
        self._player.Next (reply_handler = lambda: None,
                           error_handler = self.log.warn)


    def do_Prev (self):
        self._player.Prev (reply_handler = lambda: None,
                           error_handler = self.log.warn)


    def do_Pause (self):
        self._player.Pause (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_Stop (self):
        self._player.Stop (reply_handler = lambda: None,
                           error_handler = self.log.warn)


    def do_Play (self):
        self._player.Play (reply_handler = lambda: None,
                           error_handler = self.log.warn)


    def do_Repeat (self, repeat):
        self._player.Repeat (repeat,
                             reply_handler = lambda: None,
                             error_handler = self.log.warn)


    def do_GetStatus (self):
        return self._player.GetStatus ()


    def do_GetMetadata (self):
        metadata = self._player.GetMetadata ()
        metadata = self._normalize_metadata (metadata)
        if self.__poll_metadata_when_streaming:
            self.__configure_metadata_polling (metadata)
        return metadata


    def do_SetMetadata (self, name, value):
        self.log.warn ("SetMetadata not supported")


    def do_GetCaps (self):
        return self._player.GetCaps ()


    def do_VolumeSet (self, volume):
        self._player.VolumeSet (volume,
                                reply_handler = lambda: None,
                                error_handler = self.log.warn)


    def do_VolumeGet (self):
        return self._player.VolumeGet ()


    def do_PositionSet (self, position):
        self._player.PositionSet (position,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_PositionGet (self):
        return self._player.PositionGet ()


    def do_StatusChange (self, status):
        panflute.daemon.mpris.Player.do_StatusChange (self, status)
        self._get_status_cb (status)


    def do_TrackChange (self, metadata):
        metadata = self._normalize_metadata (metadata)
        if self.__poll_metadata_when_streaming:
            self.__configure_metadata_polling (metadata)
        panflute.daemon.mpris.Player.do_TrackChange (self, metadata)


    def _get_status_cb (self, status):
        """
        Set up polling for position changes.
        """

        state = status[panflute.mpris.STATUS_STATE]
        if state == panflute.mpris.STATE_PLAYING:
            self.start_polling_for_time ()
        elif state != panflute.mpris.STATE_PLAYING:
            self.stop_polling_for_time ()


    def _normalize_metadata (self, metadata):
        """
        Normalize the set of metadata fields being reported, either returning a
        new object or modifying the argument in-place.

        The MPRIS spec is fairly lax when saying what the reported metadata for
        a song looks like, but makes some recommendations.  The goal here is to
        fill in these fields if possible with out-of-spec fields that are in
        common use.
        """

        # Some players (such as Audacious and VLC) report "length" in milliseconds
        # instead of "mtime" and "time".

        if metadata is not None and metadata != {}:
            if metadata.has_key ("length"):
                if not metadata.has_key ("mtime"):
                    metadata["mtime"] = metadata["length"]
                if not metadata.has_key ("time"):
                    metadata["time"] = metadata["length"] // 1000
            if metadata.get ("time", -1) < 0:
                metadata["time"] = 0
            if metadata.get ("mtime", -1) < 0:
                metadata["mtime"] = 0
            if "rating" in metadata:
                metadata["panflute rating scale"] = 5
            return metadata
        else:
            return {}


    def __configure_metadata_polling (self, metadata):
        """
        Poll for updated metadata if and only if the current song is a radio
        stream.

        This is needed for players (such as Amarok and Audacious) that don't
        report metadata changes while playing a stream.
        """

        if metadata.has_key ("mtime") and metadata["mtime"] == 0 and self.__poll_metadata_source is None:
            self.log.debug ("beginning to poll for radio stream metadata")
            self.__poll_metadata_source = gobject.timeout_add (self.METADATA_POLL_INTERVAL, self.__poll_metadata_cb)
            self.cached_metadata = metadata
        elif (not metadata.has_key ("mtime") or metadata["mtime"] > 0) and self.__poll_metadata_source is not None:
            self.log.debug ("stopping polling for radio stream metadata")
            gobject.source_remove (self.__poll_metadata_source)
            self.__poll_metadata_source = None


    def __poll_metadata_cb (self):
        """
        Cache the current metadata for the radio stream, relying on the cache
        to decide whether things have changed.
        """

        self.log.debug ("polling for radio stream metadata")
        self.cached_metadata = self.GetMetadata ()
        return True
