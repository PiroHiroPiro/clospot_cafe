# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from __future__ import unicode_literals

import os, requests, json, urllib.parse, random
import sys
from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent,
    TextSendMessage, TemplateSendMessage,
    TextMessage, LocationMessage,
    URITemplateAction,
    CarouselTemplate, CarouselColumn
)

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET_KEY'])

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text="カフェを探すね！\n今あなたのいる場所を送ってほしいな！".strip()),
            TextSendMessage(text="line://nv/location")
        ]
    )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    lat = event.message.latitude
    lng = event.message.longitude

    spots = get_spots(lat, lng)
    view = carousel_view(spots, lat, lng)

    line_bot_api.reply_message(event.reply_token,view)

def get_spots(lat, lng):
    GOOGLE_PLACES_API_KEY = os.environ['GOOGLE_PLACES_API_KEY']
    google_places_api_base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
    google_places_api_query = urllib.parse.urlencode({
        "key": GOOGLE_PLACES_API_KEY
        ,"location": str(lat) + "," + str(lng)
        ,"radius": 2000 # 2km

        ,"language": "ja"
        ,"opennow": True
        ,"types": "cafe"
    })
    request_url = google_places_api_base_url + google_places_api_query
    spots = []
    try:
        res = requests.get(request_url)
        result = json.loads(res.text)
        for spot in result["results"]:
            spots.append(spot)
    except:
        print("Error : %s" % request_url)
    return spots

def carousel_view(spots, lat, lng):

    if len(spots) <= 0:
        return TextSendMessage(text="うーん...近くに今開いているカフェはないね！\nまた違うところで試してね！".strip())
    elif len(spots) > 10:
        spots = random.sample(spots, 10)
    random.Random().shuffle(spots)
    columns = []
    for spot in spots:
        carousel_column = create_carousel_column(spot, lat, lng)
        columns.append(carousel_column)

    view = [
        TextSendMessage(text="今開いているカフェが見つかったよ！".strip()),
        TemplateSendMessage(
            alt_text='CloSpots List',
            template=CarouselTemplate(columns=columns)
        )
    ]
    return view

def create_carousel_column(spot, lat, lng):
    spot_name = spot["name"]
    spot_address = spot["vicinity"]
    spot_lat = spot["geometry"]["location"]["lat"]
    spot_lng = spot["geometry"]["location"]["lng"]

    google_search_url = "https://www.google.co.jp/search?" + urllib.parse.urlencode({"q": spot_name + " " + spot_address})
    # google_map_route_url = "comgooglemaps://?" + urllib.parse.urlencode({"saddr": str(lat) + "," + str(lng), "daddr": str(spot_lat) + "," + str(spot_lng), "directionsmode": "walking"})
    google_map_route_url = "http://maps.google.com/maps?" + urllib.parse.urlencode({"saddr": str(lat) + "," + str(lng), "daddr": str(spot_lat) + "," + str(spot_lng), "dirflg": "w"})

    carousel_column = CarouselColumn(
        thumbnail_image_url=spot["icon"],
        title=spot_name,
        text=spot_address,
        actions=[
            URITemplateAction(
               label="Googleで検索",
               uri=google_search_url
            ),
            URITemplateAction(
               label="ここからのルート",
               uri=google_map_route_url
            )
        ]
    )
    return carousel_column

if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage="Usage: python " + __file__ + " [--port <port>] [--help]"
    )
    arg_parser.add_argument("-p", "--port", type=int, default=8000, help="port")
    arg_parser.add_argument("-d", "--debug", default=False, help="debug")
    options = arg_parser.parse_args()

    app.run(debug=options.debug, port=options.port)
