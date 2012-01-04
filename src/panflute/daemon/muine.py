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
Interface translator for Muine.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import dbus
import tempfile


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Muine.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "muine", "Muine",
                                                          "org.mate.Muine")
        self.props.icon_name = "muine"


    def root (self, **kwargs):
        return Root (**kwargs)


    def track_list (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for Muine.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "Muine", **kwargs)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mate.Muine", "/org/mate/Muine/Player")
        self.__player = dbus.Interface (proxy, "org.mate.Muine.Player")


    def do_Quit (self):
        self.__player.Quit (reply_handler = lambda: None,
                            error_handler = self.log.warn)


class Player (panflute.daemon.mpris.Player):
    """
    Player object for Muine.
    """

    from panflute.util import log


    NO_SONG_CAPS = panflute.mpris.CAN_PLAY

    PLAYING_CAPS = NO_SONG_CAPS |                           \
                   panflute.mpris.CAN_PAUSE |               \
                   panflute.mpris.CAN_SEEK |                \
                   panflute.mpris.CAN_PROVIDE_METADATA


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet", "PositionSet", "VolumeGet", "VolumeSet"]:
            self.register_feature (feature)
        self.__art_file = None

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mate.Muine", "/org/mate/Muine/Player")
        self.__player = dbus.Interface (proxy, "org.mate.Muine.Player")

        self.cached_caps.all = self.NO_SONG_CAPS

        self.__handlers = [
            self.__player.connect_to_signal ("StateChanged", self.__state_changed_cb),
            self.__player.connect_to_signal ("SongChanged", self.__song_changed_cb)
        ]

        self.__player.GetPlaying (reply_handler = self.__state_changed_cb,
                                  error_handler = self.log.warn)
        self.__player.GetCurrentSong (reply_handler = self.__song_changed_cb,
                                      error_handler = self.log.warn)


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = []

        if self.__art_file is not None:
            self.__art_file.close ()
            self.__art_file = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        self.__player.Next (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_Prev (self):
        self.__player.Previous (reply_handler = lambda: None,
                                error_handler = self.log.warn)


    def do_Pause (self):
        playing = (self.cached_status.state == panflute.mpris.STATE_PLAYING)
        self.__player.SetPlaying (not playing,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_Stop (self):
        self.__player.SetPlaying (False,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_Play (self):
        self.__player.SetPlaying (True,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_PositionGet (self):
        return self.__player.GetPosition () * 1000


    def do_PositionSet (self, position):
        self.__player.SetPosition (position // 1000,
                                   reply_handler = lambda: None,
                                   error_handler = self.log.warn)


    def do_VolumeGet (self):
        return self.__player.GetVolume ()


    def do_VolumeSet (self, volume):
        self.__player.SetVolume (volume,
                                 reply_handler = lambda: None,
                                 error_handler = self.log.warn)


    def __state_changed_cb (self, playing):
        """
        Update the cached state with whether or not Muine is currently playing.
        """

        if playing:
            self.cached_status.state = panflute.mpris.STATE_PLAYING
            self.start_polling_for_time ()
        else:
            self.cached_status.state = panflute.mpris.STATE_PAUSED
            self.stop_polling_for_time ()


    def __song_changed_cb (self, description):
        """
        Update the cached song metadata with the current song.
        """

        if self.__art_file is not None:
            self.__art_file.close ()
            self.__art_file = None

        if description != "":
            metadata = {}
            for line in description.split ("\n"):
                [key, value] = line.split (": ")
                if key == "uri":
                    metadata["location"] = panflute.util.make_url (value)
                elif key == "title":
                    metadata["title"] = value
                elif key == "artist":
                    metadata["artist"] = value
                elif key == "album":
                    metadata["album"] = value
                elif key == "year":
                    metadata["year"] = int (value)
                elif key == "track_number":
                    metadata["tracknumber"] = value
                elif key == "duration":
                    metadata["mtime"] = int (value) * 1000
                    metadata["time"] = int (value)

            self.cached_metadata = metadata
            self.cached_caps.all = self.PLAYING_CAPS
            self.__player.HasNext (reply_handler = self.cached_caps.bit_set_func (panflute.mpris.CAN_GO_NEXT),
                                   error_handler = self.log.warn)
            self.__player.HasPrevious (reply_handler = self.cached_caps.bit_set_func (panflute.mpris.CAN_GO_PREV),
                                       error_handler = self.log.warn)

            self.__art_file = tempfile.NamedTemporaryFile (suffix = ".png")
            self.__player.WriteAlbumCoverToFile (self.__art_file.name,
                                                 reply_handler = self.__write_album_cover_cb,
                                                 error_handler = self.log.warn)
        else:
            self.cached_metadata = {}
            self.cached_caps.all = self.NO_SONG_CAPS


    def __write_album_cover_cb (self, success):
        """
        If Muine successfully exported the album cover to the temporary file,
        update the cached metadata.
        """

        if success:
            self.cached_metadata["arturl"] = panflute.util.make_url (self.__art_file.name)
        elif self.__art_file is not None:
            # If Muine starts up while Panflute is running, there could be two calls to
            # WriteAlbumCoverToFile pending at the same time, in which case it could fail
            # both times and then try to close an already-closed-and-None'd file.
            self.__art_file.close ()
            self.__art_file = None
