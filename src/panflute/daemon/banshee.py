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
Interface translator for Banshee.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import dbus
import os
import os.path
import re
import subprocess


class Connector (panflute.daemon.connector.DBusConnector):
    """
    Connection manager for Banshee.
    """

    def __init__ (self):
        panflute.daemon.connector.DBusConnector.__init__ (self, "banshee", "Banshee",
                                                          "org.bansheeproject.Banshee")
        self.props.icon_name = "media-player-banshee"


    def root (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.Root ("Banshee", **kwargs)


    def track_list (self, **kwargs):
        # TODO: The real thing
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (**kwargs)


    def launch (self):
        # Don't launch Banshee via D-Bus, because it has problems with radio
        # streams when launched like that.  See lp:535479 and
        # https://bugzilla.mate.org/show_bug.cgi?id=612658

        return self.launch_via_command ()


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for Banshee.
    """

    from panflute.util import log

    REPEAT_NONE = 0
    REPEAT_ALL = 1
    REPEAT_SINGLE = 2

    SHUFFLE_OFF = 0
    SHUFFLE_BY_SONG = 1
    SHUFFLE_BY_ARTIST = 2   # XXX: verify this
    SHUFFLE_BY_ALBUM = 3    # XXX: verify this


    def __init__ (self, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetMetadata", "GetStatus",
                        "Next", "Prev", "Pause", "Stop", "Play", "Repeat",
                        "PositionGet", "PositionSet", "VolumeGet", "VolumeSet"]:
            self.register_feature (feature)

        bus = dbus.SessionBus ()
        proxy = bus.get_object ("org.bansheeproject.Banshee", "/org/bansheeproject/Banshee/PlaybackController")
        self.__playback = dbus.Interface (proxy, "org.bansheeproject.Banshee.PlaybackController")

        proxy = bus.get_object ("org.bansheeproject.Banshee", "/org/bansheeproject/Banshee/PlayerEngine")
        self.__engine = dbus.Interface (proxy, "org.bansheeproject.Banshee.PlayerEngine")

        proxy = bus.get_object ("org.freedesktop.DBus", "/")
        bus_obj = dbus.Interface (proxy, "org.freedesktop.DBus")

        # Try to figure out what version of Banshee is running, the hard way.
        bus_obj.GetConnectionUnixProcessID ("org.bansheeproject.Banshee",
                                            reply_handler = self.__get_pid_cb,
                                            error_handler = self.log.warn)

        self.__handlers = [
            self.__engine.connect_to_signal ("EventChanged", self.__event_changed_cb)
        ]

        self.cached_caps.go_next = True
        self.cached_caps.go_prev = True
        self.cached_caps.play = True

        self.__engine.GetCurrentTrack (reply_handler = self.__get_current_track_cb,
                                       error_handler = self.log.warn)
        self.__fetch_status ()
        self.__fetch_caps ()


    def remove_from_connection (self):
        for handler in self.__handlers:
            handler.remove ()
        self.__handlers = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Next (self):
        self.__playback.Next (True,
                              reply_handler = lambda: None,
                              error_handler = self.log.warn)


    def do_Prev (self):
        self.__playback.Previous (True,
                                  reply_handler = lambda: None,
                                  error_handler = self.log.warn)


    def do_Pause (self):
        self.__engine.TogglePlaying (reply_handler = lambda: None,
                                     error_handler = self.log.warn)


    def do_Stop (self):
        self.__engine.Close (reply_handler = lambda: None,
                             error_handler = self.log.warn)


    def do_Play (self):
        self.__engine.Play (reply_handler = lambda: None,
                            error_handler = self.log.warn)


    def do_Repeat (self, repeat):
        if repeat:
            mode = self.REPEAT_SINGLE
        else:
            mode = self.REPEAT_NONE
        self.__playback.SetRepeatMode (mode,
                                       reply_handler = lambda: None,
                                       error_handler = self.log.warn)


    def do_SetMetadata (self, name, value):
        if name == "rating":
            # SetRating added in Banshee 1.5.3
            self.__engine.SetRating (dbus.Byte (value),
                                     reply_handler = lambda: None,
                                     error_handler = self.log.warn)
            self.cached_metadata["rating"] = value
        else:
            self.log.warn ("Don't know how to set {0} to {1}".format (name, value))


    def do_PositionGet (self):
        return self.__engine.GetPosition ()


    def do_PositionSet (self, position):
        self.__engine.SetPosition (dbus.UInt32 (position),
                                   reply_handler = lambda: None,
                                   error_handler = self.log.warn)


    def do_VolumeGet (self):
        return self.__engine.GetVolume ()


    def do_VolumeSet (self, volume):
        self.__engine.SetVolume (dbus.UInt16 (volume),
                                 reply_handler = lambda: None,
                                 error_handler = self.log.warn)


    def __event_changed_cb (self, event, message, buffering_percent):
        """
        If song information changed, fetch it.
        """

        self.log.debug ("EventChanged: event=\"{0}\" message=\"{1}\" buffering_percent=\"{2}\"".format (
            event, message, buffering_percent))

        if event == "startofstream" or event == "trackinfoupdated":
            self.__engine.GetCurrentTrack (reply_handler = self.__get_current_track_cb,
                                           error_handler = self.log.warn)
            self.__fetch_caps ()
        elif event == "endofstream":
            self.cached_metadata = {}
            self.cached_caps.pause = False
            self.cached_caps.seek = False
        elif event == "statechange":
            self.__fetch_status ()


    def __get_current_track_cb (self, info):
        """
        Convert Banshee-reported metadata into MPRIS-style metadata and cache it.
        """

        metadata = {}

        if info.has_key ("URI"):
            metadata["location"] = info["URI"]
        if info.has_key ("name"):
            metadata["title"] = info["name"]
        if info.has_key ("artist") and info["artist"] != "Unknown Artist":
            metadata["artist"] = info["artist"]
        if info.has_key ("album") and info["album"] != "Unknown Album":
            metadata["album"] = info["album"]
        if info.has_key ("track-number"):
            metadata["tracknumber"] = info["track-number"]
        if info.has_key ("length"):
            metadata["mtime"] = info["length"] * 1000
            metadata["time"] = info["length"]
        if info.has_key ("genre"):
            metadata["genre"] = info["genre"]
        if info.has_key ("rating"):
            metadata["rating"] = info["rating"]
            metadata["panflute rating scale"] = 5
        if info.has_key ("year"):
            metadata["year"] = info["year"]
        if info.has_key ("artwork-id"):
            # Sometime around Banshee 1.6.0, the directory changed from album-art to
            # media-art.  Return whichever one actually exists.
            filenames = [os.path.expanduser (n.format (info["artwork-id"])) for n in
                    ["~/.cache/media-art/{0}.jpg", "~/.cache/album-art/{0}.jpg"]]
            for filename in filenames:
                if os.access (filename, os.R_OK):
                    metadata["arturl"] = panflute.util.make_url (filename)
                    break
        if info.has_key ("bit-rate"):
            metadata["audio-bitrate"] = info["bit-rate"]

        self.cached_metadata = metadata


    def __fetch_status (self):
        """
        Fetch each of the components of the MPRIS status four-tuple and cache
        them.  Rely on the underlying caching mechanism to put the values
        together into the four-tuple as the results come in.
        """

        self.__engine.GetCurrentState (reply_handler = self.__get_current_state_cb,
                                       error_handler = self.log.warn)
        self.__playback.GetShuffleMode (reply_handler = self.__get_shuffle_mode_cb,
                                        error_handler = self.log.warn)
        self.__playback.GetRepeatMode (reply_handler = self.__get_repeat_mode_cb,
                                       error_handler = self.log.warn)


    def __get_current_state_cb (self, state_name):
        """
        Update the cached status four-tuple with the current state.
        """

        state_table = { "playing": panflute.mpris.STATE_PLAYING,
                        "paused":  panflute.mpris.STATE_PAUSED,
                        "idle":    panflute.mpris.STATE_STOPPED
                      }
        if state_table.has_key (state_name):
            self.cached_status.state = state_table[state_name]
            if self.cached_status.state == panflute.mpris.STATE_PLAYING:
                self.start_polling_for_time ()
            else:
                self.stop_polling_for_time ()
        else:
            self.log.warn ("Unrecognized state \"{0}\"".format (state_name))


    def __get_shuffle_mode_cb (self, shuffle_mode):
        """
        Update the cached status four-tuple with the shuffle mode.
        """

        if shuffle_mode == self.SHUFFLE_OFF:
            self.cached_status.order = panflute.mpris.ORDER_LINEAR
        else:
            self.cached_status.order = panflute.mpris.ORDER_RANDOM


    def __get_repeat_mode_cb (self, repeat_mode):
        """
        Update the next-song and stop-when-done components of the cached
        status four-tuple.

        Note that although Banshee provides a StopWhenFinished property, that
        refers to whether Banshee will stop after the current song finishes.
        The stop-when-done field in the MPRIS status four-tuple is about
        whether the player will stop at the end of the playlist.  Banshee's
        repeat mode provides both these values.
        """

        if repeat_mode == self.REPEAT_NONE:
            self.cached_status.next = panflute.mpris.NEXT_NEXT
            self.cached_status.future = panflute.mpris.FUTURE_STOP
        elif repeat_mode == self.REPEAT_ALL:
            self.cached_status.next = panflute.mpris.NEXT_NEXT
            self.cached_status.future = panflute.mpris.FUTURE_CONTINUE
        elif repeat_mode == self.REPEAT_SINGLE:
            self.cached_status.next = panflute.mpris.NEXT_REPEAT
            self.cached_status.future = panflute.mpris.FUTURE_CONTINUE
        else:
            self.log.warn ("Unrecognized repeat mode {0}".format (repeat_mode))


    def __fetch_caps (self):
        """
        Fetch each of the capabilities flags offered by Banshee and update
        the set of cached capabilities accordingly.
        """

        self.__engine.GetCanPause (reply_handler = self.cached_caps.bit_set_func (panflute.mpris.CAN_PAUSE),
                                   error_handler = self.log.warn)
        self.__engine.GetCanSeek (reply_handler = self.cached_caps.bit_set_func (panflute.mpris.CAN_SEEK),
                                  error_handler = self.log.warn)


    def __get_pid_cb (self, pid):
        """
        Detect the Banshee version by invoking it with --version, since it
        doesn't expose its version number via D-Bus and that's what we need
        to know to determine if it supports setting ratings or not.
        """

        try:
            # XXX: This is probably Linux-specific
            with file ("/proc/{0}/cmdline".format (pid), "r") as f:
                # Find out how to invoke Banshee, dropping any extra arguments.
                args = []
                for piece in f.readline ().split ("\x00"):
                    args.append (piece)
                    if piece.endswith (".exe"):
                        break
                args.append ("--version")

                # If args[0] isn't absolute, invoke the mono interpreter
                # directly, which had a better chance of working when Banshee
                # isn't installed under the default path.
                if not args[0].startswith ("/"):
                    args[0] = "mono"

                # Invoke Banshee and extract the version number.
                with file ("/dev/null", "r+") as null:
                    proc = subprocess.Popen (args, close_fds = True, preexec_fn = os.setsid,
                                             stdin = null, stdout = subprocess.PIPE, stderr = null)
                    out, err = proc.communicate ()
                    match = re.search (r"\(([\d.]+)\)", out)
                    if match:
                        version = [int (n) for n in match.group (1).split (".")]
                        if version >= [1, 5, 3]:
                            self.register_feature ("SetMetadata")
                            self.register_feature ("SetMetadata:rating")
        except Exception, e:
            self.log.warn ("Version detection failed: {0}".format (e))
            pass
