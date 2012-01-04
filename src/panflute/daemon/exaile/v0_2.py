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
Interface translator for Exaile 0.2.x.
"""

from __future__ import absolute_import

import panflute.daemon.connector
import panflute.daemon.dbus
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import dbus
import gobject
import re
import time


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Exaile 0.2.x.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "exaile", "Exaile",
                                                          "org.exaile.DBusInterface")
        self.props.icon_name = "exaile"


    def launch (self):
        """
        Let the MultiConnector worry about falling back.
        """

        return self.launch_via_dbus ()


    def root (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.Root ("Exaile", **kwargs)


    def track_list (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.mpris.Player):
    """
    Player object for Exaile 0.2.x.
    """

    from panflute.util import log

    NO_SONG = "No track playing"
    POLL_INTERVAL = 1000


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetStatus", "GetMetadata",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet", "VolumeGet", "VolumeSet",
                        "SetMetadata", "SetMetadata:rating"]:
            self.register_feature (feature)
        self.__last_metadata_string = None
        self._stream_start = None

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.exaile.DBusInterface", "/DBusInterfaceObject")
        self.__exaile = dbus.Interface (proxy, "org.exaile.DBusInterface")

        self.__exaile.query (reply_handler = self.__query_cb,
                             error_handler = self.log.warn)

        self.cached_caps.all = panflute.mpris.CAN_GO_NEXT | \
                               panflute.mpris.CAN_GO_PREV | \
                               panflute.mpris.CAN_PLAY

        self.__poll_everything_source = gobject.timeout_add (self.POLL_INTERVAL, self.__poll_everything_cb)


    def remove_from_connection (self):
        if self.__poll_everything_source is not None:
            gobject.source_remove (self.__poll_everything_source)
            self.__poll_everything_source = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        self.__exaile.next_track (reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_Prev (self):
        self.__exaile.prev_track (reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_Pause (self):
        self.__exaile.play_pause (reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_Stop (self):
        self.__exaile.stop (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_Play (self):
        self.__exaile.play (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_PositionGet (self):
        query_str = self.__exaile.query ()
        return self.__extract_position (query_str)


    def do_SetMetadata (self, name, value):
        if name == "rating":
            self.__exaile.set_rating (value,
                                      reply_handler = lambda: None,
                                      error_handler = self.log.warn)
            # Since we look up the rating when the song changes, fake it so
            # the client "knows" it really happened.
            self.cached_metadata["rating"] = value
        else:
            self.log.warn ("Don't know how to set {0} metadata".format (name))


    def do_VolumeGet (self):
        # Exaile reports a string like "80.0", even though volume can only
        # be an integer between 0 and 100.
        return int (float (self.__exaile.get_volume ()))


    def do_VolumeSet (self, volume):
        current_volume = self.VolumeGet ()
        if volume > current_volume:
            self.__exaile.increase_volume (volume - current_volume,
                                           reply_handler = lambda: None,
                                           error_handler = self.log.warn)
        elif volume < current_volume:
            self.__exaile.decrease_volume (current_volume - volume,
                                           reply_handler = lambda: None,
                                           error_handler = self.log.warn)


    def __poll_everything_cb (self):
        """
        Get the latest status-of-everything string from Exaile and process it.
        
        Since Exaile doesn't provide any D-Bus signals whatsoever, polling is the
        only way to find out when things change.  There's no point in using the
        base class's poll-for-time feature, since we can get the current time out
        of the status-of-everything string as it is.
        """

        self.__exaile.query (reply_handler = self.__query_cb,
                             error_handler = self.log.warn)
        return True


    def __query_cb (self, query_str):
        """
        Cache the current state values of Exaile.
        """

        self.log.debug ("Polled ==> {0}".format (query_str))

        self.cached_status.state = self.__extract_state (query_str)
        self.__update_metadata (query_str)
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.do_PositionChange (self.__extract_position (query_str))


    def __extract_state (self, query_str):
        """
        Extract the playback state from the string reported by Exaile.
        """

        if query_str.startswith ("status: playing"):
            return panflute.mpris.STATE_PLAYING
        elif query_str.startswith ("status: paused"):
            return panflute.mpris.STATE_PAUSED
        else:
            if query_str != self.NO_SONG:
                self.log.warn ("Couldn't parse the status reported by Exaile")
            return panflute.mpris.STATE_STOPPED


    def __update_metadata (self, query_str):
        """
        Update the metadata of the current song, if necessary.

        Although metadata is present in the query string, there aren't any
        unambiguous field delimiters, so we rely on calling the individual
        functions.  Since metadata doesn't change frequently, use the
        difficult-to-parse-correctly string just to detect when changes do
        occur.
        """

        if query_str != self.NO_SONG:
            match = re.match ("^status: \w+ (self:.*) position: %\d+ \[[\d:]+\]$", query_str)
            metadata_string = match.group (1)
            if match and self.__last_metadata_string != metadata_string:
                self._stream_start = None
                self.__last_metadata_string = metadata_string
                fetcher = MetadataFetcher (self, self.__exaile)
                fetcher.start ()
            elif not match:
                self.log.warn ("Failed to parse the metadata reported by Exaile")
        else:
            self.cached_metadata = {}
            self.cached_caps.pause = False
            self.cached_caps.provide_metadata = False
            self._stream_start = None


    def __extract_position (self, query_str):
        """
        Extract the current position as reported in Exaile's query result.
        However, if a radio stream is being played, make do with our own
        time counter, since Exaile doesn't report time played in a stream.
        """

        if query_str == self.NO_SONG:
            return 0
        elif self._stream_start is None:
            match = re.search ("\[([\d:]+)\]$", query_str)
            if match:
                return parse_time_string (match.group (1)) * 1000
            else:
                self.log.warn ("Failed to parse position reported by Exaile")
        else:
            return int ((time.time () - self._stream_start) * 1000)


def parse_time_string (time_str):
    """
    Convert a time string as report by Exaile into a number of seconds.
    """

    seconds = 0
    for piece in time_str.split (":"):
        seconds = seconds * 60 + int (piece)
    return seconds


class MetadataFetcher (panflute.daemon.dbus.MultiCall):
    """
    Aggregates the results of calling multiple metadata-fetching functions
    from Exaile and sets the cached metadata when the results are all in.

    Doing things this way ensures that the song metadata will be updated
    all at once, instead of one string at a time.
    """

    from panflute.util import log


    def __init__ (self, player, exaile):
        panflute.daemon.dbus.MultiCall.__init__ (self)
        self.__player = player
        self.__metadata = {}

        self.add_call (exaile.get_title,      reply_handler = self.__get_title_cb)
        self.add_call (exaile.get_artist,     reply_handler = self.__get_artist_cb)
        self.add_call (exaile.get_album,      reply_handler = self.__get_album_cb)
        self.add_call (exaile.get_length,     reply_handler = self.__get_length_cb)
        self.add_call (exaile.get_rating,     reply_handler = self.__get_rating_cb)
        self.add_call (exaile.get_cover_path, reply_handler = self.__get_cover_path_cb)


    def __get_title_cb (self, title):
        self.__metadata["title"] = title


    def __get_artist_cb (self, artist):
        self.__metadata["artist"] = artist


    def __get_album_cb (self, album):
        self.__metadata["album"] = album


    def __get_length_cb (self, length):
        seconds = parse_time_string (length)
        self.__metadata["time"] = seconds
        self.__metadata["mtime"] = seconds * 1000


    def __get_rating_cb (self, rating):
        self.__metadata["rating"] = rating
        self.__metadata["panflute rating scale"] = 5


    def __get_cover_path_cb (self, path):
        if not path.endswith ("/nocover.png"):
            self.__metadata["arturl"] = panflute.util.make_url (path)


    def finished (self):
        """
        Update the cached metadata for the player object.
        """

        self.log.debug ("Caching metadata")
        self.__player.cached_metadata = self.__metadata

        self.__player.cached_caps.provide_metadata = True
        local_file = (self.__metadata.get ("mtime", 0) > 0)
        self.__player.cached_caps.pause = local_file

        if not local_file:
            # This won't work if Exaile was already playing a stream before
            # Panflute started talking to it, but since Exaile doesn't
            # report stream time, this is the best we can do.  Just make sure
            # not to reset the time if the stream continues through a
            # metadata change.
            if self.__player._stream_start is None:
                self.__player._stream_start = time.time ()
        else:
            self.__player._stream_start = None
