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
Interface translator for Rhythmbox.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import dbus
import functools
import gobject


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Rhythmbox.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "rhythmbox", "Rhythmbox",
                                                          "org.gnome.Rhythmbox")
        self.props.icon_name = "rhythmbox"


    def root (self, **kwargs):
        return Root (**kwargs)


    def track_list (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for Rhythmbox.
    """

    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "Rhythmbox", **kwargs)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.gnome.Rhythmbox", "/org/gnome/Rhythmbox/Shell")
        self.__shell = dbus.Interface (proxy, "org.gnome.Rhythmbox.Shell")


    def do_Quit (self):
        self.__shell.quit ()


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for Rhythmbox.
    """

    from panflute.util import log


    NO_SONG_CAPS = panflute.mpris.CAN_PLAY

    STREAMING_CAPS = NO_SONG_CAPS |                             \
                     panflute.mpris.CAN_PROVIDE_METADATA

    LOCAL_CAPS = STREAMING_CAPS |                               \
                 panflute.mpris.CAN_GO_NEXT |                   \
                 panflute.mpris.CAN_GO_PREV |                   \
                 panflute.mpris.CAN_PAUSE |                     \
                 panflute.mpris.CAN_SEEK

    ART_FETCH_DELAY = 3000


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Next", "Prev", "Pause", "Stop", "Play",
                        "PositionGet", "PositionSet", "VolumeGet", "VolumeSet",
                        "SetMetadata", "SetMetadata:rating"]:
            self.register_feature (feature)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.gnome.Rhythmbox", "/org/gnome/Rhythmbox/Player")
        self.__player = dbus.Interface (proxy, "org.gnome.Rhythmbox.Player")

        proxy = bus.get_object ("org.gnome.Rhythmbox", "/org/gnome/Rhythmbox/Shell")
        self.__shell = dbus.Interface (proxy, "org.gnome.Rhythmbox.Shell")

        self.__handlers = [
            self.__player.connect_to_signal ("playingChanged", self.__playing_changed_cb),
            self.__player.connect_to_signal ("playingUriChanged", self.__uri_changed_cb),
            self.__player.connect_to_signal ("playingSongPropertyChanged", self.__property_changed_cb),
            self.__player.connect_to_signal ("elapsedChanged", self.__elapsed_changed_cb)
        ]

        self.__player.getPlaying (reply_handler = self.__playing_changed_cb,
                                  error_handler = self.log.warn)
        self.__player.getPlayingUri (reply_handler = self.__uri_changed_cb,
                                     error_handler = self.log.warn)

        self.cached_caps.all = self.NO_SONG_CAPS


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        self.__player.next (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_Prev (self):
        self.__player.previous (reply_handler = lambda: None,
                                error_handler = self.log.warn)


    def do_Pause (self):
        self.__player.playPause (False,
                                 reply_handler = lambda: None,
                                 error_handler = self.log.warn)


    def do_Stop (self):
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.__player.playPause (False,
                                     reply_handler = lambda: None,
                                     error_handler = self.log.warn)


    def do_Play (self):
        if self.cached_status.state == panflute.mpris.STATE_PLAYING:
            self.__player.setElapsed (0,
                                      reply_handler = lambda: None,
                                      error_handler = self.log.warn)
        else:
            self.__player.playPause (False,
                                     reply_handler = lambda: None,
                                     error_handler = self.log.warn)


    def do_PositionGet (self):
        # FIXME: Any way to run this asynchronously?
        return self.__player.getElapsed () * 1000


    def do_PositionSet (self, elapsed):
        self.__player.setElapsed (elapsed // 1000,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_VolumeGet (self):
        # FIXME: Any way to run this asynchronously?
        return int (self.__player.getVolume () * panflute.mpris.VOLUME_MAX)


    def do_VolumeSet (self, volume):
        self.__player.setVolume (volume / panflute.mpris.VOLUME_MAX,
                                 reply_handler = lambda: None,
                                 error_handler = self.log.warn)


    def do_SetMetadata (self, name, value):
        # TODO: What fields besides "rating" should be settable?
        uri = self.cached_metadata.get ("location", None)
        if uri is not None:
            if name == "rating":
                new_rating = max (0.0, min (5.0, float (value)))
                self.__shell.setSongProperty (uri, "rating", new_rating,
                                              reply_handler = lambda: None,
                                              error_handler = self.log.warn)
                self.__update_metadata ("rating", round (new_rating))
            else:
                self.log.warn ("Don't know how to set {0} to {1}".format (name, value))


    def __playing_changed_cb (self, playing):
        """
        Update the cached state with the current playback state.
        """

        # TODO: Distinguish between PAUSED and STOPPED
        if playing:
            self.cached_status.state = panflute.mpris.STATE_PLAYING
        else:
            self.cached_status.state = panflute.mpris.STATE_PAUSED


    def __uri_changed_cb (self, uri):
        """
        If a new URI is being played, fetch its metadata.
        """

        if uri == "":
            uri = None
        if self.__different_uri (uri):
            if uri is not None:
                self.__shell.getSongProperties (uri,
                                                reply_handler = functools.partial (self.__song_properties_cb, uri),
                                                error_handler = self.log.warn)
            else:
                self.cached_metadata = {}
                self.cached_caps.all = self.NO_SONG_CAPS


    def __song_properties_cb (self, uri, props):
        """
        Update the cached metadata with the current track.
        """

        self.log.debug ("Got metadata for {0}".format (uri))

        metadata = {"location": str (uri)}
        for k in props.keys ():
            self.__process_metadata_field (metadata, k, props[k])

        self.cached_metadata = metadata

        # Rhythmbox sometimes take a few seconds to load artwork, and won't
        # announce a metadata change when it is loaded, so manually check
        # for artwork later if needed.

        if not metadata.has_key ("arturl"):
            gobject.timeout_add (self.ART_FETCH_DELAY, lambda: self.__check_for_art (uri))

        if props["duration"] > 0:
            self.cached_caps.all = self.LOCAL_CAPS
        else:
            self.cached_caps.all = self.STREAMING_CAPS


    def __check_for_art (self, uri):
        """
        Get the latest metadata for the current song (if it hasn't changed)
        to get the new artwork that may be available.
        """

        if self.cached_metadata.get ("location", None) == uri:
            self.log.debug ("Checking for delayed art")
            self.__shell.getSongProperties (uri,
                                            reply_handler = functools.partial (self.__update_art_cb, uri),
                                            error_handler = self.log.warn)


    def __update_art_cb (self, uri, props):
        """
        If artwork is now available, update the cached metadata accordingly.
        """

        for name in ["rb:coverArt", "rb:coverArt-uri"]:
            if props.has_key (name):
                self.__process_metadata_field (self.cached_metadata, name, props[name])


    def __different_uri (self, uri):
        """
        Check if the URI of the cached metadata is different than this
        one, treating "both unset" as the same.
        """

        cached_uri = self.cached_metadata.get ("location", None)
        return cached_uri != uri


    def __property_changed_cb (self, uri, property, old_value, new_value):
        """
        Update the metadata for the current song when new data is available.
        """

        self.log.debug ("property changed: {0} is now {1}".format (property, new_value))
        self.__update_metadata (property, new_value)


    def __update_metadata (self, name, value):
        """
        Change a single piece of metadata for the current song.
        """

        self.__process_metadata_field (self.cached_metadata, name, value)


    def __process_metadata_field (self, metadata, name, value):
        """
        Process a piece of metadata from Rhythmbox and add it to the MPRIS
        metadata dict.
        """

        if name == "title":
            metadata["title"] = value
        elif name == "rb:stream-song-title":
            # Special case: Rhythmbox uses "title" as the album if the stream
            # never specifies its own album.  Do likewise.
            if not metadata.has_key ("album") and metadata.has_key ("title"):
                metadata["album"] = metadata["title"]
            metadata["title"] = value
        elif name == "artist" or name == "rb:stream-song-artist":
            metadata["artist"] = value
        elif name == "album" or name == "rb:stream-song-album":
            metadata["album"] = value
        elif name == "track-number":
            metadata["tracknumber"] = value
        elif name == "duration":
            metadata["time"] = value
            metadata["mtime"] = value * 1000
        elif name == "genre":
            metadata["genre"] = value
        elif name == "description":
            metadata["comment"] = value
        elif name == "rating":
            metadata["rating"] = round (value)
            metadata["panflute rating scale"] = 5
        elif name == "year":
            metadata["year"] = value
        elif name == "post-time":
            metadata["date"] = value
        elif name == "rb:coverArt" or name == "rb:coverArt-uri":
            metadata["arturl"] = panflute.util.make_url (value)
        elif name == "mb-trackid":
            metadata["mb track id"] = value
        elif name == "mb-artistid":
            metadata["mb artist id"] = value
        elif name == "mb-artistsortname":
            metadata["mb artist sort name"] = value
        elif name == "mb-albumartistid":
            metadata["mb album artist id"] = value
        elif name == "bitrate":
            metadata["audio-bitrate"] = value


    def __elapsed_changed_cb (self, elapsed):
        """
        Forward the notification that the position has changed.
        """

        self.do_PositionChange (elapsed * 1000)
