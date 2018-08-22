#!/usr/bin/python3

"""
Wrapper around xrandr.

### Created a udev rule (/etc/udev/rules.d/95-monitor-hotplug.rules):

KERNEL=="card0", SUBSYSTEM=="drm",
ENV{LC_ALL}="en_US.utf-8", ENV{LANG}="en_US.utf-8",
ENV{DISPLAY}=":0", ENV{XAUTHORITY}="/home/phil/.Xauthority",
RUN+="/home/phil/scripts/myrandr load"

Notes:
- has to be in one line, added line breaks for readability
- check for correct display number (`env | grep DISPLAY`), maybe ":0", ":1" etc.

### Monitor udev action:
» udevadm monitor --environment --udev
monitor will print the received events for:
UDEV - the event which udev sends out after rule processing

UDEV  [106105.021984] change   /devices/pci0000:00/0000:00:02.0/drm/card0 (drm)
ACTION=change
DEVLINKS=/dev/dri/by-path/pci-0000:00:02.0-card
DEVNAME=/dev/dri/card0
DEVPATH=/devices/pci0000:00/0000:00:02.0/drm/card0
DEVTYPE=drm_minor
DISPLAY=:0
HOTPLUG=1
ID_FOR_SEAT=drm-pci-0000_00_02_0
ID_PATH=pci-0000:00:02.0
ID_PATH_TAG=pci-0000_00_02_0
LANG=en_US.utf-8
LC_ALL=en_US.utf-8
MAJOR=226
MINOR=0
SEQNUM=2871
SUBSYSTEM=drm
TAGS=:master-of-seat:uaccess:seat:
USEC_INITIALIZED=4287742
XAUTHORITY=/home/phil/.Xauthority
...

### Test udev rules:
» udevadm test $(udevadm info -q path -n /dev/dri/card0) 2>&1
(/dev/dri/card0 is device name)

### .Xauthority
» mv .Xauthority .Xauthority.bak
» touch .Xauthority
» # check `env | grep DISPLAY` for value
» xauth generate :1 . trusted

"""


import click  # need to install it as root "sudo pacman -S python-click"
import csv
from datetime import datetime
import errno
import logging
import os
import subprocess
import re
from operator import attrgetter


HOME = "/home/phil"  # cannot use os.environ["HOME"] because not phil executes this in udev rule
LOG_PATH = os.path.join(HOME, ".myrandr/log")
PROFILES_PATH = os.path.join(HOME, ".myrandr/profiles")
PROFILES_FILE = os.path.join(PROFILES_PATH, "profiles.txt")
LOG_DATEFMT = '%m-%d %H:%M:%S'

# TODO: cleanup/shorten logging conf
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger()
LOGGER.handlers = []

# create file handler and stream handler
FILE_HANDLER = logging.FileHandler(os.path.join(LOG_PATH, "myrandr.log"))
FILE_HANDLER.setLevel(logging.DEBUG)
# create console handler with a potential different log level
CONSOLE_HANDLER = logging.StreamHandler()
CONSOLE_HANDLER.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
CONSOLE_HANDLER.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt=LOG_DATEFMT))
FILE_HANDLER.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt=LOG_DATEFMT))
# add handler to logger
LOGGER.addHandler(CONSOLE_HANDLER)
LOGGER.addHandler(FILE_HANDLER)


XRANDR_LINE = re.compile(r"(?P<name>.*) (?P<connected>(dis)?connected) ?(?P<mode>primary)? ?(?P<res_and_pos>\d+x\d+\+\d+\+\d+)? \(.*$")
RES_AND_POS = re.compile(r"(?P<resolution>\d+x\d+)(?P<position>\+\d+\+\d+)")
XY_POSITION = re.compile(r"\+(?P<x_position>\d+)\+(?P<y_position>\d+)")


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def left_or_right(name):
    # TODO: remove the hardcodedness!
    # LOL
    BASE_SCREEN = "eDP-1"
    BASE_SCREEN_WORK = "LVDS-1"

    if name == "DP-2-2":
        return ["--right-of", BASE_SCREEN]
    elif name == "HDMI-1":
        return ["--right-of", BASE_SCREEN]
    elif name == "HDMI-2":
        return ["--right-of", BASE_SCREEN_WORK]
    elif name == "HDMI-3":
        return ["--right-of", "HDMI-2"]
    return []
    # LOL end


def relative_position_xrandr(screen_name, sorted_screens):
    assert screen_name in sorted_screens
    index = sorted_screens.index(screen_name)
    if index > 0:
        return ["--right-of", sorted_screens[index - 1]]
    else:
        return []


class Screen(object):
    def __init__(self, name, is_connected, position):
        self.name = name
        self.is_connected = is_connected
        self.position = position

    def xrandr_args(self, sorted_screens=None):
        result = ["--output", self.name]
        if self.is_connected and sorted_screens is not None and self.name in sorted_screens:
            result.append("--auto")
            result.extend(relative_position_xrandr(self.name, sorted_screens))
        elif self.is_connected:
            result.append("--auto")
            result.extend(left_or_right(self.name))
            # return result
        else:
            result.append("--off")

        return result

    @property
    def x_position(self):
        return self._get_pos("x_position")

    @property
    def y_position(self):
        return self._get_pos("y_position")

    def _get_pos(self, position_name):
        if not self.position:
            return 0
        match_pos = XY_POSITION.match(self.position)
        position = int(match_pos.group(position_name))
        return position

    def __repr__(self):
        connected_string = "connected" if self.is_connected else "disconnected"
        position_string = self.position if self.position else ""
        return " ".join([self.name, connected_string, position_string])


def get_screen(line):
    """create screen object from xrandr output"""
    match_line = XRANDR_LINE.match(line)
    name = match_line.group("name")
    is_connected = True if match_line.group("connected") == "connected" else False
    res_and_pos = match_line.group("res_and_pos")
    if res_and_pos:
        match_res_and_pos = RES_AND_POS.match(res_and_pos)
        position = match_res_and_pos.group("position")
    else:
        position = None

    return Screen(name, is_connected, position)


def get_screens(connected_only=False):
    result = subprocess.check_output("xrandr").decode("utf-8")
    lines = result.split("\n")
    lines = [x for x in lines if "connected" in x]  # matches "connected" and "disconnected"

    screens = [get_screen(line) for line in lines]
    if connected_only:
        return [screen for screen in screens if screen.is_connected]
    return screens


def lookup_profile(name):
    headers = ["profile_name", "screen_names", "sorted_screens"]
    with open(PROFILES_FILE, "r") as infile:
        reader = csv.DictReader(infile, headers, delimiter="|")
        for row in reader:
            if name == row["profile_name"]:
                return row["sorted_screens"].split(";")

    return None


@click.group()
def main():
    pass


@main.command()
@click.argument("profile_name", required=True)
def save(profile_name):
    mkdir_p(PROFILES_PATH)
    LOGGER.info("save profile '%s'", profile_name)

    screens = get_screens(connected_only=True)
    names = ";".join([screen.name for screen in screens])
    left2right = sorted(screens, key=attrgetter("x_position"))
    sorted_names = ";".join([screen.name for screen in left2right])

    with open(PROFILES_FILE, "a") as _file:
        line = "%s|%s|%s" % (profile_name, names, sorted_names)
        _file.write(line)
        _file.write("\n")


@main.command()
@click.argument("profile_name", required=False)
def load(profile_name):
    mkdir_p(LOG_PATH)
    LOGGER.info("%s triggered myrandr" % os.environ.get("USER", "udev"))

    screens = get_screens()
    connected_screens = get_screens(connected_only=True)
    sorted_screens = lookup_profile(profile_name)
    print(sorted_screens)

    xrandr_args = [arg for screen in screens for arg in screen.xrandr_args(sorted_screens)]
    command = ["xrandr"] + xrandr_args
    LOGGER.info("xrandr command: '%s'" % " ".join(command))

    # now do it :)
    subprocess.run(command)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
