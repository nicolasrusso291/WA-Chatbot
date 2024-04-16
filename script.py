from flask import Flask, request, redirect, url_for, session, make_response
from flask_caching import Cache
import os
import sys
import json
import requests
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

chatbot = {}

with app.app_context():

    # Google Gemini creds
    API_KEY = os.getenv('GOOGLE_API_KEY')
    # CREDENTIALS = service_account.Credentials. from_service_account_file('google_key.json')

    # Whatsapp creds
    WHATSAPP_TOKEN = os.getenv("WA_TOKEN")
    verify_token = os.getenv("VERIFY_TOKEN")
    number_id = os.getenv("NUMBER_ID")

    WHATSAPP_URL = f"https://graph.facebook.com/v18.0/{number_id}/messages"
    
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
    # Si el usuario no tiene una sesión, se crea una nueva
    if "user_id" not in session:
        session["user_id"] = str(uuid4())

    chatbot[session["user_id"]] = gemini.start_chat(history=contents)

    # Redirigir al usuario a la página principal
    # return redirect(url_for("whatsAppWebhook"))
    return "<h1 style='color:blue'>Quarev Whatsapp Chatbot</h1>"
    

def sendWhastAppMessage(phoneNumber, message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + WHATSAPP_TOKEN,
    }
    # headers = {"Authorization": WHATSAPP_TOKEN}
    payload =  json.dumps(
            {
                "messaging_product": "whatsapp",
                "to": str(phoneNumber),
                "type": "text",
                "text": {"preview_url": False, "body": message},
            }
    )
    req = requests.request("POST", WHATSAPP_URL, headers=headers, data=payload)
    print(headers, file=sys.stdout)
    print(payload, file=sys.stdout)
    print(req)    


def makeOpenAIFunctionCall(text):
    """
    system_instruction = "You are a helpful Chatbot based on WhatsApp. Include relevant emojis>"
    messages = [{"role": "system", "content": system_instruction}]

    question = {}
    question['role'] = 'user'
    question['content'] = text
    messages.append(question)
    """
    try:
        # response = openai.ChatCompletion.create(model='gpt-3.5-turbo-0613',messages=messages)
        # return response['choices'][0]['message']['content']
        return 'hola soy gemini'
    except Exception as e:
        print(e, file=sys.stdout)
        return "Sorry, Gemini server error!"


def handleWhatsAppMessage(fromId, text):
    answer = makeOpenAIFunctionCall(text)
    sendWhastAppMessage(fromId, answer)


@app.route('/123456', methods=['GET', 'POST'])
def whatsAppWebhook():
    if request.method == 'GET':
        VERIFY_TOKEN = verify_token
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("GET DATA OK", file=sys.stdout)
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
                sendWhastAppMessage(user_phone_number, f"We have received: {message}")
                executor.submit(handleWhatsAppMessage, user_phone_number, message)
                # user_message_processor(message, user_phone_number, name)
            else:
                # checking that there is data in a flow's response object before processing it
                if (
                    request_data["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"]["response_json"]
                ) is not None:
                    flow_reply_processor(request)

        return make_response('success', 200)
        '''
        if 'object' in data and 'entry' in data:
            if data['object'] == 'whatsapp_business_account':
                for entry in data['entry']:
                    fromId = entry['changes'][0]['value']['messages'][0]['from']
                    msgType = entry['changes'][0]['value']['messages'][0]['type']
                    text = entry['changes'][0]['value']['messages'][0]['text']['body']
                    sendWhastAppMessage(fromId, f"We have received: {text}")
                    executor.submit(handleWhatsAppMessage, fromId, text)

        return 'success', 200
        '''
        

if __name__ == "__main__":
    app.run(debug=True)
