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
GConf utility object for the GNOME panel applet.

This object simplifies access to the applet-instance-specific keys
stored in GConf.
"""

from __future__ import absolute_import

import gconf


class Conf (object):
    """
    Helper object for accessing data stored in GConf.
    """

    from panflute.util import log


    def __init__ (self, applet):
        self.__root = applet.get_preferences_key ()
        self.__client = gconf.client_get_default ()
        self.log.info ("GConf root is {0}".format (self.__root))


    def get_bool (self, key):
        """
        Get a boolean value stored in GConf.
        """

        full_key = self.resolve_key (key)
        return self.__client.get_bool (full_key)


    def set_bool (self, key, value):
        """
        Set a boolean value stored in GConf.
        """

        full_key = self.resolve_key (key)
        self.__client.set_bool (full_key, value)


    def connect_bool (self, key, callback, call_now = False):
        """
        Register a callback function for when a boolean GConf key's value
        changes.

        As compared to connect(), this simplifies the callback's interface
        and allows for simulating an immediate change in the key, which may
        eliminate the need for the caller to implement fetching of the key's
        current value as a separate step.
        """

        def detailed_callback (client, id, entry, unused):
            if entry.value is not None:
                callback (entry.value.get_bool ())

        if call_now:
            callback (self.get_bool (key))
        return self.connect (key, detailed_callback)


    def get_string_list (self, key):
        """
        Get a list of strings stored in GConf.
        """

        full_key = self.resolve_key (key)
        return self.__client.get_list (full_key, gconf.VALUE_STRING)


    def set_string_list (self, key, values):
        """
        Set a list of strings stored in GConf.
        """

        full_key = self.resolve_key (key)
        self.__client.set_list (full_key, gconf.VALUE_STRING, values)


    def connect_string_list (self, key, callback, call_now = False):
        """
        Register a callback function for when a string list GConf key's
        value changes.

        As compared to connect(), this simplifies the callback's interface
        and allows for simulating an immediate change in the key, which may
        eliminate the need for the caller to implement fetching of the key's
        current value as a separate step.
        """

        def detailed_callback (client, id, entry, unused):
            if entry.value is not None:
                callback ([v.get_string () for v in entry.value.get_list (gconf.VALUE_STRING)])

        if call_now:
            callback (self.get_string_list (key))
        return self.connect (key, detailed_callback)


    def connect (self, key, callback):
        """
        Register a callback function for when a GConf key's value changes.

        The caller is responsible for freeing this handler by passing the
        return value to the disconnect method of this object.
        """

        full_key = self.resolve_key (key)
        return self.__client.notify_add (full_key, callback)


    def disconnect (self, id):
        """
        Unregister a callback function.
        """

        self.__client.notify_remove (id)


    def resolve_key (self, key):
        """
        Get the full name of the key specific to this instance of the applet.
        """

        return "{0}/{1}".format (self.__root, key)
