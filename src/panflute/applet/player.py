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
GObject-based interface to the Panflute MPRIS daemon.

This module encapsulates the details of talking to the Panflute MPRIS
daemon, exposing the various interfaces through a single object.
"""

from __future__ import absolute_import

import panflute.defs
import panflute.mpris

import dbus
import gobject
import gtk
import Queue
import threading
import urllib


class Player (gobject.GObject):
    """
    Proxy object for the Panflute MPRIS daemon.

    This caches the current state exposed by the daemon, eliminating some of
    the communications that would otherwise be needed.  It particular, it makes
    it possible to create widgets that can immediately access the current
    state of the player, without needing one or more round trips to get that
    information from the daemon.
    """


    ##########################################################################
    

    __gproperties__ = {
        "can-pause": (gobject.TYPE_BOOLEAN,
                      "can-pause",
                      "Whether the player can currently pause",
                      False,
                      gobject.PARAM_READABLE),

        "can-go-next": (gobject.TYPE_BOOLEAN,
                        "can-go-next",
                        "Whether the player can currently go to the next song",
                        False,
                        gobject.PARAM_READABLE),

        "can-go-previous": (gobject.TYPE_BOOLEAN,
                            "can-go-previous",
                            "Whether the player can currently go to the previous song",
                            False,
                            gobject.PARAM_READABLE),

        "can-seek": (gobject.TYPE_BOOLEAN,
                     "can-seek",
                     "Whether the player can seek within the current song",
                     False,
                     gobject.PARAM_READABLE),

        "state": (gobject.TYPE_UINT,
                  "state",
                  "Current playback state",
                  panflute.mpris.STATE_MIN, panflute.mpris.STATE_MAX,
                  panflute.mpris.STATE_STOPPED,
                  gobject.PARAM_READABLE),

        "location": (gobject.TYPE_STRING,
                     "location",
                     "URI of the song itself",
                     None,
                     gobject.PARAM_READABLE),

        "title": (gobject.TYPE_STRING,
                  "title",
                  "Title of the current song",
                  None,
                  gobject.PARAM_READABLE),

        "artist": (gobject.TYPE_STRING,
                   "artist",
                   "Artist performing the current song",
                   None,
                   gobject.PARAM_READABLE),

        "album": (gobject.TYPE_STRING,
                  "album",
                  "Album the current song is from",
                  None,
                  gobject.PARAM_READABLE),

        "track-number": (gobject.TYPE_STRING,
                         "track-number",
                         "Track number of the song on its album",
                         None,
                         gobject.PARAM_READABLE),

        "genre": (gobject.TYPE_STRING,
                  "genre",
                  "Genre of the song",
                  None,
                  gobject.PARAM_READABLE),

        "duration": (gobject.TYPE_UINT,
                     "duration",
                     "Length of the current song, in milliseconds",
                     0, gobject.G_MAXUINT,
                     0,
                     gobject.PARAM_READABLE),

        "year": (gobject.TYPE_UINT,
                 "year",
                 "Year the song was made",
                 0, gobject.G_MAXUINT,
                 0,
                 gobject.PARAM_READABLE),

        "elapsed": (gobject.TYPE_UINT,
                    "elapsed",
                    "Position within the current song, in milliseconds",
                    0, gobject.G_MAXUINT,
                    0,
                    gobject.PARAM_READABLE),

        "rating": (gobject.TYPE_UINT,
                   "rating",
                   "Rating of the current song",
                   0, 10,
                   0,
                   gobject.PARAM_READABLE),

        "rating-scale": (gobject.TYPE_UINT,
                         "rating-scale",
                         "The size of the scale used to rate the song",
                         0, 10,
                         0,
                         gobject.PARAM_READABLE),

        "art": (gobject.TYPE_OBJECT,
                "art",
                "Artwork associated with the current song",
                gobject.PARAM_READABLE),

        "art-file": (gobject.TYPE_STRING,
                     "art-file",
                     "File name of the artwork associated with the current song",
                     None,
                     gobject.PARAM_READABLE),

        "volume": (gobject.TYPE_UINT,
                   "volume",
                   "Volume of the song being played",
                   0, 100,
                   50,
                   gobject.PARAM_READWRITE)
    }


    from panflute.util import log


    def __init__ (self):
        gobject.GObject.__init__ (self)

        self.__props = {
            "can-pause":       False,
            "can-go-next":     False,
            "can-go-previous": False,
            "can-seek":        False,
            "state":           panflute.mpris.STATE_STOPPED,
            "location":        None,
            "title":           None,
            "artist":          None,
            "album":           None,
            "track-number":    None,
            "genre":           None,
            "duration":        0,
            "year":            0,
            "elapsed":         0,
            "rating":          0,
            "rating-scale":    0,
            "art":             None,
            "art-file":        None,
            "volume":          50
        }

        self.__queue = Queue.Queue (-1)
        self.__art_thread = ArtLoaderThread (self, self.__queue)
        self.__art_thread.start ()
        self.__features = []

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.mpris.panflute", "/Player")
        self.__player = dbus.Interface (proxy, panflute.mpris.INTERFACE)
        self.__player_ex = dbus.Interface (proxy, "org.kuliniewicz.Panflute")

        self.__dbus_handlers = [
            self.__player.connect_to_signal ("CapsChange", self.__caps_change_cb),
            self.__player.connect_to_signal ("StatusChange", self.__status_change_cb),
            self.__player.connect_to_signal ("TrackChange", self.__track_change_cb),
            self.__player_ex.connect_to_signal ("PositionChange", self.__position_change_cb),
            self.__player_ex.connect_to_signal ("FeatureAdded", self.__feature_added_cb)
        ]

        self.__player.GetCaps (reply_handler = self.__caps_change_cb,
                               error_handler = self.log.warn)
        self.__player.GetStatus (reply_handler = self.__status_change_cb,
                                 error_handler = self.log.warn)
        self.__player.GetMetadata (reply_handler = self.__track_change_cb,
                                   error_handler = self.log.warn)
        self.__player.PositionGet (reply_handler = self.__position_change_cb,
                                   error_handler = self.log.warn)
        self.__player_ex.GetFeatures (reply_handler = self.__get_features_cb,
                                      error_handler = self.log.warn)


    def __del__ (self):
        self.log.debug ("Inside destructor")

        self.shutdown ()
        for handler in self.__dbus_handlers:
            handler.disconnect ()
        self.__dbus_handlers = []


    def do_get_property (self, property):
        return self.__props[property.name]


    def do_set_property (self, property, value):
        if property.name == "volume":
            self.__props["volume"] = value
            self.__player.VolumeSet (value, reply_handler = lambda: None,
                                            error_handler = self.log.warn)


    def _set_property (self, name, value):
        """
        Set the value of a property, issuing the notify signal if the value
        does in fact change.

        This is distinct from the set_property provided by gobject in that
        it prevents outsiders from trying to set properties.
        """

        if self.__props[name] != value:
            self.__props[name] = value
            self.notify (name)


    def __get_features_cb (self, features):
        """
        Add the current set of features to those known to exist.
        """

        for feature in features:
            self.__feature_added_cb (feature)


    def __feature_added_cb (self, feature):
        """
        Add a newly detected feature to those known to exist.
        """

        self.__features.append (feature)
        if feature == "VolumeGet":
            self.__player.VolumeGet (reply_handler = self.__volume_get_cb,
                                     error_handler = self.log.warn)
        self.emit ("feature-added", feature)


    def supports (self, feature):
        """
        Check if the player supports a particular feature.
        """

        return feature in self.__features


    def __caps_change_cb (self, caps):
        """
        Update the capabilities properties with the current caps.
        """

        self._set_property ("can-pause", (caps & panflute.mpris.CAN_PAUSE) != 0)
        self._set_property ("can-go-next", (caps & panflute.mpris.CAN_GO_NEXT) != 0)
        self._set_property ("can-go-previous", (caps & panflute.mpris.CAN_GO_PREV) != 0)
        self._set_property ("can-seek", (caps & panflute.mpris.CAN_SEEK) != 0)


    def __status_change_cb (self, status):
        """
        Update the status properties with the current status.
        """

        self._set_property ("state", status[panflute.mpris.STATUS_STATE])


    def __track_change_cb (self, metadata):
        """
        Update the properties with the latest metadata.
        """

        old_title = self.props.title
        old_artist = self.props.artist
        old_album = self.props.album

        self._set_property ("location", metadata.get ("location", None))
        self._set_property ("title", metadata.get ("title", None))
        self._set_property ("artist", metadata.get ("artist", None) or None)
        self._set_property ("album", metadata.get ("album", None) or None)
        self._set_property ("track-number", metadata.get ("tracknumber", None) or None)
        self._set_property ("genre", metadata.get ("genre", None) or None)
        self._set_property ("duration", metadata.get ("mtime", 0))
        self._set_property ("year", metadata.get ("year", 0))
        self._set_property ("rating", metadata.get ("rating", 0))
        self._set_property ("rating-scale", metadata.get ("panflute rating scale", 0))

        self._set_property ("art-file", None)
        self._set_property ("art", None)
        self.__queue.put ("{0} {1}".format (metadata.get ("location", "-"), metadata.get ("arturl", "-")))

        if self.props.title != old_title or self.props.artist != old_artist or self.props.album != old_album:
            self.emit ("song-changed")


    def __position_change_cb (self, position):
        """
        Update the elapsed property with the latest value.
        """

        self._set_property ("elapsed", position)


    def __volume_get_cb (self, volume):
        """
        Update the volume with the current value.
        """

        self._set_property ("volume", volume)


    def pause (self):
        """
        Play or pause playback.

        This pedantically figures out which MPRIS method should be called to
        actually play or pause (or stop) playback, since Pause won't necessarily
        actually toggle playback for some MPRIS players (e.g. Audacious won't
        start playing in response to a Pause if playback is stopped).
        """

        if self.props.state == panflute.mpris.STATE_PLAYING:
            if self.props.can_pause:
                method = self.__player.Pause
            else:
                method = self.__player.Stop
        elif self.props.state == panflute.mpris.STATE_PAUSED:
            method = self.__player.Pause
        else:
            method = self.__player.Play

        method (reply_handler = lambda: None,
                error_handler = self.log.warn)


    def stop (self):
        """
        Unconditionally stop playback.
        """

        self.__player.Stop (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def next (self):
        """
        Advance to the next song.
        """

        self.__player.Next (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def previous (self):
        """
        Go back to the previous song.
        """

        self.__player.Prev (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def rate_song (self, rating):
        """
        Rate the current song.
        """

        self.__player_ex.SetMetadata ("rating", rating,
                                      reply_handler = lambda: None,
                                      error_handler = self.log.warn)


    def seek (self, position):
        """
        Seek to a position within the current song.
        """

        self.__player.PositionSet (int (position),
                                   reply_handler = lambda: None,
                                   error_handler = self.log.warn)


    def shutdown (self):
        """
        Shut down the album art thread cleanly.
        """

        if self.__art_thread is not None:
            self.__queue.put ("")
            self.__art_thread = None


gobject.type_register (Player)
gobject.signal_new ("song-changed", Player,
                    gobject.SIGNAL_RUN_LAST,
                    gobject.TYPE_NONE,
                    ())
gobject.signal_new ("feature-added", Player,
                    gobject.SIGNAL_RUN_LAST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_STRING,))


class ArtLoaderThread (threading.Thread):
    """
    Thread used to load album art from a (possibly remote) URL.

    This is done in a separate thread to avoid blocking the GUI, whether
    because the art URL is non-local or if the art file is large and takes
    a nontrivial amount of time to load.
    """

    PURGE_INTERVAL = 20

    from panflute.util import log


    def __init__ (self, player, queue):
        threading.Thread.__init__ (self, name = "Art Loader")
        self.__player = player
        self.__queue = queue
        self.__opener = Opener ()
        self.__count = 0


    def run (self):
        while True:
            if self.__count % self.PURGE_INTERVAL == 0:
                # Prevent temporary files from accumulating
                self.log.debug ("Purging temporary files")
                self.__opener.cleanup ()

            # Skip any backlog.
            pair = self.__queue.get ()
            while not self.__queue.empty ():
                self.log.debug ("Skipping {0} -- backlog".format (pair))
                pair = self.__queue.get ()

            self.log.debug ("Got new art URL pair {0}".format (pair))
            if pair == "":
                break

            [location, url] = pair.split (" ")
            if url != "-":
                try:
                    name, headers = self.__opener.retrieve (url)
                    pixbuf = gtk.gdk.pixbuf_new_from_file (name)
                    if self.__queue.empty ():
                        gobject.idle_add (lambda: self.__set_art (location, name, pixbuf))
                    else:
                        self.log.debug ("Discarding {0}; already out of date".format (name))
                    self.__count += 1
                except Exception, e:
                    self.log.warn ("Loading {0} failed: {1}".format (url, e))
            else:
                gobject.idle_add (lambda: self.__set_art (location, None, None))

        self.log.debug ("Terminating Art Loader thread")
        self.__opener.cleanup ()


    def __set_art (self, location, name, pixbuf):
        """
        Set the new art for the player.

        Done in a separate function to allow it to be run in the GUI thread.
        """

        if self.__player.props.location == location:
            self.log.debug ("Showing art from file {0} for song {1}".format (name, location))
            self.__player._set_property ("art-file", name)
            self.__player._set_property ("art", pixbuf)
        else:
            self.log.debug ("Discarding art; different song is now playing")
        return False


class Opener (urllib.FancyURLopener):
    """
    URL opener that never tries to ask the user for authentication, in the
    unlikely event a remote site tries to do that.
    """

    version = "Panflute/{0}".format (panflute.defs.VERSION)

    def prompt_user_passwd (self, host, realm):
        return (None, None)
