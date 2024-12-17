import threading
import time
import httpx
import pika # type: ignore
import json
from fastapi import FastAPI
import requests

# URL do webhook do sistema de pagamento

app = FastAPI()

RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "admin"
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

TOPIC_PEDIDOS_CRIADOS = 'pedidos.criados'
TOPIC_PEDIDOS_EXCLUIDOS = 'pedidos.excluídos'
TOPIC_PEDIDOS_ENVIADOS = 'pedidos.enviados'
TOPIC_PAGAMENTOS_APROVADOS = 'pagamentos.aprovados'
TOPIC_PAGAMENTOS_RECUSADOS = 'pagamentos.recusados'

WEBHOOK_URL = "http://sistemapgto:8000/webhook/pagamento"

def enviar_evento(evento, routing_key):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    channel.exchange_declare(exchange='default', exchange_type='topic')

    # Introduz um delay de 5 simulando loading do pgto
    print("Aguardando 5 segundos antes de enviar o evento...")
    time.sleep(5)

    channel.basic_publish(
        exchange='default', 
        routing_key=routing_key, 
        body=json.dumps(evento)
    )

    print(
        f"Evento enviado para a exchange 'default' com chave {routing_key}: {evento}")
    connection.close()



def callback(ch, method, properties, body):
    try:
        # Decodifica os dados do pedido
        pedido = json.loads(body)
        print(f"Pedido recebido para processamento: {pedido}")
        
        # Monta os dados para o sistema de pagamento
        dados_pagamento = {
            "transacao_id": f"pgto_{pedido['produto']}_{pedido['cliente_id']}",
            "cliente_id": pedido["cliente_id"],
            "produto": pedido["produto"],
            "quantidade": pedido["quantidade"],
        }

        print(dados_pagamento)
        
        # Envia a requisição para o webhook do sistema de pagamento
        response = requests.post(WEBHOOK_URL, json=dados_pagamento)
        
        if response.status_code == 200:
            resposta_pagamento = response.json()
            print(f"Resposta do sistema de pagamento: {resposta_pagamento}")
            
            # Verifica o status do pagamento retornado pelo webhook
            if resposta_pagamento["status"] == "aprovado":
                pagamento_aprovado = {
                    "cliente_id": pedido["cliente_id"],
                    "produto": pedido["produto"],
                    "quantidade": pedido["quantidade"],
                    "status": "Aprovado",
                    "id": resposta_pagamento["transacao_id"]
                }
                enviar_evento(pagamento_aprovado, TOPIC_PAGAMENTOS_APROVADOS)
            else:
                pagamento_recusado = {
                    "cliente_id": pedido["cliente_id"],
                    "produto": pedido["produto"],
                    "quantidade": pedido["quantidade"],
                    "status": "Recusado",
                    "id": resposta_pagamento["transacao_id"]
                }
                enviar_evento(pagamento_recusado, TOPIC_PAGAMENTOS_RECUSADOS)
        else:
            print(f"Erro ao conectar com o webhook. Código {response.status_code}")

    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")
    except Exception as e:
        print(f"Erro inesperado: {e}")


def consumir_pedidos():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    result = channel.queue_declare(queue='', exclusive=True)
    selected = result.method.queue
    channel.queue_bind(exchange='default',
                       queue=selected, routing_key=TOPIC_PEDIDOS_CRIADOS)
    channel.basic_consume(
        queue=selected, on_message_callback=callback, auto_ack=True)

    print('Aguardando mensagens na fila Pedidos_Criados. Para sair pressione CTRL+C')
    channel.start_consuming()


@app.get("/")
def root():
    return {"message": "O consumidor está rodando"}


@app.on_event("startup")
def start_rabbitmq_consumer():
    threading.Thread(target=consumir_pedidos, daemon=True).start()
