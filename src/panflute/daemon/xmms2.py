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
Interface translator for XMMS2.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris

import gobject
import os
import xmmsclient
import xmmsclient.glib


class Connector (panflute.daemon.connector.PollingConnector):
    """
    Connection manager for XMMS2.
    """

    from panflute.util import log


    def __init__ (self):
        panflute.daemon.connector.PollingConnector.__init__ (self, "xmms2", "XMMS2")

        # Note that syncronous and asychronous calls on the same connection
        # tend to raise libxmmsclient errors, so we'll use separate connections
        # for each type of call.  We'll use async when we can and sync when we
        # must.

        self.__async = xmmsclient.XMMS ("Panflute")
        self.__sync_connector = None
        self.__async_connector = None


    def root (self, **kwargs):
        return Root (self.__async, **kwargs)


    def track_list (self, **kwargs):
        # TODO: Implement for real
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (self.__async, **kwargs)


    def try_connect (self):
        """
        Attempt to connect to the XMMS2 daemon.
        """

        try:
            self.log.debug ("Attempting to connect to XMMS2")

            path = os.getenv ("XMMS_PATH")
            self.__async.connect (path, self.__disconnect_cb)
            self.__async_connector = xmmsclient.glib.GLibConnector (self.__async)

            self.log.debug ("Connection established")
            self.props.connected = True

        except IOError:
            self.log.debug ("Connection failed")


    def __disconnect_cb (self, unknown):
        """
        Clean up after the XMMS2 daemon quits.
        """

        self.log.debug ("Connection lost")

        # TODO: Need to clean up after the connector?
        self.__async_connector = None

        self.props.connected = False


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for XMMS2.
    """

    def __init__ (self, async, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "XMMS2", **kwargs)
        self.__async = async


    def do_Quit (self):
        self.__async.quit (lambda result: None)


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for XMMS2.
    """

    from panflute.util import log

    ELAPSED_THRESHOLD = 250         # ms; for throttling elapsed-time updates


    def __init__ (self, async, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetStatus", "GetMetadata",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet", "PositionSet",
                        "SetMetadata", "SetMetadata:rating"]:
            self.register_feature (feature)
        self.__async = async
        self.__id = None
        self.__pos = None
        self.__elapsed = 0

        self.cached_caps.all = panflute.mpris.CAN_PLAY

        self.log.debug ("setting up broadcasts and signals")
        async.broadcast_playback_status (self.__playback_status_cb)
        async.broadcast_playlist_current_pos (self.__playlist_current_pos_cb)
        async.broadcast_playback_current_id (self.__playback_current_id_cb)
        async.broadcast_medialib_entry_changed (self.__medialib_entry_changed_cb)
        async.signal_playback_playtime (self.__playback_playtime_cb)

        self.log.debug ("starting basic calls")
        async.playback_status (self.__playback_status_cb)
        async.playlist_current_pos (None, self.__playlist_current_pos_cb)
        async.playback_current_id (self.__playback_current_id_cb)

        self.log.debug ("done with initialization")


    def do_Next (self):
        self.__async.playlist_set_next_rel (1, lambda result: self.__async.playback_tickle ())


    def do_Prev (self):
        self.__async.playlist_set_next_rel (-1, lambda result: self.__async.playback_tickle ())


    def do_Pause (self):
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.__async.playback_pause ()
        else:
            self.__async.playback_start ()


    def do_Stop (self):
        self.__async.playback_stop ()


    def do_Play (self):
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.__async.playback_seek_ms (0)
        else:
            self.__async.playback_start ()


    def do_PositionGet (self):
        # Avoid having to make a synchronous call
        return self.__elapsed


    def do_PositionSet (self, position):
        self.__async.playback_seek_ms (position)


    def do_SetMetadata (self, name, value):
        if name == "rating":
            self.__async.medialib_property_set (self.__id, "rating", value, "client/generic")
        else:
            self.log.warn ("Don't know how to set \"{0}\"".format (name))


    def __playback_status_cb (self, result):
        """
        Update the cached status to reflect that of XMMS2.
        """

        mapping = { xmmsclient.PLAYBACK_STATUS_PLAY:  panflute.mpris.STATE_PLAYING,
                    xmmsclient.PLAYBACK_STATUS_PAUSE: panflute.mpris.STATE_PAUSED,
                    xmmsclient.PLAYBACK_STATUS_STOP:  panflute.mpris.STATE_STOPPED
                  }
        state = result.value ()

        if mapping.has_key (state):
            self.cached_status.state = mapping[state]
        else:
            self.log.warn ("Unrecognized state {0}".format (state))


    def __playlist_current_pos_cb (self, result):
        """
        Check if it's possible to go previous or next from the current
        position within the playlist.
        """

        self.__pos = result.value ()
        self.log.debug ("playlist position is {0} of type {1}".format (self.__pos, type (self.__pos)))
        if type (self.__pos) == unicode:
            # Fake it
            self.__pos = { "position": 0, "name": "default" }
        self.__async.playlist_list_entries (None, self.__playlist_list_entries_cb)


    def __playlist_list_entries_cb (self, result):
        """
        Given the bounds of the current playlist, figure out whether going
        previous or next is possible.
        """

        count = len (result.value ())
        self.log.debug ("position is {0}; playlist length is {1}".format (self.__pos, count))
        self.cached_caps.go_prev = (self.__pos["position"] > 0)
        self.cached_caps.go_next = (self.__pos["position"] < count - 1)


    def __playback_current_id_cb (self, result):
        """
        Fetch metadata for the song that's now playing.
        """

        self.__id = result.value ()
        self.__async.medialib_get_info (self.__id, self.__medialib_get_info_cb)


    def __medialib_entry_changed_cb (self, result):
        """
        If the current song's metadata change, fetch it again.
        """

        if self.__id == result.value ():
            self.__async.medialib_get_info (self.__id, self.__medialib_get_info_cb)


    def __medialib_get_info_cb (self, result):
        """
        Update the cached metadata with the new information.
        """

        raw_info = result.value ()
        info = {}
        metadata = {}
        self.log.debug ("Raw metadata: {0}".format (raw_info))

        # We don't care about where each value came from.
        if raw_info is not None:
            for key in raw_info:
                if type (key) == tuple:
                    info[key[1]] = raw_info[key]
                else:
                    info[key] = raw_info[key]
        else:
            info = None

        self.log.debug ("Preprocessed metadata: {0}".format (info))

        if info is not None:
            if info.has_key ("url"):
                metadata["location"] = info["url"]

            if info.has_key ("title"):
                metadata["title"] = info["title"]

            if info.has_key ("artist"):
                metadata["artist"] = info["artist"]

            if info.has_key ("album"):
                metadata["album"] = info["album"]
            elif info.has_key ("channel"):
                metadata["album"] = info["channel"]

            if info.has_key ("duration"):
                metadata["mtime"] = info["duration"]
                metadata["time"] = info["duration"] // 1000

            if info.has_key ("genre"):
                metadata["genre"] = info["genre"]

            if info.has_key ("comment"):
                metadata["comment"] = info["comment"]

            if info.has_key ("rating"):
                metadata["rating"] = info["rating"]
                metadata["panflute rating scale"] = 5
            elif info.has_key ("vote_score") and info.has_key ("vote_count"):
                metadata["rating"] = info["vote_score"] // info["vote_count"]
                metadata["panflute rating scale"] = 5

            for key in ["album_front_large", "album_front_small", "album_front_thumbnail"]:
                if info.has_key (key):
                    metadata["arturl"] = info[key]
                    break

            if info.has_key ("bitrate"):
                metadata["audio-bitrate"] = info["bitrate"]

            if info.has_key ("samplerate"):
                metadata["audio-samplerate"] = info["samplerate"]

        self.log.debug ("Resulting metadata: {0}".format (metadata))

        self.cached_metadata = metadata

        has_song = (len (metadata) > 0)
        self.cached_caps.seek = has_song
        self.cached_caps.provide_metadata = has_song
        self.cached_caps.pause = (metadata.get ("mtime", 0) > 0)


    def __playback_playtime_cb (self, result):
        """
        Update with the latest position within the current song.
        """

        # The XMMS2 Python bindings don't seem to have a reliable way to
        # delay restarting a signal or otherwise throttle it, so ignore
        # any updates that don't exceed a certain threshold.

        if abs (result.value () - self.__elapsed) >= self.ELAPSED_THRESHOLD:
            self.__elapsed = result.value ()
            self.do_PositionChange (self.__elapsed)

        # Older versions of XMMS2 need this
        if "restart" in dir (result):
            result.restart ()
