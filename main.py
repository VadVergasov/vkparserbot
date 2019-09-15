import vk_api
import config
import threading
import json
import telebot
from multiprocessing import Process
from urllib.request import urlopen, urlretrieve
import urllib.request
import os
import re

bot = telebot.TeleBot(config.token)

vk_session = vk_api.VkApi(config.phone, config.password)
vk_session.auth()

vk = vk_session.get_api()


last_id = -1

if not os.path.isfile(os.getcwd() + "/chats.json"):
    with open("chats.json", "w"):
        pass
f = open("chats.json", "r")
all_ids = json.loads(f.read())
f.close()


def write_ids():
    global all_ids
    f = open("chats.json", "w")
    f.write(json.dumps(all_ids))
    f.close()


@bot.message_handler(commands=["start", "help"])
def start(message):
    global all_ids
    all_ids.append(message.chat.id)
    write_ids()
    bot.reply_to(
        message,
        "Теперь Вы будете получать сообщения о новых записях в сообществе /dev/null во Вконтакте.",
    )


@bot.message_handler(commands=["stop"])
def stop(message):
    global all_ids
    try:
        all_ids.remove(message.chat.id)
        write_ids()
    except Exception as e:
        print(e)
    bot.reply_to(message, "Вы отписаны от рассылки")


to_send_file = None


def download(url):
    page = urlopen(url)
    content = page.read()
    page.close()
    link = content.decode("utf-8", "ignore")
    string = re.compile('<source src=\\\\"([^"]*)\\\\"')
    urls = string.findall(link)

    for i in ["1080.mp4", "720.mp4", "360.mp4", "240.mp4"]:
        for url in urls:
            if i in url:
                source = url.replace("\\/", "/")
                reg = re.compile(r"/([^/]*\.mp4)")
                name = reg.findall(source)[0]
                path = "tmp/"
                if not os.path.exists(path):
                    os.makedirs(path)
                fullpath = os.path.join(path, name)
                urlretrieve(source, fullpath)
                global to_send_file
                to_send_file = open(fullpath, "rb")
                return


def post(response):
    global all_ids
    attachments = response["attachments"]
    for i in attachments:
        if i["type"] != "link":
            url = (
                "https://vk.com/"
                + i["type"]
                + str(i[i["type"]]["owner_id"])
                + "_"
                + str(i[i["type"]]["id"])
            )
            print(url)
            if i["type"] == "photo":
                info = vk.photos.get(
                    owner_id=str(i[i["type"]]["owner_id"]),
                    album_id=i[i["type"]]["album_id"],
                    photo_ids=i[i["type"]]["id"],
                    count="1",
                )
                for j in info["items"][0]["sizes"]:
                    url = j["url"]
                urllib.request.urlretrieve(
                    url, os.getcwd() + "/tmp/" + i["type"] + ".jpg"
                )
                to_send = open(os.getcwd() + "/tmp/" + i["type"] + ".jpg", "rb")
                for j in range(len(all_ids)):
                    bot.send_photo(all_ids[j], to_send, caption=str(response["text"]))
                to_send.close()
                os.remove("tmp/" + i["type"] + ".jpg")
            elif i["type"] == "video":
                download(url)
                for i in range(len(all_ids)):
                    bot.send_video(
                        all_ids[i], to_send_file, caption=str(response["text"])
                    )
                to_send_file.close()
        elif i["type"] == "link":
            for j in range(len(all_ids)):
                bot.send_message(
                    all_ids[j],
                    str(response["text"])
                    + "\n["
                    + str(i["link"]["title"])
                    + "]("
                    + str(i["link"]["url"])
                    + ")",
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
        else:
            print(response)


def check():
    global last_id
    threading.Timer(20.0, check).start()
    response = vk.wall.get(
        owner_id="-72495085", count="1", filter="owner", extended="1", offset=0
    )
    print(response["items"][0]["id"])
    for i in range(len(response["items"]) - 1, -1, -1):
        if (
            last_id != int(response["items"][0]["id"])
            and response["items"][i]["marked_as_ads"] != 1
        ):
            try:
                post(response["items"][i])
            except Exception as e:
                if not os.path.isfile(os.getcwd() + "/log.txt"):
                    with open("log.txt", "w"):
                        pass
                f = open("log.txt", "r")
                log = f.read()
                f.close()
                log += str(e) + "\n" + str(response["items"][i]) + "\n\n"
                f = open("log.txt", "w")
                f.write(log)
                f.close()
            last_id = int(response["items"][i]["id"])


def run1():
    bot.polling()


if __name__ == "__main__":
    p1 = Process(target=run1)
    p1.start()
    p2 = Process(target=check)
    p2.start()
    p1.join()
    p2.join()
