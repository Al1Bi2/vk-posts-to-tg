#!/usr/bin/env python3
import sys
from dotenv import dotenv_values
import logging
import argparse
import vk2tg


def main():
    parser = argparse.ArgumentParser(
        description='A service for migration from VKontakte to Telegram and simultaneous posting.')
    subparsers = parser.add_subparsers(required=True, dest="type")
    a = subparsers.add_parser("ex", help="Migrate existing posts")
    a.add_argument("-c", "--count", default=0, type=int, help="Count of posts, default - all")
    a.add_argument("-r", "--order", default=1,type=int, choices=[1, -1], help="Order (1 for OLDER first, -1 for NEWER first")
    a.add_argument("-f", "--offset", default=0, type=int, help="Nuber of start post(from 0)")
    b = subparsers.add_parser("new", help='Mirror new posts')
    c = subparsers.add_parser("copy", help='Copy music from vk post to tg (added in case music download error)')
    c.add_argument("-in", dest="i", required=True, type=str, help="URL of VK post")
    c.add_argument("-out", dest="o", required=True, type=str, help="URL of TG post")
    args = parser.parse_args()

    bot = vk2tg.Vk2Tg()
    bot.load_config()
    bot.login()
    match args.type:
        case "ex":
            bot.copy_ex_posts(args.count, args.order, args.offset)
        case "new":
            bot.copy_new_posts()
        case "copy":
            bot.copy_music(args.i, args.o)


if __name__ == '__main__':
    main()
