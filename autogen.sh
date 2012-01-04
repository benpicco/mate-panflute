#! /bin/sh

git log >ChangeLog
REQUIRED_AUTOMAKE_VERSION=1.10 REQUIRED_INTLTOOL_VERSION=0.40 mate-autogen.sh "$@"
