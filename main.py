#!/usr/bin/env python3
import dotenv
import os
import sys
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from telegram import InputMediaPhoto, InputMediaAudio
from telegram.ext import Updater
import time
import m3u8
import requests
import subprocess
from dotenv import dotenv_values
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import logging

from vk_api.vk_api import VkApiMethod
import argparse
import signal
#TODO: rewrite all as module to get rid of global vars
log_formatter = logging.Formatter(u'[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
log_file_name = "bot.log"

file_handler = logging.FileHandler(log_file_name)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

bot_logger = logging.getLogger('bot')
bot_logger.setLevel(logging.DEBUG)
bot_logger.addHandler(file_handler)
bot_logger.addHandler(console_handler)

extDataDir = os.getcwd()
if getattr(sys, 'frozen', False):
    extDataDir = sys._MEIPASS


def load_config(path: str = "") -> dict:
    filepath = os.path.join(path, '.env')
    config = dotenv_values(filepath)
    if not config:
        bot_logger.error(f"""No .env file at path: {filepath} """)
        raise IOError
    return config

def auth_handler():
    """ При двухфакторной аутентификации вызывается эта функция.
    """

    # Код двухфакторной аутентификации
    key = input("Enter authentication code: ")
    # Если: True - сохранить, False - не сохранять.
    remember_device = True

    return key, remember_device


first = True


def post_handler(post):
    try:
        content = {"text": "", "media": [], "audio": []}
        bot_logger.info('Post received')
        text = ""
        media = []
        audio = []
        if post['text'] != '':
            text = post['text']

        if 'attachments' in post.keys():

            for attachment in post['attachments']:
                if attachment['type'] == 'photo':
                    photo = attachment['photo']
                    max_size_photo = max(photo['sizes'], key=lambda x: x['height'])
                    url = max_size_photo['url']
                    media.append(
                        InputMediaPhoto(url, caption=post['text'] if len(media) == 0 else ""))

                if attachment['type'] == 'audio':
                    audio_att = attachment['audio']
                    url = audio_att['url']
                    if url.split(".")[-1][:3] == "mp3":
                        response = requests.get(url)
                        if response.status_code != 200:
                            bot_logger.error(f"For {url} received status code {response.status_code}")
                            raise ValueError
                        with open("audio.mp3", 'wb') as file:
                            file.write(response.content)
                        audio.append(
                            InputMediaAudio(open('audio.mp3', 'rb'), performer=audio_att['artist'],
                                            title=audio_att['title']))
                    else:
                        subprocess.run(
                            ['ffmpeg', '-http_persistent', 'false', '-i', url, '-y', '-c', 'copy', 'audio.mp3'])
                        audio.append(
                            InputMediaAudio(open('audio.mp3', 'rb'), performer=audio_att['artist'],
                                            title=audio_att['title']))
                        os.remove('audio.mp3')
        content['text'] = text
        content['media'] = media
        content['audio'] = audio

        time.sleep(6)

        bot_logger.info('Post processed')
        return content
    except:
        bot_logger.error("Unexpected error: {} {}".format(sys.exc_info()[0], sys.exc_info()[1]))
        raise ValueError


def send_message(bot, content):
    if len(content['media']) != 0:
        message = bot.send_media_group(config['TELEGRAM_GROUP_ID'], media=content['media'])[0]
    else:
        message = bot.send_message(config['TELEGRAM_GROUP_ID'], text=content['text'])
    if content['audio'] != [] and message:
        bot.send_media_group(config['TELEGRAM_GROUP_ID'], media=content['audio'],
                             reply_to_message_id=message.message_id)


def get_new_posts(bot):
    try:

        vk_session = vk_api.VkApi(token=config['VK_TOKEN'])
        bot_logger.info("vk logged")
        long_poll = VkBotLongPoll(vk_session, config['VK_GROUP_ID'])
        bot_logger.info("vk longpoll logged")

        def signal_handler(sig, frame):
            print("\nKeyboard interrupt exception caught")
            time.sleep(2)
            print("Exiting the program.")
            exit(0)

        # Register the signal handler for SIGINT (Ctrl + C)
        signal.signal(signal.SIGINT, signal_handler)
        for event in long_poll.listen():
            bot_logger.info("new event")

            if event.type == VkBotEventType.WALL_POST_NEW:
                post = post_handler(event.obj)
                send_message(bot, post)



    except KeyboardInterrupt:
        bot_logger.info("Bot stopped")
        sys.exit(0)
    except:
        bot_logger.error("Unexpected error: {} {}".format(sys.exc_info()[0], sys.exc_info()[1]))
        pass


def get_def_posts(bot, *vargs):
    global first
    vargs = vargs[0]
    print(vargs)
    if first:
        vk_session = vk_login()
        bot_logger.info("logged for existing posts")
        tools = vk_api.VkTools(vk_session)

        wall = tools.get_all('wall.get', 100, {'owner_id': -int(config['VK_GROUP_ID'])})
        # wall['items']=wall['items'][:51]
        print(len(wall['items']))
        count = wall['count']
        order = -1
        if vargs:
            if (len(vargs) >= 1):
                count = int(vargs[0])
            if (len(vargs) >= 2):
                order = int(vargs[1]) * -1
        print('Posts count:', count)
        for wall_item in wall['items'][::order]:
            try:

                print(count)
                post = post_handler(wall_item)
                send_message(bot, post)
                count -= 1
                if count <= 0:
                    break
                time.sleep(30)
            except ValueError:
                pass
        first = False


def vk_login():
    bot_logger.info("Logged in vk")
    vk_session = vk_api.VkApi(str(config['VK_LOGIN']), str(config['VK_PASS']), auth_handler=auth_handler,
                              app_id=int(config['VK_APP_ID']),
                              client_secret=config['VK_SECRET'])
    try:
        vk_session.auth(token_only=True)
    except vk_api.AuthError as error_msg:
        print(error_msg)
        return
    return vk_session


def edit_music(bot, *vargs):
    bot_logger.info("Editing music")
    vargs = vargs[0]
    vk_post = vargs[0].split('?w=wall')[1].split('&')[0]
    tg_post = int(vargs[1].split('/')[-1].split('?')[0])
    vk_session = vk_login()

    vk = VkApiMethod(vk_session)
    post = vk.wall.get_by_id(posts=vk_post)[0]
    content = post_handler(post)
    for idx, song in enumerate(content['audio']):
        bot_logger.info(f"Edit {tg_post + idx}")
        bot.edit_message_media(media=song, chat_id=config['TELEGRAM_GROUP_ID'], message_id=tg_post + idx)


def main():
    try:
        global config

        config  = load_config(extDataDir)
        parser = argparse.ArgumentParser(description='A service for migration from VKontakte to Telegram and simultaneous posting.')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-e', nargs=2, metavar=('count', 'order'), help='Migrate existing posts')
        group.add_argument('-n', action='store_true', help='Mirror new posts')
        group.add_argument('-cm', nargs=2, metavar=('vk_post_url', 'tg_post_url'), help='Edit music in tg from vk')
        parser.add_argument('-l', "--local", action='store_true', help='Use .env file')



        args = parser.parse_args()

        if args.local:
            config = dotenv_values('.env')
        bot_logger.info("Bot started")
        updater = Updater(config['TELEGRAM_BOT_TOKEN'])
        bot = updater.bot

    except:
        bot_logger.error("Unexpected error at start: {} {}".format(sys.exc_info()[0], sys.exc_info()[1]))
        sys.exit(0)

    if args.e:
        get_def_posts(bot, args.e)
    elif args.n:

        get_new_posts(bot)
    elif args.cm:
        if len(args.cm) < 2:
            print("Run with args -cm <vk_post_url> <tg_post_url>")
        else:
            edit_music(bot, args.cm)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == '__main__':
    main()




