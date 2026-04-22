import os
from flask import Flask, request, jsonify
import google.generativeai as genai
import requests

app = Flask(__name__)

# Configuración de la IA
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# INSTRUCCIONES DE OKAMA
SYSTEM_INSTRUCTION = (
    "Eres el asistente oficial de Okama, un negocio en San Luis Potosí. "
    "Vendes playeras personalizadas, tote bags, cuadros de aluminio, stickers y vinil. "
    "Eres amable y creativo. Ayuda a los clientes con sus dudas sobre diseños y productos."
)

@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == "Okama_117":
        return request.args.get("hub.challenge")
    return "Error de validación", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    try:
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            message = data['entry'][0]['changes'][0]['value']['messages'][0]
            user_number = message['from']
            user_text = message['text']['body']
            
            # Usamos el modelo con el nombre corregido
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(f"{SYSTEM_INSTRUCTION}\n\nCliente: {user_text}")
            
            send_whatsapp_message(user_number, response.text)
    except Exception as e:
        print(f"Error detectado: {e}")
        
    return "EVENT_RECEIVED", 200

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v18.0/{os.environ.get('PHONE_NUMBER_ID')}/messages"
    headers = {"Authorization": f"Bearer {os.environ.get('WHATSAPP_TOKEN')}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, json=payload, headers=headers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
