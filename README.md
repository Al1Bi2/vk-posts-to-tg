# vk-posts-to-tg app
*A service for migration from VKontakte to Telegram and simultaneous posting. *

> **Warning!** The bot is written for personal use and works on duct tape.
> It **is not** stable.

>This bot repost text, images and music while maintaining the structure of the post
## Requirements
Py 3.10 and ffmpeg installed

## Configuration
1. For mirror posting go to  `https://vk.com/<your_group_id>?act=tokens` and create a token with "wall" rights 
and enable Long Poll API here `https://vk.com/<your_group_id>?act=longpoll_api`
2. For migrating old posts you just need your vk credentials and 2fa enabled
3. For tg just create bot and add it as administrator to your channel
4. Create `.env` file and fill it as `.env.example`
5. Install or requirements with `pip install -r requirements.txt`
6. Launch without parameters to get help
7. ???
8. Maybe profit

Also, you can compile it for Win with pyinstaller or chmod for unix

