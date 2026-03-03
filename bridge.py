import json
import asyncio
import re
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import websockets

# --- CONFIGURATION AWS ---
ENDPOINT = "a1cld6os4v3nbx-ats.iot.ca-central-1.amazonaws.com"
CLIENT_ID = "TwinCAT_Bridge_Server"
PATH_TO_CERT = r"C:\Certificates\12eb4d73ded626e2b02f727a4e27a6088985d2f28b2491f4c8370c7602d757d0-certificate.pem.crt"
PATH_TO_KEY = r"C:\Certificates\12eb4d73ded626e2b02f727a4e27a6088985d2f28b2491f4c8370c7602d757d0-private.pem.key"
PATH_TO_ROOT = r"C:\Certificates\AmazonRootCA1.pem"
TOPIC = "Finish_Door"

web_clients = set()
loop = None

# Callback appelé quand AWS envoie un message
def on_aws_message(client, userdata, message):
    global loop
    raw_payload = message.payload.decode('utf-8').strip('\x00').strip()
    
    # Nettoyage pour le JSON (Gestion TRUE/FALSE de TwinCAT)
    payload = re.sub(r'\bTRUE\b', 'true', raw_payload, flags=re.IGNORECASE)
    payload = re.sub(r'\bFALSE\b', 'false', payload, flags=re.IGNORECASE)
    
    print(f"AWS IoT -> Bridge: {payload}")

    # Envoi vers ton index.html (WebSocket local)
    if web_clients and loop:
        for ws_client in list(web_clients):
            try:
                asyncio.run_coroutine_threadsafe(ws_client.send(payload), loop)
            except Exception as e:
                print(f"Erreur d'envoi WebSocket: {e}")

# --- CONFIGURATION DU SERVEUR WEBSOCKET (Pour index.html) ---
async def handle_client(websocket):
    web_clients.add(websocket)
    print(f"HTML connecté au pont. Total: {len(web_clients)}")
    try:
        async for message in websocket:
            pass 
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        web_clients.discard(websocket)
        print(f"HTML déconnecté. Total: {len(web_clients)}")

# --- INITIALISATION AWS IOT ---
aws_client = AWSIoTMQTTClient(CLIENT_ID)
aws_client.configureEndpoint(ENDPOINT, 8883)
aws_client.configureCredentials(PATH_TO_ROOT, PATH_TO_KEY, PATH_TO_CERT)

# Paramètres de connexion robustes
aws_client.configureAutoReconnectBackoffTime(1, 32, 20)
aws_client.configureOfflinePublishQueueing(-1)
aws_client.configureDrainingFrequency(2)
aws_client.configureConnectDisconnectTimeout(10)
aws_client.configureMQTTOperationTimeout(5)

print("Connexion à AWS IoT Core...")
aws_client.connect()
aws_client.subscribe(TOPIC, 1, on_aws_message)
print(f"Abonné au topic AWS: {TOPIC}")

async def main():
    async with websockets.serve(handle_client, '0.0.0.0', 1884, reuse_address=True):
        print("Pont AWS <-> HTML actif sur ws://localhost:1884")
        await asyncio.Future() # Maintient le serveur actif

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Arrêt du pont...")
        aws_client.disconnect()
