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
Base classes for the MPRIS objects exposed by Panflute.

All method implementations default to do-nothing behavior.  Player-specific
subclasses should implement the appropriate functionality by translating
the MPRIS protocol into whatever interface that player uses.

Subclasses should not override the MPRIS method themselves, but rather the
do_* versions of them.  This allows logging and error handling to be
handled entirely by the base class.

See http://wiki.xmms2.xmms.se/wiki/MPRIS for full documentation of the
interfaces being implemented here.

Some extension methods and signals are also provided for functionality
not available through the MPRIS standard.  These additional features are
offered through the same objects, but a different interface.
"""

from __future__ import absolute_import

import panflute.defs
import panflute.mpris

import dbus.service
import gobject
import sys


PANFLUTE_INTERFACE = "org.kuliniewicz.Panflute"


##############################################################################


class Root (dbus.service.Object):
    """
    The MPRIS object located at /, providing basic information about the
    music player itself.
    """

    from panflute.util import log


    def __init__ (self, name, **kwargs):
        # TODO: Get the name and version from the configure script.
        dbus.service.Object.__init__ (self, **kwargs)
        self.__name = "Panflute {0} / {1}".format (panflute.defs.VERSION, name)


    # Identity method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "s")
    def Identity (self):
        self.log.debug ("Identity")
        return self.__name


    # Quit method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Quit (self):
        self.log.debug ("Quit")
        self.do_Quit ()

    def do_Quit (self):
        pass


    # MprisVersion method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "(qq)")
    def MprisVersion (self):
        self.log.debug ("MprisVersion")
        return self.do_MprisVersion ()

    def do_MprisVersion (self):
        return (1, 0)


##############################################################################


class TrackList (dbus.service.Object):
    """
    The MPRIS object located at /TrackList, providing access to the music
    player's list of tracks being played.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        dbus.service.Object.__init__ (self, **kwargs)


    # GetMetadata method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "i",
                          out_signature = "a{sv}")
    def GetMetadata (self, index):
        self.log.debug ("GetMetadata {0}".format (index))
        if index < 0:
            raise ValueError ("index must be >= 0")
        return self.do_GetMetadata (index)

    def do_GetMetadata (self, index):
        return {}


    # GetCurrentTrack method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "i")
    def GetCurrentTrack (self):
        self.log.debug ("GetCurrentTrack")
        return self.do_GetCurrentTrack ()

    def do_GetCurrentTrack (self):
        return -1


    # GetLength method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "i")
    def GetLength (self):
        self.log.debug ("GetLength")
        length = self.do_GetLength ()
        assert length >= 0
        return length

    def do_GetLength (self):
        return 0


    # AddTrack method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "sb",
                          out_signature = "i")
    def AddTrack (self, uri, play_immediately):
        self.log.debug ("AddTrack {0} {1}".format (uri, play_immediately))
        return self.do_AddTrack (uri, play_immediately)

    def do_AddTrack (self, uri, play_immediately):
        return -1


    # DelTrack method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "i",
                          out_signature = "")
    def DelTrack (self, index):
        self.log.debug ("DelTrack {0}".format (index))
        if index < 0:
            raise ValueError ("index must be >= 0")
        self.do_DelTrack ()

    def do_DelTrack (self, index):
        pass


    # SetLoop method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "b",
                          out_signature = "")
    def SetLoop (self, loop):
        self.log.debug ("SetLoop {0}".format (loop))
        self.do_SetLoop (loop)

    def do_SetLoop (self, loop):
        pass


    # SetRandom method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "b",
                          out_signature = "")
    def SetRandom (self, shuffle):
        self.log.debug ("SetRandom {0}".format (shuffle))
        self.do_SetRandom (shuffle)

    def do_SetRandom (self, shuffle):
        pass


    # TrackListChange signal

    @dbus.service.signal (dbus_interface = panflute.mpris.INTERFACE,
                          signature = "i")
    def TrackListChange (self, length):
        self.log.debug ("sending TrackListChange {0}".format (length))
        assert length >= 0

    def do_TrackListChange (self, length):
        self.TrackListChange (length)


##############################################################################


class Player (dbus.service.Object):
    """
    The MPRIS object located at /Player, providing access to playback controls
    and current status.

    This class offers a cache of various status values, which subclasses may
    set at will.  The cache manipulation methods will automatically fire the
    appropriate signals, and the default implementations of the corresponding
    Get functions will read from the cache.  Subclasses are free to disregard
    the cache and implement the functionality themselves if they wish.
    """

    from panflute.util import log


    def __init__ (self, **kwargs):
        dbus.service.Object.__init__ (self, **kwargs)

        # Built-in features are always available.
        self.__features = ["GetFeatures", "Supports",
                           "CapsChange", "StatusChange", "TrackChange", "PositionChange"]

        self.__polling = False
        self.__poll_source = None

        self.__cached_status = CachedStatus (self,
                                             panflute.mpris.STATE_STOPPED,
                                             panflute.mpris.ORDER_LINEAR,
                                             panflute.mpris.NEXT_NEXT,
                                             panflute.mpris.FUTURE_CONTINUE)
        self.__cached_metadata = CachedMetadata (self)
        self.__cached_caps = CachedCaps (self, panflute.mpris.CAN_DO_NOTHING)

    def remove_from_connection (self):
        self.stop_polling_for_time ()
        dbus.service.Object.remove_from_connection (self)


    # Next method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Next (self):
        self.log.debug ("Next")
        self.do_Next ()

    def do_Next (self):
        pass


    # Prev method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Prev (self):
        self.log.debug ("Prev")
        self.do_Prev ()

    def do_Prev (self):
        pass


    # Pause method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Pause (self):
        self.log.debug ("Pause")
        self.do_Pause ()

    def do_Pause (self):
        pass


    # Stop method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Stop (self):
        self.log.debug ("Stop")
        self.do_Stop ()

    def do_Stop (self):
        pass


    # Play method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "")
    def Play (self):
        self.log.debug ("Play")
        self.do_Play ()

    def do_Play (self):
        pass


    # Repeat method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "b",
                          out_signature = "")
    def Repeat (self, repeat):
        self.log.debug ("Repeat {0}".format (repeat))
        self.do_Repeat (repeat)

    def do_Repeat (self, repeat):
        pass


    # GetStatus method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "(iiii)")
    def GetStatus (self):
        self.log.debug ("GetStatus")
        status = self.do_GetStatus ()
        self.__assert_valid_status (status)
        return status

    def do_GetStatus (self):
        """
        By default, serve the value out of the cache.
        """

        return self.__cached_status.tuple

    def __assert_valid_status (self, status):
        """
        Assert that a status vector complies with the MPRIS spec.
        """

        (state, order, next, future) = status
        assert state >= panflute.mpris.STATE_MIN and state <= panflute.mpris.STATE_MAX
        assert order >= panflute.mpris.ORDER_MIN and order <= panflute.mpris.ORDER_MAX
        assert next >= panflute.mpris.NEXT_MIN and next <= panflute.mpris.NEXT_MAX
        assert future >= panflute.mpris.FUTURE_MIN and future <= panflute.mpris.FUTURE_MAX


    # GetMetadata method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "a{sv}")
    def GetMetadata (self):
        self.log.debug ("GetMetadata")
        return self.do_GetMetadata ()

    def do_GetMetadata (self):
        return self.__cached_metadata


    # SetMetadata extension method

    @dbus.service.method (dbus_interface = PANFLUTE_INTERFACE,
                          in_signature = "sv",
                          out_signature = "")
    def SetMetadata (self, name, value):
        """
        Set a metadata field for the current song.  Not all fields will
        necessarily be settable.

        This could be used for setting a song's rating -- MPRIS's GetMetadata
        provides a way to *see* ratings, but no way to change them.
        """

        self.log.debug ("SetMetadata")
        self.do_SetMetadata (name, value)

    def do_SetMetadata (self, name, value):
        pass


    # GetCaps method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "i")
    def GetCaps (self):
        self.log.debug ("GetCaps")
        caps = self.do_GetCaps ()
        self.__assert_valid_caps (caps)
        return caps

    def do_GetCaps (self):
        return self.cached_caps.all

    def __assert_valid_caps (self, caps):
        """
        Assert that a set of caps flags complies with the MPRIS spec.
        """

        assert (caps & ~panflute.mpris.CAPABILITY_MASK) == 0


    # VolumeSet method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "i",
                          out_signature = "")
    def VolumeSet (self, volume):
        self.log.debug ("VolumeSet {0}".format (volume))
        if volume < panflute.mpris.VOLUME_MIN or volume > panflute.mpris.VOLUME_MAX:
            raise ValueError ("volume must be between {0} and {1}".format (panflute.mpris.VOLUME_MIN,
                                                                           panflute.mpris.VOLUME_MAX))
        self.do_VolumeSet (volume)

    def do_VolumeSet (self, volume):
        pass


    # VolumeGet method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "i")
    def VolumeGet (self):
        self.log.debug ("VolumeGet")
        volume = self.do_VolumeGet ()
        assert volume >= panflute.mpris.VOLUME_MIN and volume <= panflute.mpris.VOLUME_MAX
        return volume

    def do_VolumeGet (self):
        return panflute.mpris.VOLUME_MIN


    # PositionSet method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "i",
                          out_signature = "")
    def PositionSet (self, position):
        self.log.debug ("PositionSet {0}".format (position))
        if position < 0:
            raise ValueError ("position must be >= 0")
        self.do_PositionSet (position)

    def do_PositionSet (self, position):
        pass


    # PositionGet method

    @dbus.service.method (dbus_interface = panflute.mpris.INTERFACE,
                          in_signature = "",
                          out_signature = "i")
    def PositionGet (self):
        self.log.debug ("PositionGet")
        position = self.do_PositionGet ()
        assert position >= 0
        return position

    def do_PositionGet (self):
        return 0


    # Features extension method
    # Returns a list of all Player features supported by the current
    # player.  This list should not change for the lifetime of the
    # object.  Features are not returned in any particular order.

    @dbus.service.method (dbus_interface = PANFLUTE_INTERFACE,
                          in_signature = "",
                          out_signature = "as")
    def GetFeatures (self):
        self.log.debug ("GetFeatures")
        return self.do_GetFeatures ()

    def do_GetFeatures (self):
        return self.__features


    def register_feature (self, feature):
        """
        Register a feature to be returned by GetFeatures and Supports.  All
        features should be registered as soon as possible when initializing
        the Player object.
        """

        self.__features.append (feature)
        self.do_FeatureAdded (feature)


    # Supports extension method
    # Returns true if a specific feature (listed by GetFeatures) is supported.
    # This is primarily a convenience if only one or two features are of
    # interest, to avoid having to pull the entire list.
    
    @dbus.service.method (dbus_interface = PANFLUTE_INTERFACE,
                          in_signature = "s",
                          out_signature = "b")
    def Supports (self, feature):
        self.log.debug ("Supports ({0})".format (feature))
        return self.do_Supports (feature)

    def do_Supports (self, feature):
        return feature in self.__features


    # FeatureAdded extension signal
    # Indicates that a feature has been added to the list of available ones,
    # presumably a feature whose detection couldn't be done immediately.

    @dbus.service.signal (dbus_interface = PANFLUTE_INTERFACE,
                          signature = "s")
    def FeatureAdded (self, feature):
        self.log.debug ("sending FeatureAdded {0}".format (feature))

    def do_FeatureAdded (self, feature):
        self.FeatureAdded (feature)


    # TrackChange signal

    @dbus.service.signal (dbus_interface = panflute.mpris.INTERFACE,
                          signature = "a{sv}")
    def TrackChange (self, metadata):
        self.log.debug ("sending TrackChange {0}".format (metadata))

    def do_TrackChange (self, metadata):
        self.TrackChange (metadata)


    # StatusChange signal

    @dbus.service.signal (dbus_interface = panflute.mpris.INTERFACE,
                          signature = "(iiii)")
    def StatusChange (self, status):
        self.log.debug ("sending StatusChange {0}".format (status))
        self.__assert_valid_status (status)

    def do_StatusChange (self, status):
        self.StatusChange (status)


    # CapsChange signal

    @dbus.service.signal (dbus_interface = panflute.mpris.INTERFACE,
                          signature = "i")
    def CapsChange (self, caps):
        self.log.debug ("sending CapsChange {0}".format (hex (caps)))
        self.__assert_valid_caps (caps)

    def do_CapsChange (self, caps):
        self.CapsChange (caps)


    # PositionChange extension signal
    @dbus.service.signal (dbus_interface = PANFLUTE_INTERFACE,
                          signature = "i")
    def PositionChange (self, position):
        """
        Signal sent whenever the current position within the song changes.

        Although time is reported in milliseconds, this signal almost certainly
        won't be sent 1,000 times a second.  However, it ought to be sent
        roughly once a second, to allow clients to update an elapsed-time
        display without having to implement their own polling loop.
        """
        self.log.debug ("sending PositionChange {0}".format (position))
        assert position >= 0

    def do_PositionChange (self, position):
        self.PositionChange (position)


    # status cache

    @property
    def cached_status (self):
        """
        Get the currently cached status.  The returned object is monitored
        for changes.
        """

        return self.__cached_status

    @cached_status.setter
    def cached_status (self, status):
        """
        Completely change the cached status, sending signals as appropriate.
        """

        new_status = CachedStatus (self, status[panflute.mpris.STATUS_STATE],
                                         status[panflute.mpris.STATUS_ORDER],
                                         status[panflute.mpris.STATUS_NEXT],
                                         status[panflute.mpris.STATUS_FUTURE])
        if self.__cached_status.tuple != new_status.tuple:
            self.__cached_status = new_status
            self.do_StatusChange (new_status.tuple)


    # metadata cache

    @property
    def cached_metadata (self):
        """
        Get the currently cached metadata.  The returned object is monitored
        for changes.
        """

        return self.__cached_metadata

    @cached_metadata.setter
    def cached_metadata (self, metadata):
        """
        Completely change the cached metadata, sending signals as appropriate.
        """

        new_metadata = CachedMetadata (self, metadata)
        if self.__cached_metadata != new_metadata:
            self.__cached_metadata = new_metadata
            self.do_TrackChange (new_metadata)


    # caps cache

    @property
    def cached_caps (self):
        """
        Get the currently cached capabilities.  The properties on the
        returned object are monitored for changes.
        """

        return self.__cached_caps


    # polling for elapsed time updates

    def start_polling_for_time (self):
        """
        Begin polling for elapsed time updates.
        """

        if not self.__polling:
            self.__polling = True
            self.__poll_for_time ()


    def stop_polling_for_time (self):
        """
        Stop polling for elapsed time updates.
        """

        self.__polling = False
        if self.__poll_source is not None:
            gobject.source_remove (self.__poll_source)
            self.__poll_source = None


    def __poll_for_time (self):
        """
        Call the PositionGet method directly, report it, and queue another
        call to this function when the next second is expected to tick.
        """

        elapsed = self.PositionGet ()
        self.do_PositionChange (elapsed)

        if self.__polling:
            # Poll when the next second tick is expected, but don't poll more
            # frequently than four times a second.
            delay = max (250, 1000 - (elapsed % 1000))
            self.__poll_source = gobject.timeout_add (delay, self.__poll_for_time)

        return False


##############################################################################


def sanitize_string (value):
    """
    Convert a string, silently replacing empty strings with None so they
    get removed from the metadata entirely.
    """

    if value is None or value == "":
        return None
    else:
        return unicode (value)


class CachedMetadata (dict):
    """
    Intelligent dict used for implementing the metadata cache.  Setting a
    key after construction will trigger a TrackChange signal from the
    owning Player object.  It will also enforce that values associated with
    keys recommended in the MPRIS spec are of the correct type.

    The end result is an object that player implementations can simply
    update as they wish, with all the necessary MPRIS stuff happening
    automatically.
    """

    from panflute.util import log

    CONVERSIONS = {
        "location":                  sanitize_string,
        "title":                     sanitize_string,
        "artist":                    sanitize_string,
        "album":                     sanitize_string,
        "tracknumber":               sanitize_string,
        "time":                      int,
        "mtime":                     int,
        "genre":                     sanitize_string,
        "comment":                   sanitize_string,
        "rating":                    int,
        "panflute rating scale":     int,
        "year":                      int,
        "date":                      int,
        "arturl":                    sanitize_string,
        "asin":                      sanitize_string,
        "puid fingerprint":          sanitize_string,
        "mb track id":               sanitize_string,
        "mb artist id":              sanitize_string,
        "mb artist sort name":       sanitize_string,
        "mb album id":               sanitize_string,
        "mb release date":           sanitize_string,
        "mb album artist":           sanitize_string,
        "mb album artist id":        sanitize_string,
        "mb album artist sort name": sanitize_string,
        "audio-bitrate":             int,
        "audio-samplerate":          int,
        "video-bitrate":             int
    }


    def __init__ (self, player, initial_values = {}):
        dict.__init__ (self)

        # Note that __player is set *after* populating with the initial values,
        # since construction doesn't count as a change!

        self.__player = None
        for key in initial_values:
            self[key] = initial_values[key]
        self.__player = player


    def __setitem__ (self, key, value):
        """
        Convert the value to the type recommended by MPRIS, and trigger a
        TrackChange signal if needed.
        """

        conversion = self.CONVERSIONS.get (key, lambda x: x)
        try:
            clean_value = conversion (value)
        except Exception, e:
            self.log.warn ("Failed to clean up metadata '{0}' => '{1}".format (key, value))
            clean_value = None

        if clean_value is None:
            del self[key]
        elif self.get (key, None) != clean_value:
            dict.__setitem__ (self, key, clean_value)
            if self.__player is not None:
                self.__player.do_TrackChange (self)


    def __delitem__ (self, key):
        """
        Remove a key/value pair, triggering a TrackChange signal if needed.
        """

        if self.has_key (key):
            dict.__delitem__ (self, key)
            if self.__player is not None:
                self.__player.do_TrackChange ()


##############################################################################


class CachedStatus (object):
    """
    A cached copy of the MPRIS status four-tuple, providing an easier way to
    get and set the various components of the status value.  When values
    actually change, a TrackChange signal will be triggered from the owning
    Player object.
    """


    def __init__ (self, player, state, order, next, future):
        # Populate the actual data using the setters so that the assertions
        # get run against the initial values.

        self.__state = None
        self.__order = None
        self.__next = None
        self.__future = None
        self.__player = None

        self.state = state
        self.order = order
        self.next = next
        self.future = future
        self.__player = player


    @property
    def state (self):
        """
        Get the cached playback state.
        """

        return self.__state


    @state.setter
    def state (self, new_state):
        """
        Update the cached playback state.
        """

        assert new_state >= panflute.mpris.STATE_MIN and new_state <= panflute.mpris.STATE_MAX
        if self.__state != new_state:
            self.__state = new_state
            if self.__player is not None:
                self.__player.do_StatusChange (self.tuple)


    @property
    def order (self):
        """
        Get the cached playback order.
        """

        return self.__order


    @order.setter
    def order (self, new_order):
        """
        Update the cached playback order.
        """

        assert new_order >= panflute.mpris.ORDER_MIN and new_order <= panflute.mpris.ORDER_MAX
        if self.__order != new_order:
            self.__order = new_order
            if self.__player is not None:
                self.__player.do_StatusChange (self.tuple)


    @property
    def next (self):
        """
        Get the cached value for what will be played next.
        """

        return self.__next


    @next.setter
    def next (self, new_next):
        """
        Update the cached value for what will be played next.
        """

        assert new_next >= panflute.mpris.NEXT_MIN and new_next <= panflute.mpris.NEXT_MAX
        if self.__next != new_next:
            self.__next = new_next
            if self.__player is not None:
                self.__player.do_StatusChange (self.tuple)


    @property
    def future (self):
        """
        Get the cached value for how playback will end.
        """

        return self.__future


    @future.setter
    def future (self, new_future):
        """
        Update the cached value for how playback will end.
        """

        assert new_future >= panflute.mpris.FUTURE_MIN and new_future <= panflute.mpris.FUTURE_MAX
        if self.__future != new_future:
            self.__future = new_future
            if self.__player is not None:
                self.__player.do_StatusChange (self.tuple)


    @property
    def tuple (self):
        """
        Get the MPRIS-style four-tuple for the entire status.
        """

        return (self.__state, self.__order, self.__next, self.__future)


##############################################################################


def bit_property (mask):
    """
    Create a property with a getter/setter pair for a single bit of the
    capabilities bitmask.
    """

    def getter (self):
        return (self.all & mask) != 0

    def setter (self, value):
        if value:
            self.all |= mask
        else:
            self.all &= ~mask

    return property (getter, setter)


class CachedCaps (object):
    """
    A cached copy of the player capabilities bitmask, providing an easier way
    to get and set the various components.  When it changes, a TrackChange
    signal will be triggered from the owning Player object.
    """


    def __init__ (self, player, caps):
        # Populate the actual data using the setter so that the assertions
        # get run against the initial values.

        self.__player = None
        self.__caps = None
        self.all = caps
        self.__player = player


    @property
    def all (self):
        """
        Get the entire bitmask of capabilities.
        """

        return self.__caps


    @all.setter
    def all (self, caps):
        """
        Set the entire bitmask of capabilities.
        """

        assert (caps & ~panflute.mpris.CAPABILITY_MASK) == 0
        if self.__caps != caps:
            self.__caps = caps
            if self.__player is not None:
                self.__player.do_CapsChange (caps)


    def bit_set_func (self, mask):
        """
        Return a function that takes a boolean value and sets the given
        mask accordingly.  Helpful for creating D-Bus callbacks.
        """

        def setter (can_do_it):
            if can_do_it:
                self.all |= mask
            else:
                self.all &= ~mask

        return setter


    go_next          = bit_property (panflute.mpris.CAN_GO_NEXT)
    go_prev          = bit_property (panflute.mpris.CAN_GO_PREV)
    pause            = bit_property (panflute.mpris.CAN_PAUSE)
    play             = bit_property (panflute.mpris.CAN_PLAY)
    seek             = bit_property (panflute.mpris.CAN_SEEK)
    provide_metadata = bit_property (panflute.mpris.CAN_PROVIDE_METADATA)
    has_tracklist    = bit_property (panflute.mpris.CAN_HAS_TRACKLIST)
