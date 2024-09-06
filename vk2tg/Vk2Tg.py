from dataclasses import dataclass, field
from enum import Enum
import os
import sys
import time

import dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.vk_api import VkApiMethod
from telegram import InputMediaPhoto, InputMediaAudio
from telegram.ext import Updater
import logging

import requests
import subprocess

LOG_FORMAT = logging.Formatter(u'[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
LOG_FILENAME = "bot.log"
LOG_LEVEL = logging.DEBUG
ORDER_OLDEST = 1
"""Chronological order of posts"""
ORDER_NEWEST = -1
"""Wall order of posts"""


@dataclass
class Content:
    """DataClass for wall content transfer"""
    text: str = ""
    media: list[InputMediaPhoto] = field(default_factory=list)
    audio: list[InputMediaAudio] = field(default_factory=list)


def auth_handler():
    """ При двухфакторной аутентификации вызывается эта функция.
    """

    # Код двухфакторной аутентификации
    key = input("Enter authentication code: ")
    # Если: True - сохранить, False - не сохранять.
    remember_device = True

    return key, remember_device


class Vk2Tg:
    def __init__(self, config: dict = None):
        self.vkapi = None
        self.longpoll = None
        self.tools = None
        self.config = config
        self.vk_session = None
        self.tg_session = None
        self.bot_logger = self._setup_logger()
        self.bot_logger.debug("INIT SUCCESSFULLY")

    def edit_music(self, vk_link: str, tg_link:str):
        self.bot_logger.info("Editing music")
        self.bot_logger.info(vk_link)
        vk_id = vk_link.split('?w=wall')[1].split('&')[0]
        tg_id = int(tg_link.split('/')[-1].split('?')[0])

        post = self.vkapi.wall.get_by_id(posts=vk_id)[0]
        content = self._post_handler(post)
        self.bot_logger.info(content.text)
        for idx, song in enumerate(content.audio):
            self.tg_session.edit_message_media(media=song, chat_id=self.config['TELEGRAM_GROUP_ID'], message_id=tg_id + idx)

    def copy_ex_posts(self, count=0, order=ORDER_OLDEST, offset=0):
        """Copy existing posts

        count : number of posts
        order : chronological or wall order (-1 or 1 respectively)
        """
        if count < 0:
            raise ValueError("<count> should be greater than 0")
        self.bot_logger.info("logged for existing posts")

        wall = self.tools.get_all('wall.get', 100, {'owner_id': -int(self.config['VK_GROUP_ID'])})
        self.bot_logger.debug(f"Total number of posts: {wall['count']}")

        total = wall["count"]
        if count == 0:
            count = total
        self.bot_logger.debug(min(offset + count, total))
        wall_posts = sorted(wall["items"], key=lambda d: d["date"])  #sort by date because of pinned post

        for i in range(offset, min(offset + count, total)):
            try:
                post = self._post_handler(wall_posts[::order][i])  #reverse by [::-1] if we want chrono order
                self.bot_logger.debug(post.text)
                self.send_message(post)
                time.sleep(30)
            except ValueError as e:
                self.bot_logger.error(e)
                pass

    def copy_new_posts(self):
        try:
            for event in self.longpoll.listen():
                self.bot_logger.info("new event")

                if event.type == VkBotEventType.WALL_POST_NEW:
                    post = self._post_handler(event.obj)
                    self.send_message(post)
        except KeyboardInterrupt:
            self.bot_logger.info("Bot stopped")
            sys.exit(0)
        except Exception as e:
            self.bot_logger.error("Unexpected error: {}".format(e))
            pass

    def send_message(self, content: Content):
        if len(content.media) != 0:
            message = self.tg_session.send_media_group(self.config['TELEGRAM_GROUP_ID'], media=content.media)[0]
        else:
            message = self.tg_session.send_message(self.config['TELEGRAM_GROUP_ID'], text=content.text)
        if content.audio != [] and message:
            self.tg_session.send_media_group(self.config['TELEGRAM_GROUP_ID'], media=content.audio,
                                             reply_to_message_id=message.message_id)

    def _post_handler(self, post) -> Content:
        try:
            content = Content()
            self.bot_logger.info('Post received')
            if post['text'] != '':
                content.text = post['text']

            if 'attachments' in post.keys():

                for attachment in post['attachments']:
                    if attachment['type'] == 'photo':
                        photo = attachment['photo']
                        max_size_photo = max(photo['sizes'], key=lambda x: x['height'])
                        url = max_size_photo['url']
                        content.media.append(
                            InputMediaPhoto(url, caption=post['text'] if len(content.media) == 0 else ""))

                    if attachment['type'] == 'audio':
                        audio_att = attachment['audio']
                        url = audio_att['url']
                        if url.split(".")[-1][:3] == "mp3":
                            response = requests.get(url)
                            if response.status_code != 200:
                                self.bot_logger.error(f"For {url} received status code {response.status_code}")
                                raise ValueError
                            with open("audio.mp3", 'wb') as file:
                                file.write(response.content)
                        else:
                            subprocess.run(
                                ['ffmpeg', '-http_persistent', 'false', '-i', url, '-y', '-c', 'copy', 'audio.mp3'])
                        content.audio.append(InputMediaAudio(open('audio.mp3', 'rb'),
                                                             performer=audio_att['artist'],
                                                             title=audio_att['title']))
                        os.remove('audio.mp3')

            time.sleep(6)

            self.bot_logger.info('Post processed')
            return content
        except:
            self.bot_logger.error("Unexpected error: {} {}".format(sys.exc_info()[0], sys.exc_info()[1]))
            raise ValueError

    def _setup_logger(self) -> logging.Logger:
        file_handler = logging.FileHandler(LOG_FILENAME)
        file_handler.setFormatter(LOG_FORMAT)
        file_handler.setLevel(LOG_LEVEL)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(LOG_FORMAT)
        console_handler.setLevel(LOG_LEVEL)

        bot_logger = logging.getLogger('bot')
        bot_logger.setLevel(LOG_LEVEL)
        bot_logger.addHandler(file_handler)
        bot_logger.addHandler(console_handler)
        return bot_logger

    def load_config(self, config_path: str = None):
        if not config_path:
            config_path = os.getcwd()
            if getattr(sys, 'frozen', False):  #if program is frozen
                config_path = sys._MEIPASS
        filepath = os.path.join(config_path, '.env')

        self.config = dotenv.dotenv_values(filepath)
        if not self.config:  #check if dotenv_values return empty dict
            raise IOError('.env not found')

        self.bot_logger.debug(".env loaded")

    def login(self):
        self.vk_session = self.vk_login()
        self.tg_session = self.tg_login()

    def vk_login(self, config=None):
        vk_session = vk_api.VkApi(str(self.config['VK_LOGIN']), str(self.config['VK_PASS']), auth_handler=auth_handler,
                                  app_id=int(self.config['VK_APP_ID']),
                                  client_secret=self.config['VK_SECRET'])
        try:
            vk_session.auth(token_only=True)
        except vk_api.AuthError as error_msg:
            self.bot_logger.error(f"Auth error {error_msg}")

            return None
        self.longpoll = VkBotLongPoll(vk_session, self.config['VK_GROUP_ID'])
        self.tools = vk_api.VkTools(vk_session)
        self.vkapi = vk_api.vk_api.VkApiMethod(vk_session)
        self.bot_logger.info("VK logged")
        return vk_session

    def tg_login(self, config=None):
        updater = Updater(self.config['TELEGRAM_BOT_TOKEN'])
        bot = updater.bot
        self.bot_logger.info("TG logged")
        return bot


def main():
    try:
        bot = Vk2Tg()
        bot.load_config()
        bot.login()
        #bot.copy_new_posts()
        #bot.copy_ex_posts()
        bot.edit_music(vk_link="https://vk.com/electro_minds?w=wall-201106047_388",tg_link="")
    except Exception as e:
        logging.error(e)
        exit(-1)


if __name__ == "__main__":
    main()
