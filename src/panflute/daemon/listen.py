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
Interface translator for Listen.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.dbus
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import dbus
import gobject


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Listen.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "listen", "Listen",
                                                          "org.gnome.Listen")
        self.props.icon_name = "listen"


    def root (self, **kwargs):
        return Root (**kwargs)


    def track_list (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for Listen.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "Listen", **kwargs)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.gnome.Listen", "/org/gnome/listen")
        self.__player = dbus.Interface (proxy, "org.gnome.Listen")


    def do_Quit (self):
        self.__player.quit (reply_handler = lambda reply: None,
                            error_handler = self.log.warn)


class Player (panflute.daemon.mpris.Player):
    """
    Player object for Listen.
    """

    from panflute.util import log

    POLL_INTERVAL = 1000


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Pause", "Play", "Stop", "Prev", "Next",
                        "PositionGet", "VolumeSet"]:
            self.register_feature (feature)
        self.__uri = None

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.gnome.Listen", "/org/gnome/listen")
        self.__player = dbus.Interface (proxy, "org.gnome.Listen")

        self.__poll_everything_source = gobject.timeout_add (self.POLL_INTERVAL, self.__poll_everything_cb)
        self.__poll_everything_cb ()

        self.cached_caps.go_next = True
        self.cached_caps.go_prev = True
        self.cached_caps.pause = True
        self.cached_caps.play = True


    def remove_from_connection (self):
        if self.__poll_everything_source is not None:
            gobject.source_remove (self.__poll_everything_source)
            self.__poll_everything_source = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_PositionGet (self):
        elapsed = self.__player.current_position () * 1000
        if elapsed < 0:
            self.log.debug ("Reported invalid position {0}".format (elapsed))
            return 0
        return elapsed


    def do_Pause (self):
        self.__player.play_pause (reply_handler = lambda result: None,
                                  error_handler = self.log.warn)


    def do_Play (self):
        if self.cached_status.state != panflute.mpris.STATE_PLAYING:
            self.__player.play_pause (reply_handler = lambda result: None,
                                      error_handler = self.log.warn)


    def do_Stop (self):
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.__player.play_pause (reply_handler = lambda result: None,
                                      error_handler = self.log.warn)


    def do_Next (self):
        self.__player.next (reply_handler = lambda result: None,
                            error_handler = self.log.warn)


    def do_Prev (self):
        self.__player.previous (reply_handler = lambda result: None,
                                error_handler = self.log.warn)


    def do_VolumeSet (self, volume):
        self.__player.volume (volume / panflute.mpris.VOLUME_MAX,
                              reply_handler = lambda result: None,
                              error_handler = self.log.warn)


    def __poll_everything_cb (self):
        """
        Poll for assorted information.
        """

        self.__player.playing (reply_handler = self.__playing_cb,
                               error_handler = self.log.warn)

        fetcher = SongFetcher (self, self.__player)
        fetcher.start ()

        return True


    def __playing_cb (self, playing):
        """
        Update the cached status with whether Listen is playing.
        """

        if playing:
            self.cached_status.state = panflute.mpris.STATE_PLAYING
            self.start_polling_for_time ()
        else:
            self.cached_status.state = panflute.mpris.STATE_PAUSED
            self.stop_polling_for_time ()


    def _set_uri (self, uri):
        """
        Begin the process of updating the cached metadata, if the
        current song has changed.
        """

        if uri is None or uri == "":
            self.__uri = None
            self.cached_metadata = {}
            self.cached_caps.provide_metadata = False
        elif uri != self.__uri:
            self.__uri = uri
            fetcher = MetadataFetcher (self, self.__player, uri)
            fetcher.start ()


class SongFetcher (panflute.daemon.dbus.MultiCall):
    """
    Aggregates the information needed to determine whether the lack of a
    current song as reported by Listen is because there truly is no
    current song, or because it's simply paused (in which case Listen for
    some reason reports no song).
    """

    from panflute.util import log

    def __init__ (self, player, listen):
        panflute.daemon.dbus.MultiCall.__init__ (self)
        self.__player = player
        self.__uri = None
        self.__elapsed = 0

        self.add_call (listen.get_uri,          reply_handler = self.__get_uri_cb)
        self.add_call (listen.current_position, reply_handler = self.__current_position_cb)


    def __get_uri_cb (self, uri):
        self.__uri = uri


    def __current_position_cb (self, position):
        self.__elapsed = position * 1000


    def finished (self):
        self.log.debug ("uri: {0}; elapsed: {1}".format (self.__uri, self.__elapsed))
        if (self.__uri is None or self.__uri == "") and self.__elapsed == 0:
            self.__player._set_uri (None)
        elif self.__uri != "":
            self.__player._set_uri (self.__uri)


class MetadataFetcher (panflute.daemon.dbus.MultiCall):
    """
    Aggregates the results of calling multiple metadata-fetching functions
    from Listen and sets the cached metadata when the results are all in.

    Doing things this way ensures that the song metadata will be updated
    all at once, instead of one string at a time.
    """

    from panflute.util import log


    def __init__ (self, player, listen, uri):
        panflute.daemon.dbus.MultiCall.__init__ (self)
        self.__player = player
        self.__metadata = {"location": uri}
        self.__uri = uri

        self.add_call (listen.get_title,           reply_handler = self.__get_title_cb)
        self.add_call (listen.get_artist,          reply_handler = self.__get_artist_cb)
        self.add_call (listen.get_album,           reply_handler = self.__get_album_cb)
        self.add_call (listen.current_song_length, reply_handler = self.__current_song_length_cb)
        self.add_call (listen.get_cover_path,      reply_handler = self.__get_cover_path_cb)


    def __get_title_cb (self, title = None):
        if title is not None:
            self.__metadata["title"] = title


    def __get_artist_cb (self, artist):
        self.__metadata["artist"] = artist


    def __get_album_cb (self, album):
        self.__metadata["album"] = album


    def __current_song_length_cb (self, length):
        self.__metadata["time"] = length
        self.__metadata["mtime"] = length * 1000


    def __get_cover_path_cb (self, path):
        self.__metadata["arturl"] = panflute.util.make_url (path)


    def finished (self):
        """
        Decrement the count of pending replies, and if it's reached zero,
        update the cached metadata for the player object.
        """

        self.log.debug ("Caching metadata")
        self.__player.cached_metadata = self.__metadata
        self.__player.cached_caps.provide_metadata = True
