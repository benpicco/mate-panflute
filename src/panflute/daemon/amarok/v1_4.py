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
Interface translator for Amarok 1.4.
"""

from __future__ import absolute_import, division

import panflute.daemon.connector
import panflute.daemon.mpris
import panflute.mpris
import panflute.util

import dcopext
import glib
import kdecore
import Queue
import sys
import threading


class Connector (panflute.daemon.connector.PollingConnector):
    """
    Connection manager for Amarok 1.4.
    """

    from panflute.util import log

    def __init__ (self):
        panflute.daemon.connector.PollingConnector.__init__ (self, "amarok", "Amarok")
        self.__thread = WorkerThread (self)
        self.__thread.start ()


    def try_connect (self):
        # Try to talk to Amarok to see if it's there
        self.__thread.enqueue ("player", "title",
                               callback = lambda unused: self.set_property ("connected", True))


    def root (self, **kwargs):
        return Root (self, self.__thread, **kwargs)


    def track_list (self, **kwargs):
        return panflute.daemon.mpris.TrackList (**kwargs)


    def player (self, **kwargs):
        return Player (self.__thread, **kwargs)


class WorkerThread (threading.Thread):
    """
    Thread used to perform DCOP initialization and function calls, with the
    results delivered back to the main thread.

    These are done in a separate thread since DCOP calls are synchronous, and
    simply creating a KApplication can take several seconds if the KDE3
    daemons aren't already running.
    """

    from panflute.util import log


    def __init__ (self, connector):
        threading.Thread.__init__ (self, name = "Amarok 1.4 thread")
        self.daemon = True
        self.__connector = connector
        self.__app = None       # __amarok won't work if __app get GC'd
        self.__amarok = None
        self.__queue = None


    def enqueue (self, obj_name, func_name, *args, **kwargs):
        """
        Queue a DCOP call, with an optional handler (callback = ...) to
        process the result.  If the call fails, the connector is told the
        connection has been lost.
        """

        if self.__queue is not None:
            func = self.__amarok[obj_name][func_name]
            callback = kwargs.get ("callback", None)
            self.__queue.put ((func, args, callback))


    def immediate (self, obj_name, func_name, *args):
        """
        Execute a DCOP call in the current thread.
        """

        return self.__amarok[obj_name][func_name] (*args)


    def run (self):
        self.__establish_connection ()
        self.__process_queue ()


    def __establish_connection (self):
        """
        Establish a DCOP connection to Amarok 1.4.
        """

        self.log.debug ("Initializing Amarok 1.4 connectivity")

        # The KApplication constructor calls exit() if it finds arguments in
        # argv that it doesn't understand, so hide everything but the program
        # name from it.

        fake_argv = sys.argv[0:1]
        self.__app = kdecore.KApplication (fake_argv, "panflute-daemon")
        self.__amarok = dcopext.DCOPApp ("amarok", self.__app.dcopClient ())
        self.log.debug ("Initialization complete")


    def __process_queue (self):
        """
        Process queued DCOP method calls and deliver the result to the
        main thread, if desired.  If the call fails, report a loss of
        the connection.
        """

        self.__queue = Queue.Queue (-1)

        while True:
            try:
                self.__process_step ()
            except Exception, e:
                self.log.error ("DCOP error: {0}".format (e))


    def __process_step (self):
        """
        Process a single queue element.  This is done to ensure that each step
        through the loop has different variables; otherwise, when the lambdas
        get invoked, they'll use the loop's *current* values for "callback"
        and "result" instead of the right ones.
        """

        func, args, callback = self.__queue.get ()
        ok, result = func (*args)
        if ok and callback is not None:
            glib.idle_add (lambda: callback (result) and False)
        elif not ok:
            glib.idle_add (lambda: self.__connector.set_property ("connected", False))


class Root (panflute.daemon.mpris.Root):
    """
    Root MPRIS object for Amarok 1.4.
    """

    from panflute.util import log


    def __init__ (self, connector, call_thread, **kwargs):
        panflute.daemon.mpris.Root.__init__ (self, "Amarok", **kwargs)
        self.__connector = connector
        self.__thread = call_thread


    def do_Quit (self):
        self.__thread.enqueue ("MainApplication-Interface", "quit",
                               callback = lambda result: self.__connector.set_property ("connected", False))


class Player (panflute.daemon.mpris.Player):
    """
    Player MPRIS object for Amarok 1.4.
    """

    from panflute.util import log

    POLL_INTERVAL = 1000


    def __init__ (self, thread, **kwargs):
        panflute.daemon.mpris.Player.__init__ (self, **kwargs)
        for feature in ["GetCaps", "GetStatus", "GetMetadata",
                        "Play", "Pause", "Stop", "Next", "Prev", "Repeat",
                        "PositionGet", "PositionSet", "VolumeGet", "VolumeSet",
                        "SetMetadata", "SetMetadata:rating"]:
            self.register_feature (feature)
        self.__thread = thread
        self.__elapsed = 0
        self.__elapsed_fetch = 0
        self.__url = None

        self.cached_caps.go_next = True
        self.cached_caps.go_prev = True
        self.cached_caps.play = True
        self.cached_caps.pause = True

        self.__poll_source = glib.timeout_add (self.POLL_INTERVAL, self.__poll_cb)
        self.__poll_cb ()


    def remove_from_connection (self):
        if self.__poll_source is not None:
            glib.source_remove (self.__poll_source)
            self.__poll_source = None

        panflute.daemon.mpris.Player.remove_from_connection (self)


    def do_Play (self):
        self.__thread.enqueue ("player", "play")


    def do_Pause (self):
        self.__thread.enqueue ("player", "playPause")


    def do_Stop (self):
        self.__thread.enqueue ("player", "stop")


    def do_Next (self):
        self.__thread.enqueue ("player", "next")


    def do_Prev (self):
        self.__thread.enqueue ("player", "prev")


    def do_PositionGet (self):
        # Rely on the polling to update the value
        return self.__elapsed


    def do_PositionSet (self, elapsed):
        self.__thread.enqueue ("player", "seek", elapsed // 1000)


    def do_SetMetadata (self, name, value):
        if name == "rating":
            self.__thread.enqueue ("player", "setRating", value * 2)
            self.cached_metadata["rating"] = value


    def do_Repeat (self, repeat):
        # XXX: For some reason this succeeds but doesn't do anything to Amarok,
        # even though invoking the same method via the dcop command-line tool
        # works.  Note that dbus.Boolean causes the DCOP library to choke, so
        # manual conversion to a Python boolean value is needed.
        if repeat:
            self.log.debug ("setting track repeat to True")
            self.__thread.enqueue ("player", "enableRepeatTrack", True)
        else:
            self.log.debug ("setting track repeat to False")
            self.__thread.enqueue ("player", "enableRepeatTrack", False)


    def do_VolumeGet (self):
        ok, volume = self.__thread.immediate ("player", "getVolume")
        if ok:
            return volume
        else:
            return 0


    def do_VolumeSet (self, volume):
        self.__thread.enqueue ("player", "setVolume", volume)


    def __poll_cb (self):
        """
        Poll Amarok 1.4 for various status information.
        """

        self.__thread.enqueue ("player", "isPlaying",
                               callback = self.__is_playing_cb)

        self.__thread.enqueue ("player", "encodedURL",
                               callback = self.__encoded_url_cb)

        self.__thread.enqueue ("player", "trackCurrentTime",
                               callback = self.__track_current_time_cb)

        self.__thread.enqueue ("player", "randomModeStatus",
                               callback = self.__random_mode_status_cb)

        self.__thread.enqueue ("player", "repeatPlaylistStatus",
                               callback = self.__repeat_playlist_status_cb)

        self.__thread.enqueue ("player", "repeatTrackStatus",
                               callback = self.__repeat_track_status_cb)

        return True


    def __is_playing_cb (self, playing):
        """
        Update the cached playing status.
        """

        if playing:
            self.cached_status.state = panflute.mpris.STATE_PLAYING
        else:
            self.cached_status.state = panflute.mpris.STATE_PAUSED


    def __encoded_url_cb (self, url):
        """
        Use a URL change as a trigger to fetch new metadata.
        """

        if url is None or url == "":
            self.cached_metadata = {}
            self.cached_caps.provide_metadata = False
            self.cached_caps.seek = False
            self.__url = None
        elif self.__url != url:
            self.__url = url
            self.__elapsed_fetch = self.__elapsed
            collector = MetadataCollector (self, self.__thread, url)
            collector.start ()


    def __track_current_time_cb (self, position):
        """
        Update the cached elapsed time.
        """

        elapsed = position * 1000
        if self.__elapsed != elapsed:
            self.__elapsed = elapsed
            self.do_PositionChange (elapsed)

        # Periodically refresh the metadata for streams.
        if self.cached_metadata.has_key ("mtime") and \
                self.cached_metadata["mtime"] == 0  and \
                self.__elapsed - self.__elapsed_fetch >= 15000:
            self.__elapsed_fetch = self.__elapsed
            collector = MetadataCollector (self, self.__thread, self.__url)
            collector.start ()


    def __random_mode_status_cb (self, random):
        """
        Update the cached playback order.
        """

        if random:
            self.cached_status.order = panflute.mpris.ORDER_RANDOM
        else:
            self.cached_status.order = panflute.mpris.ORDER_LINEAR


    def __repeat_playlist_status_cb (self, repeat):
        """
        Update the cached what-happens-at-end-of-playlist state.
        """

        if repeat:
            self.cached_status.future = panflute.mpris.FUTURE_CONTINUE
        else:
            self.cached_status.future = panflute.mpris.FUTURE_STOP


    def __repeat_track_status_cb (self, repeat):
        """
        Update the cached what-happens-at-end-of-track state.
        """

        if repeat:
            self.cached_status.next = panflute.mpris.NEXT_REPEAT
        else:
            self.cached_status.next = panflute.mpris.NEXT_NEXT


class MetadataCollector (object):
    """
    Collects the results of various DCOP calls to Amarok 1.4 for getting the
    song's metadata, caching it once all the results are in.

    This is conceptually the same as panflute.daemon.dbus.MultiCall, but
    oriented around DCOP and the worker thread.
    """

    from panflute.util import log


    def __init__ (self, player, thread, url):
        self.__player = player
        self.__thread = thread
        self.__url = url
        self.__metadata = {}
        self.__pending = 0


    def start (self):
        """
        Start the series of DCOP calls to get the metadata.
        """

        # Note: if any of these fail, the thread will sever the connection
        # and purge the rest of the queued callbacks, dropping the remaining
        # references to this object and causing it to be GC'd.  Therefore,
        # this object doesn't have to worry about handling failures.

        self.log.debug ("Starting to collect metadata for {0}".format (self.__url))
        self.__pending = 12
        self.__metadata = { "location": self.__url }

        self.__thread.enqueue ("player", "title", callback = self.__title_cb)
        self.__thread.enqueue ("player", "artist", callback = self.__artist_cb)
        self.__thread.enqueue ("player", "album", callback = self.__album_cb)
        self.__thread.enqueue ("player", "trackTotalTime", callback = self.__track_total_time_cb)
        self.__thread.enqueue ("player", "rating", callback = self.__rating_cb)
        self.__thread.enqueue ("player", "coverImage", callback = self.__cover_image_cb)
        self.__thread.enqueue ("player", "track", callback = self.__track_cb)
        self.__thread.enqueue ("player", "genre", callback = self.__genre_cb)
        self.__thread.enqueue ("player", "comment", callback = self.__comment_cb)
        self.__thread.enqueue ("player", "year", callback = self.__year_cb)
        self.__thread.enqueue ("player", "bitrate", callback = self.__bitrate_cb)
        self.__thread.enqueue ("player", "sampleRate", callback = self.__sample_rate_cb)


    def __title_cb (self, title):
        self.__metadata["title"] = title
        self.__decrement_pending ()


    def __artist_cb (self, artist):
        self.__metadata["artist"] = artist
        self.__decrement_pending ()


    def __album_cb (self, album):
        self.__metadata["album"] = album
        self.__decrement_pending ()


    def __track_total_time_cb (self, duration):
        self.__metadata["time"] = int (duration)
        self.__metadata["mtime"] = int (duration) * 1000
        self.__decrement_pending ()


    def __rating_cb (self, rating):
        self.__metadata["rating"] = rating // 2
        self.__metadata["panflute rating scale"] = 5
        self.__decrement_pending ()


    def __cover_image_cb (self, filename):
        if not filename.endswith ("@nocover.png"):
            self.__metadata["arturl"] = panflute.util.make_url (filename)
        self.__decrement_pending ()


    def __track_cb (self, tracknumber):
        self.__metadata["tracknumber"] = tracknumber
        self.__decrement_pending ()


    def __genre_cb (self, genre):
        self.__metadata["genre"] = genre
        self.__decrement_pending ()


    def __comment_cb (self, comment):
        self.__metadata["comment"] = comment
        self.__decrement_pending ()


    def __year_cb (self, year):
        self.__metadata["year"] = year
        self.__decrement_pending ()


    def __bitrate_cb (self, bitrate):
        self.__metadata["audio-bitrate"] = int (bitrate) * 1000
        self.__decrement_pending ()


    def __sample_rate_cb (self, sample_rate):
        self.__metadata["audio-samplerate"] = sample_rate
        self.__decrement_pending ()


    def __decrement_pending (self):
        """
        Update the cached metadata once all intermediate results are in.
        """

        self.__pending -= 1
        assert self.__pending >= 0
        if self.__pending == 0:
            self.__player.cached_metadata = self.__metadata
            self.__player.cached_caps.provide_metadata = True
            self.__player.cached_caps.seek = (self.__metadata.get ("mtime", 0) > 0)
