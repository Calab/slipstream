#!/usr/bin/env python3
"""Slipstream launcher.

    python main.py                 # windowed 1280x720
    python main.py --fullscreen
    python main.py --width 1920 --height 1080
"""

import argparse

from slipstream.app import SlipstreamApp


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Slipstream - an underwater swimming game")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--fps", action="store_true", help="show a frame-rate meter")
    ap.add_argument("--offscreen", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--reset-save", action="store_true", help="clear all best times")
    return ap.parse_args(argv)


def main():
    SlipstreamApp(parse_args()).run()


if __name__ == "__main__":
    main()
