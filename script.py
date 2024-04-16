from flask import Flask, request, redirect, url_for, session, make_response
from flask_caching import Cache
import os
import sys
import json
import requests
import re
from uuid import uuid4
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

executor = ThreadPoolExecutor(2)
cache = Cache(config={"CACHE_TYPE": 'SimpleCache'})
app = Flask(__name__)

dotenv_path = Path('./RUN.env')
load_dotenv(dotenv_path=dotenv_path)

FLASK_KEY = os.getenv('FLASK_KEY')
# Configurar el secreto de la sesión
app.secret_key = FLASK_KEY

app.permanent_session_lifetime = timedelta(minutes=5)

cache.init_app(app)

chat_session = {}

with app.app_context():

    # Google Gemini creds
    API_KEY = os.getenv('GOOGLE_API_KEY')
    # CREDENTIALS = service_account.Credentials. from_service_account_file('google_key.json')

    # Whatsapp creds
    WHATSAPP_TOKEN = os.getenv("WA_TOKEN")
    verify_token = os.getenv("VERIFY_TOKEN")
    number_id = os.getenv("NUMBER_ID")

    WHATSAPP_URL = f"https://graph.facebook.com/v19.0/{number_id}/messages"
    
    model = "gemini-pro"

    with open('generation_config.json', "r") as f:
        generation_config = json.load(f)

    with open('safety_settings.json', "r") as f:
        safety_settings = json.load(f)

    with open('content.json', "r") as f:
        contents = json.load(f)

    # Create client
    genai.configure(api_key=API_KEY)
    gemini = genai.GenerativeModel(model_name=model, generation_config=generation_config, safety_settings=safety_settings)


@app.errorhandler(404)
def page_not_found(e):
    return redirect(url_for('index'))


@app.route("/")
def index():
    return "<h1 style='color:blue'>Quarev Whatsapp Chatbot</h1>"
    

@app.route('/webhook', methods=['GET', 'POST'])
def whatsAppWebhook():
    if request.method == 'GET':
        VERIFY_TOKEN = verify_token
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("GET DATA OK: " + challenge, file=sys.stdout)
            return challenge, 200
        else:
            return 'error', 403

    if request.method == 'POST':
        request_data = request.get_json()
        print(request_data, file=sys.stdout)
        if (
            request_data["entry"][0]["changes"][0]["value"].get("messages")
        ) is not None:
            name = request_data["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
            if (
                request_data["entry"][0]["changes"][0]["value"]["messages"][0].get("text")
            ) is not None:
                message = request_data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
                user_phone_number = request_data["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
                global chat_session
                if user_phone_number not in chat_session:
                    chat_init(user_phone_number)
                # sendWhastAppMessage(user_phone_number, f"We have received: {message}")
                executor.submit(handleWhatsAppMessage, user_phone_number, message)
                # user_message_processor(message, user_phone_number, name)
            else:
                # checking that there is data in a flow's response object before processing it
                if (
                    request_data["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"]["response_json"]
                ) is not None:
                    flow_reply_processor(request)

        return make_response('success', 200)
        

def flow_reply_processor(request):
    request_data = json.loads(request.get_data())
    name = request_data["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
    message = request_data["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"][
        "response_json"]

    flow_message = json.loads(message)
    flow_key = flow_message["flow_key"]
    if flow_key == "agentconnect":
        firstname = flow_message["firstname"]
        reply = f"Thank you for reaching out {firstname}. An agent will reach out to you the soonest"
    else:
        firstname = flow_message["firstname"]
        secondname = flow_message["secondname"]
        issue = flow_message["issue"]
        reply = f"Your response has been recorded. This is what we received:\n\n*NAME*: {firstname} {secondname}\n*YOUR MESSAGE*: {issue}"

    user_phone_number = request_data["entry"][0]["changes"][0]["value"]["contacts"][0][
        "wa_id"]
    sendWhastAppMessage(user_phone_number, reply)
    

def waid_formatter(string):
    pattern = r'(^\d\d)(9)(\d.*)'
    subst = "\\1\\3"
    result = re.sub(pattern, subst, string)
    if result:
        return result
    else:
        return string


def sendWhastAppMessage(phoneNumber, message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + WHATSAPP_TOKEN,
    }
    # headers = {"Authorization": WHATSAPP_TOKEN}
    waid = str(phoneNumber)
    waid = waid_formatter(waid)
    payload =  json.dumps(
            {
                "messaging_product": "whatsapp",
                "to": waid,
                "type": "text",
                "text": {"preview_url": False, "body": message},
            }
    )
    req = requests.request("POST", WHATSAPP_URL, headers=headers, data=payload)
    print(headers, file=sys.stdout)
    print(payload, file=sys.stdout)
    print(req)

def geminiCall(text):
    try:
        global chat_session
        response = chatbot[user_id].send_message(text)
        return response.text
        #return 'hola soy gemini'
    except Exception as e:
        print(e, file=sys.stdout)
        return "Sorry, Gemini server error!"


def handleWhatsAppMessage(fromId, text):
    answer = geminiCall(text)
    sendWhastAppMessage(fromId, answer)


def chat_init(wa_id):
    global chat_session
    chat_session[wa_id] = gemini.start_chat(history=contents)

if __name__ == "__main__":
    app.run(debug=True)
