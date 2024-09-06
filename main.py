#!/usr/bin/env python3
import sys
from dotenv import dotenv_values
import logging
import argparse
import vk2tg


def main():
    parser = argparse.ArgumentParser(
        description='A service for migration from VKontakte to Telegram and simultaneous posting.')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-e', action="append", nargs="*", type=int, metavar=('count', 'order'),
                       help=' -e [count [order [offset]]] Migrate existing posts')
    group.add_argument('-n', action='store_true', help='Mirror new posts')
    group.add_argument('-cm', nargs=2, metavar=('vk_post_url', 'tg_post_url'), help='Edit music in tg from vk')
    parser.add_argument('-l', "--local", action='store_true', help='Use .env file')

    args = parser.parse_args()

    if args.local:
        config = dotenv_values('.env')

    bot = vk2tg.Vk2Tg()
    bot.load_config()
    bot.login()

    if args.e:
        subarg = args.e[0]
        if len(subarg) == 0:
            bot.copy_ex_posts()
        elif len(subarg) == 1:
            bot.copy_ex_posts(subarg[0])
        elif len(subarg) == 2:
            bot.copy_ex_posts(subarg[0], subarg[1])
        elif len(subarg) == 3:
            bot.copy_ex_posts(subarg[0], subarg[1], subarg[2])
        elif len(subarg) > 3:
            raise IOError("argument -e: expected 0..3 arguments")
    elif args.n:
        bot.copy_new_posts()
    elif args.cm:
        bot.edit_music()
    else:
        parser.print_help()
        exit(-1)


if __name__ == '__main__':
    main()
