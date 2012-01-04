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
Interface translator for Exaile 0.3.x.
"""

from __future__ import absolute_import, division

import panflute.daemon.passthrough

import dbus


class Connector (panflute.daemon.passthrough.Connector):
    """
    Connection manager for Exaile 0.3.x.
    """

    def __init__ (self):
        panflute.daemon.passthrough.Connector.__init__ (self, "exaile", "Exaile",
                                                        "exaile")
        self.props.icon_name = "exaile"


    def launch (self):
        """
        Let the MultiConnector worry about falling back.
        """

        return self.launch_via_dbus ()


    def player (self, **kwargs):
        return Player (**kwargs)


class Player (panflute.daemon.passthrough.Player):
    """
    Player object for Exaile 0.3.x.

    Since the metadata provided via Exaile's MPRIS interface is incomplete,
    this class augments it with metadata fetched from its other, native
    interface.  The metadata cache is used to combine the two sources.  The
    native interface is also used to set ratings.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        # Ew, hack, but callbacks that run in the parent constructor may try
        # to invoke __exaile, so...
        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.exaile.Exaile", "/org/exaile/Exaile")
        self.__exaile = dbus.Interface (proxy, "org.exaile.Exaile")

        # *Now* construct properly
        panflute.daemon.passthrough.Player.__init__ (self, "exaile", True, **kwargs)
        self.__last_loc = None

        self.__exaile.GetVersion (reply_handler = self.__get_version_cb,
                                  error_handler = self.log.warn)


    def __get_version_cb (self, version_string):
        """
        Setting ratings only works in Exaile 0.3.1 and later.
        """

        version = [int(x) for x in version_string.split (".")]
        if version >= [0, 3, 1]:
            self.register_feature ("SetMetadata")
            self.register_feature ("SetMetadata:rating")


    def do_StatusChange (self, status):
        """
        Exaile 0.3.x doesn't reliably report status via the StatusChange
        signal, sometimes reporting it's stopped when it's playing a
        stream.  Double-check with a more reliable function.
        """

        self.log.debug ("signalled status {0}".format (status))
        cleaned = list (status)     # dbus.Struct object is read-only
        if cleaned[panflute.mpris.STATUS_STATE] == panflute.mpris.STATE_STOPPED:
            if self.__exaile.IsPlaying ():
                self.log.debug ("correcting status; playing a stream")
                cleaned[panflute.mpris.STATUS_STATE] = panflute.mpris.STATE_PLAYING
        panflute.daemon.passthrough.Player.do_StatusChange (self, cleaned)


    def do_GetMetadata (self):
        """
        Cache the newly fetched metadata and begin retrieving the values that
        Exaile doesn't report via MPRIS.
        """

        # Setting the cache will invoke do_TrackChange automatically.
        metadata = panflute.daemon.passthrough.Player.do_GetMetadata (self)
        self.log.debug ("got metadata: {0}".format (metadata))
        rating = self.__exaile.GetTrackAttr ("__rating")
        if rating is not None and rating != "" and rating != "None":
            metadata["rating"] = self.__rescale_rating_from_exaile (rating)
        self.cached_metadata = metadata
        return self.cached_metadata


    def do_SetMetadata (self, name, value):
        if name == "rating":
            # Exaile stores ratings on a scale of 0.0 to 100.0
            self.__exaile.SetTrackAttr ("__rating", self.__rescale_rating_to_exaile (value))
            self.cached_metadata["rating"] = value


    def do_TrackChange (self, metadata):
        """
        Update the cached metadata and start fetching additional information
        not provided via Exaile's MPRIS interface.
        """

        self.log.debug ("track changed: {0}".format (metadata))

        # There are two ways this could be called: in response to a TrackChange
        # from Exaile, in which case the metadata object itself has changed and
        # needs to be re-cached; or the existing metadata has been augmented by
        # this very class.  Only in the first case is special processing
        # necessary.

        if self.cached_metadata != metadata:
            # No need to call the parent's do_TrackChange, since setting
            # cached_metadata has the side effect of calling us again, at which
            # time the other branch of the if will be executed.
            self.cached_metadata = self._normalize_metadata (metadata)

            if self.cached_metadata.get ("location", self.__last_loc) != self.__last_loc:
                self.__last_loc = self.cached_metadata["location"]
                if self.cached_metadata.get ("mtime", 0) <= 0:
                    self.__exaile.GetTrackAttr ("__length",
                                                reply_handler = self.__get_attr_length_cb,
                                                error_handler = self.log.warn)
                if not self.cached_metadata.has_key ("rating"):
                    self.log.debug ("calling GetTrackAttr('__rating')")
                    self.__exaile.GetTrackAttr ("__rating",
                                                reply_handler = self.__get_attr_rating_cb,
                                                error_handler = self.log.warn)
                else:
                    self.log.debug ("Not fetching rating; cached rating is {0}".format (
                        self.cached_metadata.has_key ("rating")))
        else:
            panflute.daemon.passthrough.Player.do_TrackChange (self, metadata)


    def __get_attr_length_cb (self, length = "0.0"):
        """
        Add the length of the song to the cached metadata.
        """

        # Exaile returns nothing -- not an empty string, actually nothing -- if
        # the song is a stream.  Thus the default value for rating is needed
        # to prevent a not-enough-arguments error in this case.

        self.log.debug ("Exaile reports length of {0}".format (length))

        msec = int (float (length) * 1000)
        sec = msec // 1000

        self.cached_metadata["mtime"] = msec
        self.cached_metadata["time"] = sec


    def __get_attr_rating_cb (self, rating = "0.0"):
        """
        Add the rating of the song to the cached metadata.
        """

        # Exaile returns nothing -- not an empty string, actually nothing -- if
        # the song has no rating.  Thus the default value for rating is needed
        # to prevent a not-enough-arguments error in this case.

        self.log.debug ("Exaile reports rating of {0}".format (rating))
        self.cached_metadata["rating"] = self.__rescale_rating_from_exaile (rating)


    def __rescale_rating_from_exaile (self, rating):
        """
        Convert an Exaile-reported rating to a standard rating.
        """

        if rating is not None and rating != "" and rating != "None":
            return int (float (rating) / 20.0)
        else:
            return 0.0


    def __rescale_rating_to_exaile (self, rating):
        """
        Convert a standard rating to an Exaile-reported rating.
        """

        return rating * 20.0


    def _normalize_metadata (self, metadata):
        # Exaile 0.3.1b sometimes sets mtime to 0 despite setting time to the
        # proper value, so fix that.
        if metadata is not None and metadata != {}:
            if metadata.get ("time", 0) > 0 and metadata.get ("mtime", 0) <= 0:
                metadata["mtime"] = metadata["time"] * 1000
        return panflute.daemon.passthrough.Player._normalize_metadata (self, metadata)
