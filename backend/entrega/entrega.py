import threading
import pika  # type: ignore
import json
import time  # Para introduzir o delay

from fastapi import FastAPI

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

FILAS = {
    "Pagamentos_Aprovados": TOPIC_PAGAMENTOS_APROVADOS,
}

###################################################################

def enviar_evento(evento, routing_key):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

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
        pedido = json.loads(body)
        print(f"Pedido recebido para processamento: {pedido}")

        if not all(key in pedido for key in ["id", "client_id", "product_id", "product_name", "quantity", "status"]):
            print("Erro: Formato de pedido inválido.")
            return

        pedido_enviado = {
            "id": pedido["id"],
            "client_id": pedido["client_id"],
            "product_id": pedido["product_id"],
            "product_name": pedido["product_name"],
            "quantity": pedido["quantity"],
            "status": "enviado", 
        }

        # Introduz um delay de 5 segundos antes de enviar o evento
        print("Aguardando 5 segundos antes de enviar o evento...")
        time.sleep(5)

        enviar_evento(pedido_enviado, TOPIC_PEDIDOS_ENVIADOS)
        print(f"Pedido enviado com sucesso para a fila: {TOPIC_PEDIDOS_ENVIADOS}")

    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")
    except Exception as e:
        print(f"Erro inesperado: {e}")

def consumir_pedidos():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST, credentials=CREDENTIALS))
        channel = connection.channel()
        channel.exchange_declare(exchange='default', exchange_type='topic')

        for fila, routing_key in FILAS.items():
            result = channel.queue_declare(queue='', exclusive=True)
            fila_temporaria = result.method.queue
            channel.queue_bind(exchange='default',
                               queue=fila_temporaria, routing_key=routing_key)

            channel.basic_consume(
                queue=fila_temporaria, on_message_callback=callback, auto_ack=True
            )

            print(f"Consumindo mensagens da fila: {fila} (chave: {routing_key})")

        print("Aguardando mensagens de todas as filas. Para sair pressione CTRL+C")
        channel.start_consuming()
        
    except Exception as e:
        print(f"Erro ao configurar o consumidor: {str(e)}")

###################################################################

@app.get("/")
def root():
    return {"message": "O serviço de entrega está rodando"}

@app.on_event("startup")
def start_rabbitmq_consumer():
    threading.Thread(target=consumir_pedidos, daemon=True).start()
