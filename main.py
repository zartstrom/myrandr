#!/usr/bin/python3

"""
Wrapper around xrandr.
Created a udev rule (/etc/udev/rules.d/95-monitor-hotplug.rules)

KERNEL=="card0", SUBSYSTEM=="drm",
ENV{LC_ALL}="en_US.utf-8", ENV{LANG}="en_US.utf-8",
ENV{DISPLAY}=":0", ENV{XAUTHORITY}="/home/phil/.Xauthority",
RUN+="/home/phil/scripts/myrandr"
(has to be in one line, added line breaks for readability)
"""


import click  # need to install it as root "sudo pacman -S python-click"
from datetime import datetime
import errno
import os
import subprocess
import re


XRANDR_LINE = re.compile(r"(?P<name>.*) (?P<connected>(dis)?connected) ?(?P<mode>primary)? ?(?P<res_and_pos>\d+x\d+\+\d+\+\d+)? \(.*$")
RES_AND_POS = re.compile(r"(?P<resolution>\d+x\d+)(?P<position>\+\d+\+\d+)")

HOME = "/home/phil"  # cannot use os.environ["HOME"] because root executes this in udev rule


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
        return ["--left-of", BASE_SCREEN]
    elif name == "HDMI-1":
        return ["--right-of", BASE_SCREEN]
    elif name == "HDMI-2":
        return ["--right-of", "HDMI-3"]
    elif name == "HDMI-3":
        return ["--right-of", BASE_SCREEN_WORK]
    return []
    # LOL end


class Screen(object):
    def __init__(self, name, is_connected, position):
        self.name = name
        self.is_connected = is_connected
        self.position = position

    def xrandr_args(self):
        result =  ["--output", self.name]
        if not self.is_connected:
            result.append("--off")

        result.append("--auto")
        result.extend(left_or_right(self.name))

        return result

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


@click.command()
def myrandr():
    mkdir_p(os.path.join(HOME, ".myrandr/log"))
    with open(os.path.join(HOME, ".myrandr/log", "plug.log"), "a") as logfile:
        logfile.write("myrandr called at %s.\n" % str(datetime.now()))

    result = subprocess.check_output("xrandr").decode("utf-8")
    lines = result.split("\n")
    lines = [x for x in lines if "connected" in x]  # matches "connected" and "disconnected"

    screens = [get_screen(line) for line in lines]
    xrandr_args = [arg for screen in screens for arg in screen.xrandr_args()]

    # now do it :)
    subprocess.run(["xrandr"] + xrandr_args)


if __name__ == "__main__":
    myrandr()
