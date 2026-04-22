from flask import Flask, request

app = Flask(__name__)

# Este es tu token de seguridad
VERIFY_TOKEN = "Okama_117"

@app.route('/webhook', methods=['GET'])
def verify():
    # Esta sección es EXCLUSIVA para que Meta valide tu bot
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if token == VERIFY_TOKEN:
        return challenge
    return "Token incorrecto", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    # Aquí es donde el bot recibirá los mensajes reales después
    return "EVENT_RECEIVED", 200

@app.route('/')
def index():
    return "Servidor de Okama: Online y listo."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
