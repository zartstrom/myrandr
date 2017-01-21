

import click
import os
import subprocess
import re


# XRANDR_LINE = re.compile(r"(?P<name>.*) (?P<connected>(dis)?connected) (?P<mode>primary)? (?P<resolution>\d+x\d+\+\d+\+\d)?")
XRANDR_LINE = re.compile(r"(?P<name>.*) (?P<connected>(dis)?connected) ?(?P<mode>primary)? ?(?P<res_and_pos>\d+x\d+\+\d+\+\d+)? \(.*$")
RES_AND_POS = re.compile(r"(?P<resolution>\d+x\d+)(?P<position>\+\d+\+\d+)")

BASE_SCREEN = "eDP-1"


def left_or_right(name):
    # TODO: remove hardcodedness
    if name == "DP-2-2":
        return ["--left-of", BASE_SCREEN]
    elif name == "HDMI-1":
        return ["--right-of", BASE_SCREEN]
    else:
        return []


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

    result = subprocess.check_output("xrandr").decode("utf-8")
    lines = result.split("\n")
    lines = [x for x in lines if "connected" in x]
    for line in lines:
        screen = get_screen(line)
    screens = [get_screen(line) for line in lines]
    # for screen in screens:
    #     print(screen.xrandr_args())
    xrandr_args = [arg for screen in screens for arg in screen.xrandr_args()]
    # print(xrandr_args)
    # print
    subprocess.run(["xrandr"] + xrandr_args)

if __name__ == "__main__":
    myrandr()
