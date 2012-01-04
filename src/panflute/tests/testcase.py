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
Collection of test cases to run against each player.
"""

from __future__ import absolute_import, print_function

import panflute.mpris

import Queue
import time


class TestCase (object):
    """
    Base for all test cases.
    """

    def __init__ (self, prereqs):
        self.prereqs = prereqs


    def should_be_run (self, player_ex):
        """
        Check if this test case should be attempted.
        """

        for prereq in self.prereqs:
            if not player_ex.Supports (prereq):
                return False
        return True


    def test (self, player, player_ex):
        """
        Actually run the test, raising an error on failure.
        """

        raise NotImplementedError


    def assert_equal (self, tested, expected):
        """
        Assert that two values are equal.
        """

        if tested != expected:
            raise AssertionError ("expected {0} but got {1}".format (expected, tested))


    def assert_almost_equal (self, tested, expected, tolerance):
        """
        Assert that two values are pretty close to equal.
        """

        if abs (tested - expected) > tolerance:
            raise AssertionError ("expected about {0} but got {1}".format (expected, tested))


    def assert_unequal (self, tested, unexpected):
        """
        Assert that two values are unequal.
        """

        if tested == unexpected:
            raise AssertionError ("did not expect {0}".format (tested))


    def assert_member (self, tested, expected_list):
        """
        Assert that a value is one of several possible expected values.
        """

        if tested not in expected_list:
            raise AssertionError ("expected one of {0} but got {1}".format (expected_list, tested))


    def assert_greater (self, tested, lower_bound):
        """
        Assert that a value is greater than another value.
        """

        if tested <= lower_bound:
            raise AssertionError ("expected {0} to be greater than {1}".format (tested, lower_bound))


    def assert_greater_or_equal (self, tested, lower_bound):
        """
        Assert that a value is greater than or equal to another value.
        """

        if tested < lower_bound:
            raise AssertionError ("expected {0} to be greater than or equal to {1}".format (tested, lower_bound))


    def assert_contains (self, container, value):
        """
        Assert that a container (such as a dict) contains something.
        """

        if value not in container:
            raise AssertionError ("expected to find {0} inside {1}".format (value, container))


class Volume (TestCase):
    """
    Getting and setting the volume should be consistent.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["VolumeGet", "VolumeSet"])


    def test (self, player, player_ex):
        # Qmmp fudges the volume setting by a point or two.
        player.VolumeSet (25)
        time.sleep (1)
        self.assert_almost_equal (player.VolumeGet (), 25, 2)

        player.VolumeSet (75)
        time.sleep (1)
        self.assert_almost_equal (player.VolumeGet (), 75, 2)


class State (TestCase):
    """
    Reporting of the playback state through transitions.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["GetStatus", "StatusChange", "Play", "Pause", "Stop"])
        self.__queue = Queue.Queue ()


    def test (self, player, player_ex):
        handler = player.connect_to_signal ("StatusChange", self.__status_change_cb)

        try:
            status = player.GetStatus ()
            self.assert_unequal (status[panflute.mpris.STATUS_STATE], panflute.mpris.STATE_PLAYING)

            player.Play ()
            self.__expect_change (player, [panflute.mpris.STATE_PLAYING], status[panflute.mpris.STATUS_STATE])

            player.Pause ()
            self.__expect_change (player, [panflute.mpris.STATE_PAUSED], panflute.mpris.STATE_PLAYING)

            player.Pause ()
            self.__expect_change (player, [panflute.mpris.STATE_PLAYING], panflute.mpris.STATE_PAUSED)

            player.Stop ()
            self.__expect_change (player, [panflute.mpris.STATE_STOPPED, panflute.mpris.STATE_PAUSED],
                                  panflute.mpris.STATE_PLAYING)
        finally:
            handler.remove ()


    def __expect_change (self, player, expected, previous):
        """
        Expect a status change, throwing an exception if it doesn't.
        """

        # Ignore redundant signals, such as is sent by Amarok 2.3.1.

        status = self.__queue.get (True, 3)
        while status[panflute.mpris.STATUS_STATE] == previous:
            status = self.__queue.get (True, 3)

        self.assert_member (status[panflute.mpris.STATUS_STATE], expected)
        time.sleep (1)      # in case player signals before changing function result (e.g. Qmmp)
        status = player.GetStatus ()
        self.assert_member (status[panflute.mpris.STATUS_STATE], expected)


    def __status_change_cb (self, status):
        """
        Pass the signalled status change to the test thread.
        """

        self.__queue.put (status)


class Metadata (TestCase):
    """
    Reporting of metadata through song changes.

    Actually, this only checks the "location" property, to avoid cases where
    the metadata changes at different times, or if an incomplete set of
    metadata gets provided.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["GetMetadata", "TrackChange", "Next", "Prev"])
        self.__queue = Queue.Queue ()


    def test (self, player, player_ex):
        handler = player.connect_to_signal ("TrackChange", self.__track_change_cb)

        try:
            # Some players start off with current song == first song;
            # others don't.
            initial = self.__location_of (player.GetMetadata ())

            player.Play ()
            if initial == None:
                first = self.__expect_change (player, None)
            else:
                first = self.__location_of (player.GetMetadata ())

            player.Next ()
            second = self.__expect_change (player, first)

            player.Next ()
            third = self.__expect_change (player, second)

            player.Prev ()
            second_again = self.__expect_change (player, third)
            self.assert_equal (second_again, second)

            player.Prev ()
            first_again = self.__expect_change (player, second_again)
            self.assert_equal (first_again, first)
        finally:
            handler.remove ()


    def __expect_change (self, player, previous):
        """
        Expect a metadata change, throwing an exception if it doesn't.
        """

        # Some players (like Banshee) temporarily report metadata {}
        # while inside a transition.  Other players (like Audacious)
        # send multiple signals, so silently swallow those.

        location = self.__location_of (self.__queue.get (True, 3))
        while location is None or location == previous:
            location = self.__location_of (self.__queue.get (True, 3))

        location_too = self.__location_of (player.GetMetadata ())
        self.assert_equal (location_too, location)
        return location


    def __location_of (self, metadata):
        """
        Extract the location value of the metadata, if it exists.
        """

        return metadata.get ("location", None)


    def __track_change_cb (self, metadata):
        """
        Pass the signalled metadata change to the test thread.
        """

        self.__queue.put (metadata)


class Elapsed (TestCase):
    """
    Reporting of elapsed time during playback.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["Play", "PositionGet", "PositionChange"])
        self.__queue = Queue.Queue ()


    def test (self, player, player_ex):
        handler = player_ex.connect_to_signal ("PositionChange", self.__position_change_cb)

        try:
            player.Play ()

            # Since the signals are asynchronous, there's a race condition if
            # we try to compare the results of the signal with the results
            # of a direct call for elapsed time, unless we're extremely
            # careful.

            signal0 = self.__expect_later (-1)

            signal1 = self.__expect_later (signal0)
            direct0 = player.PositionGet ()
            self.assert_greater_or_equal (direct0, signal1)

            signal2 = self.__expect_later (signal1)
            direct1 = player.PositionGet ()
            self.assert_greater (direct1, direct0)
        finally:
            handler.remove ()


    def __expect_later (self, previous):
        """
        Expect the next signalled elapsed time will be later than the
        previous one.
        """

        elapsed = self.__queue.get (True, 3)
        while elapsed == previous:
            # Ignore stutters (e.g. with Rhythmbox starting to play)
            elapsed = self.__queue.get (True, 3)

        self.assert_greater (elapsed, previous)
        return elapsed


    def __position_change_cb (self, elapsed):
        """
        Pass the signalled position change to the test thread.
        """

        self.__queue.put (elapsed)


class Seek (TestCase):
    """
    Seeking back and forth within a song.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["Play", "PositionGet", "PositionSet"])


    def test (self, player, player_ex):
        player.Play ()
        time.sleep (1)

        player.PositionSet (7000)
        time.sleep (1)
        elapsed = player.PositionGet ()
        self.assert_greater_or_equal (elapsed, 7000)

        player.PositionSet (2000)
        time.sleep (1)
        elapsed = player.PositionGet ()
        self.assert_greater_or_equal (elapsed, 2000)
        self.assert_greater (7000, elapsed)


class SetRating (TestCase):
    """
    Setting the rating of a song.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["Play", "Next", "Prev", "GetMetadata", "SetMetadata:rating"])


    def test (self, player, player_ex):
        player.Play ()
        time.sleep (1)

        player_ex.SetMetadata ("rating", 4)
        player.Next ()
        time.sleep (1)

        player_ex.SetMetadata ("rating", 2)
        player.Prev ()
        time.sleep (1)

        rating = player.GetMetadata ()["rating"]
        self.assert_equal (rating, 4)

        player.Next ()
        time.sleep (1)

        rating = player.GetMetadata ()["rating"]
        self.assert_equal (rating, 2)


class RatingScale (TestCase):
    """
    Any song that has a rating should also specify the number of starts on the
    rating scale being used.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["Play", "GetMetadata"])


    def test (self, player, player_ex):
        player.Play ()
        time.sleep (1)

        info = player.GetMetadata ()
        if "rating" in info:
            self.assert_contains (info, "panflute rating scale")
            self.assert_greater_or_equal (info["panflute rating scale"], info["rating"])


class RatingScaleSet (TestCase):
    """
    Stronger version of RatingScale, ensuring that a song actually has a
    rating assigned to it.
    """

    def __init__ (self):
        TestCase.__init__ (self, ["Play", "Next", "GetMetadata", "SetMetadata", "SetMetadata:rating"])


    def test (self, player, player_ex):
        player.Play ()
        time.sleep (1)
        player_ex.SetMetadata ("rating", 4)
        time.sleep (1)
        player.Next ()
        time.sleep (1)
        player.Prev ()
        time.sleep (1)

        info = player.GetMetadata ()
        self.assert_contains (info, "rating")
        self.assert_contains (info, "panflute rating scale")
        self.assert_greater_or_equal (info["panflute rating scale"], info["rating"])


ALL_TESTS = [
    Volume (),
    State (),
    Metadata (),
    Elapsed (),
    Seek (),
    SetRating (),
    RatingScale (),
    RatingScaleSet ()
]
