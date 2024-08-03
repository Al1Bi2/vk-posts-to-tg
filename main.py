#!/usr/bin/env python3

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
from dotenv import  dotenv_values
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import logging

from vk_api.vk_api import VkApiMethod

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
config = dotenv_values(os.path.join(extDataDir, '.env'))

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
    try:  # TODO: rewrite the code
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
        content['text'] = text
        content['media'] = media
        content['audio'] = audio

        time.sleep(6)
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
    try:  # TODO: rewrite the code

        vk_session = vk_api.VkApi(token=config['VK_TOKEN'])
        bot_logger.info("vk logged")
        long_poll = VkBotLongPoll(vk_session, config['VK_GROUP_ID'])
        bot_logger.info("vk longpoll logged")
        for event in long_poll.listen():

            if event.type == VkBotEventType.WALL_POST_NEW:
                post = post_handler(event.obj)
                send_message(bot, post)




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


if __name__ == '__main__':

    args = sys.argv
    if args is None or len(args) < 2:
        print("usage: vk-to-tg [-e <count> <order>] [-n] [-cm <vk_post_url> <tg_post_url>]")
        sys.exit(0)
    posts_type = args[1]

    try:
        if posts_type == "-local":
            config = dotenv_values('.env')
        bot_logger.info("Bot started")
        updater = Updater(config['TELEGRAM_BOT_TOKEN'])
        bot = updater.bot

    except:
        bot_logger.error("Unexpected error at start: {} {}".format(sys.exc_info()[0], sys.exc_info()[1]))
        sys.exit(0)


    match posts_type:
        case '-e':
            get_def_posts(bot, args[2:])
        case '-n':
            while True:
                get_new_posts(bot)
        case '-cm':
            if len(args) < 4:
                print("Run with args -cm <vk_post_url> <tg_post_url>")
            edit_music(bot, args[2:])
        case _:
            print("usage: vk-to-tg [-e <count> <order>] [-n] [-cm <vk_post_url> <tg_post_url>]")
            sys.exit(0)




def download_key(key_uri: str) -> bin:
    return requests.get(url=key_uri).content


def parse_segments(segments: list):
    segments_data = {}

    for segment in segments:
        segment_uri = segment.get("uri")

        extended_segment = {
            "segment_method": None,
            "method_uri": None
        }
        if segment.get("key").get("method") == "AES-128":
            extended_segment["segment_method"] = True
            extended_segment["method_uri"] = segment.get("key").get("uri")
        segments_data[segment_uri] = extended_segment
    return segments_data


def download_segments(segments_data: dict, index_url: str) -> bin:
    downloaded_segments = []

    for uri in segments_data.keys():
        audio = requests.get(url=index_url.replace("index.m3u8", uri))

        downloaded_segments.append(audio.content)

        if segments_data.get(uri).get("segment_method") is not None:
            key_uri = segments_data.get(uri).get("method_uri")
            key = download_key(key_uri=key_uri)

            iv = downloaded_segments[-1][0:16]
            ciphered_data = downloaded_segments[-1][16:]

            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            data = unpad(cipher.decrypt(ciphered_data), AES.block_size)
            downloaded_segments[-1] = data

    return b''.join(downloaded_segments)


def get_music(audio):
    url = audio['url']
    m3u8_data = m3u8.load(url)
    segments = m3u8_data.get("segments")
    segments_data = parse_segments(segments=segments)
    segments_loaded = download_segments(segments_data=segments_data, index_url=url)
    with open("", "w+b") as f:
        f.write(download_segments(segments_data, url))