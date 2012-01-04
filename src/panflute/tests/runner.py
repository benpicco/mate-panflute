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
Base classes for running tests against a player configuration.
"""

from __future__ import absolute_import, print_function

import panflute.defs
import panflute.util

import dbus
import glib
import os
import os.path
import shutil
import subprocess
import sys
import threading
import time
import traceback


class Launcher (object):
    """
    Launch a subprocess for running a series of tests against the same
    player configuration.
    """

    def __init__ (self, daemon_prefix, prefix, user, password, test_names, owner, data, player_name):
        self.__daemon_prefix = daemon_prefix
        self.__prefix = prefix
        self.__user = user
        self.__password = password
        self.__test_names = test_names
        self.__owner = owner
        self.__data = data
        self.__player_name = player_name

        self.__child = None
        self.__env = os.environ.copy ()


    def start (self):
        """
        Start the subprocess and begin collecting results from it.
        """

        with open ("/dev/null", "r") as null:
            child = subprocess.Popen ([sys.argv[0], "--subprocess", self.__player_name, self.__daemon_prefix,
                                            self.__prefix, self.__user, self.__password] + self.__test_names,
                                      shell = False, close_fds = True, preexec_fn = os.setsid,
                                      stdin = null, stdout = subprocess.PIPE, env = self.__env)

        glib.io_add_watch (child.stdout, glib.IO_IN | glib.IO_HUP, self.__child_io_cb)


    def augment_env_path (self, name, value):
        """
        Augment a PATH-style environment variable, creating it if it doesn't
        already exist.
        """

        if self.__env.has_key (name):
            self.__env[name] = "{0}:{1}".format (value, self.__env[name])
        else:
            self.__env[name] = value


    def set_env (self, name, value):
        """
        Set an environment variable for the subprocess.
        """

        self.__env[name] = value


    def __child_io_cb (self, source, cond):
        """
        Called when the subprocess produces more data, or closes the pipe.
        """

        if cond == glib.IO_IN:
            more = self.__process_message (source)
            if not more:
                self.__owner.start_next_launcher ()
            return more
        else:
            # glib.IO_HUP indicates the subprocess crashed, probably leaving
            # behind its own children.  Abort testing since any results
            # produced without cleaning up the mess will be unreliable.
            self.__owner.abort_testing ()
            return False


    def __process_message (self, source):
        """
        Process a message from the subprocess, returning True if more
        messages are expected.
        """

        # Read until reaching a blank line (record separator).
        try:
            line = source.readline ().rstrip ()
            [result, test_name] = line.split (" ")
            if result != "***":
                detail = ""
                line = source.readline ().rstrip ()
                while line != "":
                    detail += line + "\n"
                    line = source.readline ().rstrip ()
                if result == "START":
                    self.__owner.process_start (self.__data, test_name)
                else:
                    self.__owner.process_result (self.__data, test_name, result, detail)
                return True
            else:
                return False
        except ValueError:
            # The split() failed, so data was truncated, probably because the
            # subprocess got killed.
            return False


class Runner (threading.Thread):
    """
    Runs a series of tests against a player configuration.
    """

    TONE_PATHS = [os.path.join (panflute.defs.PKG_DATA_DIR, filename)
                  for filename in ["test220.ogg", "test440.ogg", "test660.ogg"]]

    TONE_URIS = map (panflute.util.make_url, TONE_PATHS)


    def __init__ (self, main_loop, daemon_prefix, prefix, user, password, tests):
        threading.Thread.__init__ (self, name = "Test runner")

        self.__main_loop = main_loop
        self.__daemon_prefix = daemon_prefix
        self.__prefix = prefix
        self.__user = user
        self.__password = password
        self.__tests = tests

        self.__panflute = None
        self.__child = None

        self.bus = dbus.SessionBus ()
        proxy = self.bus.get_object ("org.freedesktop.DBus", "/org/freedesktop/DBus")
        self.bus_obj = dbus.Interface (proxy, "org.freedesktop.DBus")


    def run (self):
        if len (self.__tests) == 0:
            # For debugging, just start the player as it would be invoked for
            # running tests, then quit.
            try:
                print ("DEBUG: prepare_persistent", file = sys.stderr)
                self.prepare_persistent ()
                time.sleep (3)
                print ("DEBUG: prepare_single", file = sys.stderr)
                self.prepare_single (self.__prefix, self.__user, self.__password)
                time.sleep (3)
            finally:
                self.__main_loop.quit ()
        else:
            # The calls to sleep are to give various things a chance to settle
            # down before continuing; having two instances of the same player
            # running at the same time, for example, causes problems.

            try:
                print ("DEBUG: prepare_persistent", file = sys.stderr)
                self.prepare_persistent ()
                print ("DEBUG: start_daemon", file = sys.stderr)
                self.start_daemon ()
                print ("DEBUG: sleep", file = sys.stderr)
                time.sleep (3)

                for test in self.__tests:
                    try:
                        print ("START {0}".format (test.__class__.__name__))
                        print ()
                        sys.stdout.flush ()

                        print ("DEBUG: prepare_single", file = sys.stderr)
                        self.prepare_single (self.__prefix, self.__user, self.__password)
                        time.sleep (3)
                        print ("DEBUG: create_proxies", file = sys.stderr)
                        player, player_ex = self.create_proxies ()
                        print ("DEBUG: sleep", file = sys.stderr)
                        time.sleep (3)

                        print ("DEBUG: should_be_run", file = sys.stderr)
                        if test.should_be_run (player_ex):
                            print ("DEBUG: test", file = sys.stderr)
                            test.test (player, player_ex)
                            result = "PASS"
                            detail = ""
                        else:
                            result = "SKIP"
                            detail = ""
                    except Exception, e:
                        result = "FAIL"
                        detail = traceback.format_exc (e)
                    finally:
                        try:
                            print ("DEBUG: cleanup_single", file = sys.stderr)
                            self.cleanup_single ()
                            print ("DEBUG: wait_for", file = sys.stderr)
                            self.wait_for ("org.mpris.panflute", False)
                            print ("DEBUG: sleep", file = sys.stderr)
                            time.sleep (3)
                        except Exception, e:
                            if result != "FAIL":
                                result = "FAIL"
                                detail = traceback.format_exc (e)
                        finally:
                            if self.__child is not None:
                                print ("DEBUG: end_process", file = sys.stderr)
                                self.end_process (self.__child)
                                self.__child = None

                    print ("{0} {1}".format (result, test.__class__.__name__))
                    if detail != "":
                        print (detail.rstrip ())
                    print ()
                    sys.stdout.flush ()

                print ("DEBUG: stop_daemon", file = sys.stderr)
                self.stop_daemon ()
                print ("DEBUG: cleanup_persistent", file = sys.stderr)
                self.cleanup_persistent ()
                print ("DEBUG: sleep", file = sys.stderr)
                time.sleep (3)

            finally:
                print ("*** ***")
                sys.stdout.flush ()
                print ("DEBUG: quit", file = sys.stderr)
                self.__main_loop.quit ()


    def prepare_persistent (self):
        """
        Perform any pre-test setup that doesn't have to be re-done every
        time a test is started.
        """

        pass


    def cleanup_persistent (self):
        """
        Perform any post-test cleanup after all the tests are done.
        """

        pass


    def prepare_single (self, prefix, user, password):
        """
        Perform setup before each test.
        """

        pass


    def cleanup_single (self):
        """
        Perform cleanup after each test.
        """

        pass


    def set_child (self, child):
        """
        Set a child to be forcibly terminated at the end of the test.
        """

        self.__child = child


    def rmdirs (self, path):
        """
        Recursive remove a directory.
        """

        try:
            shutil.rmtree (os.path.expanduser (path))
        except OSError:
            # don't care if directory didn't exist
            pass


    def rmfile (self, path):
        """
        Delete a file, ignoring errors.
        """

        try:
            os.unlink (os.path.expanduser (path))
        except OSError:
            # don't care if file didn't exist
            pass


    def mkdir (self, path):
        """
        Create a directory, ignoring errors.
        """

        try:
            os.makedirs (os.path.expanduser (path))
        except OSError:
            # don't care if directory already exists
            pass


    def run_command (self, command):
        """
        Run a shell command.
        """

        with open ("/dev/null", "r+") as null:
            return subprocess.Popen (command, shell = False, close_fds = True, preexec_fn = os.setsid,
                                     stdin = null, stdout = null, stderr = null)


    def end_process (self, child):
        """
        Forcibly terminate a subprocess.
        """

        try:
            if child.poll () is None:
                child.terminate ()
                time.sleep (3)
                if child.poll () is None:
                    child.kill ()
                    child.wait ()
        except OSError, e:
            # 3 == "no such process" == not a problem
            if e.errno != 3:
                raise e


    def start_daemon (self):
        """
        Start the Panflute daemon.
        """

        daemon = os.path.join (self.__daemon_prefix, "bin/panflute-daemon")

        #self.__panflute = self.run_command ([daemon, "-d"])

        with open ("/dev/null", "r") as null:
            with open ("/tmp/panflute-daemon.out", "a") as out:
                with open ("/tmp/panflute-daemon.err", "a") as err:
                    self.__panflute = subprocess.Popen ([daemon, "-d"],
                                                        shell = False, close_fds = True, preexec_fn = os.setsid,
                                                        stdin = null, stdout = out, stderr = err)

        self.wait_for ("org.kuliniewicz.Panflute", True)


    def stop_daemon (self):
        """
        Stop the Panflute daemon.
        """

        try:
            self.end_process (self.__panflute)
            self.wait_for ("org.kuliniewicz.Panflute", False, 1)
        finally:
            self.__panflute = None


    def create_proxies (self):
        """
        Create the player proxy objects.
        """

        self.wait_for ("org.mpris.panflute", True)

        proxy = self.bus.get_object ("org.mpris.panflute", "/Player")
        player = dbus.Interface (proxy, panflute.mpris.INTERFACE)
        player_ex = dbus.Interface (proxy, "org.kuliniewicz.Panflute")

        return player, player_ex


    def wait_for (self, name, wanted, tries = 20):
        """
        Wait for a D-Bus name to appear, giving up after too many tries.
        """

        while tries > 0:
            time.sleep (1)
            if self.bus_obj.NameHasOwner (name) == wanted:
                return
            tries = tries - 1

        raise TestError


class TestError (Exception):
    pass
