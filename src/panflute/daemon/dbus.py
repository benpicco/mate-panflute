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
Utility routines for working with D-Bus.
"""

from __future__ import absolute_import

import dbus
import functools


class MultiCall (object):
    """
    Asynchronously invoke multiple D-Bus methods in parallel, and execute
    a function once they've all completed.

    Using this when the results of multiple independent D-Bus calls reduces
    the number of round-trips needed, and handles the accounting needed to
    figure out when each of the asynchronous methods has returned.  Instances
    of this class should only be used once.
    """

    from panflute.util import log


    def __init__ (self):
        self.__methods = []
        self.__pending = 0


    def add_call (self, func, *args, **kwargs):
        """
        Register a D-Bus method to be called with the given arguments and
        reply_handler.
        """

        self.__methods.append ((func, args, kwargs["reply_handler"]))


    def start (self):
        """
        Actually call the D-Bus methods.
        """

        self.__pending = len (self.__methods)
        for (func, args, handler) in self.__methods:
            func (*args, reply_handler = functools.partial (self.__reply_cb, handler),
                         error_handler = self.__error_cb)


    def finished (self):
        """
        Called when all the D-Bus methods have returned.
        """

        pass


    def __reply_cb (self, handler, *args):
        """
        Call the handler for a successful result and decrement the pending
        counter.
        """

        try:
            handler (*args)
        finally:
            self.__decrement_pending ()


    def __error_cb (self, message):
        """
        Report the D-Bus error and decrement the pending counter.
        """

        self.log.warn (message)
        self.__decrement_pending ()


    def __decrement_pending (self):
        """
        Decrement the count of pending results, and call the function if
        all results are in.
        """

        self.__pending -= 1
        assert self.__pending >= 0
        if self.__pending == 0:
            self.finished ()
