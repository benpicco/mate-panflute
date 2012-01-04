dnl
dnl Preamble
dnl

AC_PREREQ(2.53)
AC_INIT(panflute, [trunk], [https://bugs.launchpad.net/panflute/+filebug])
AM_INIT_AUTOMAKE([-Wno-portability])

AC_CONFIG_SRCDIR([src/panflute-daemon])
AC_CONFIG_MACRO_DIR([m4])

AM_MAINTAINER_MODE

dnl
dnl Python
dnl

AM_PATH_PYTHON(2.6)

dnl
dnl Library Dependencies
dnl

dnl Daemon required dependencies

PKG_CHECK_MODULES(DBUS, [dbus-python >= 0.80])
PKG_CHECK_MODULES(PYGOBJECT, [pygobject-2.0])

AX_PYTHON_MODULE([dbus], [required])
AX_PYTHON_MODULE([dbus.exceptions], [required])
AX_PYTHON_MODULE([dbus.service], [required])
AX_PYTHON_MODULE([mateconf], [required])
AX_PYTHON_MODULE([glib], [required])
AX_PYTHON_MODULE([gobject], [required])

dnl Daemon optional dependencies

AX_PYTHON_MODULE([dcopext])
AX_PYTHON_MODULE([kdecore])
AX_PYTHON_MODULE([mpd])
AX_PYTHON_MODULE([pyinotify])
AX_PYTHON_MODULE([xmms.control])
AX_PYTHON_MODULE([xmmsclient])
AX_PYTHON_MODULE([xmmsclient.glib])

dnl Applet required dependencies

PYGTK_MIN_VERSION=2.16
PKG_CHECK_MODULES(PYGTK, [pygtk-2.0 >= $PYGTK_MIN_VERSION], [], [true])
PKG_CHECK_MODULES(MATE_PYTHON_DESKTOP, [mate-python-desktop-2.0], [], [true])

AX_PYTHON_MODULE([mateapplet])
AX_PYTHON_MODULE([gtk])
AX_PYTHON_MODULE([numpy])    dnl If PyGTK was built with it, will crash without it (lp:441527)
AX_PYTHON_MODULE([pango])

dnl Applet optional dependencies

PKG_CHECK_MODULES(PYNOTIFY, [notify-python], [], [])

AX_PYTHON_MODULE([pynotify])

dnl
dnl MateConf
dnl

AC_PATH_PROG(MATECONFTOOL, [mateconftool-2], [no])
if test "x$MATECONFTOOL" = xno; then
	AC_MSG_ERROR([mateconftool-2 executable not found -- it should be installed as part of MateConf])
fi
AC_SUBST(MATECONFTOOL)
AM_MATECONF_SOURCE_2

dnl
dnl i18n Support
dnl

AC_PROG_INTLTOOL([0.40])

GETTEXT_PACKAGE=panflute
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE, "$GETTEXT_PACKAGE", [The gettext package])

AM_GLIB_GNU_GETTEXT

dnl
dnl Output
dnl

AC_CONFIG_FILES([
	Makefile
	src/Makefile
	src/panflute/Makefile
	src/panflute/defs.py.in
	src/panflute/daemon/Makefile
	src/panflute/daemon/amarok/Makefile
	src/panflute/daemon/exaile/Makefile
	src/panflute/applet/Makefile
	src/panflute/debugger/Makefile
	src/panflute/tests/Makefile
	data/Makefile
	po/Makefile.in
])
AC_OUTPUT


if test "x$HAVE_PYMOD_DCOPEXT" != "xyes" -o "x$HAVE_PYMOD_KDECORE" != "xyes"; then
	AC_MSG_WARN([Support for Amarok 1.4 requires the following Python modules to be installed:])
	if test "x$HAVE_PYMOD_DCOPEXT" != "xyes"; then
		AC_MSG_WARN([    * dcopext])
	fi
	if test "x$HAVE_PYMOD_KDECORE" != "xyes"; then
		AC_MSG_WARN([    * kdecore])
	fi
	warned_about_something="yes"
fi

if test "x$HAVE_PYMOD_PYINOTIFY" != "xyes"; then
	AC_MSG_WARN([Support for MOC requires the following Python modules to be installed:])
	AC_MSG_WARN([    * pyinotify])
	warned_about_something="yes"
fi

if test "x$HAVE_PYMOD_MPD" != "xyes"; then
	AC_MSG_WARN([Support for MPD requires the following Python modules to be installed:])
	AC_MSG_WARN([    * mpd])
	warned_about_something="yes"
fi

if test "x$HAVE_PYMOD_XMMS_CONTROL" != "xyes"; then
	AC_MSG_WARN([Support for XMMS requires the following Python modules to be installed:])
	AC_MSG_WARN([    * xmms.control])
	warned_about_something="yes"
fi

if test "x$HAVE_PYMOD_XMMSCLIENT" != "xyes" -o "x$HAVE_PYMOD_XMMSCLIENT_GLIB" != "xyes"; then
	AC_MSG_WARN([Support for XMMS2 requires the following Python modules to be installed:])
	if test "x$HAVE_PYMOD_XMMSCLIENT" != "xyes"; then
		AC_MSG_WARN([    * xmmsclient])
	fi
	if test "x$HAVE_PYMOD_XMMSCLIENT_GLIB" != "xyes"; then
		AC_MSG_WARN([    * xmmsclient.glib])
	fi
	warned_about_something="yes"
fi

if test "x$HAVE_PYMOD_MATEAPPLET" != "xyes" -o "x$HAVE_PYMOD_GTK" != "xyes" -o "x$HAVE_PYMOD_NUMPY" != "xyes" -o "x$HAVE_PYMOD_PANGO" != "xyes"; then
	AC_MSG_WARN([The MATE panel applet requires the following Python modules to be installed:])
	if test "x$HAVE_PYMOD_MATEAPPLET" != "xyes"; then
		AC_MSG_WARN([    * mateapplet])
	fi
	if test "x$HAVE_PYMOD_GTK" != "xyes"; then
		AC_MSG_WARN([    * gtk])
	fi
	if test "x$HAVE_PYMOD_NUMPY" != "xyes"; then
		AC_MSG_WARN([    * numpy])
	fi
	if test "x$HAVE_PYMOD_PANGO" != "xyes"; then
		AC_MSG_WARN([    * pango])
	fi
	warned_about_something="yes"
fi

if test -n "$PYGTK_PKG_ERRORS"; then
	AC_MSG_WARN([The MATE panel applet requires PyGTK $PYGTK_MIN_VERSION or later])
	warned_about_something="yes"
fi

if test "x$HAVE_PYMOD_PYNOTIFY" != "xyes"; then
	AC_MSG_WARN([Popup notifications in the MATE panel applet require the following Python modules to be installed:])
	AC_MSG_WARN([    * pynotify])
	warned_about_something="yes"
fi

if test -n "$warned_about_something"; then
	AC_MSG_NOTICE([The above warnings will not prevent you from installing Panflute.])
	AC_MSG_NOTICE([However, not all features will be available until those additional])
	AC_MSG_NOTICE([Python modules are installed.])
fi
