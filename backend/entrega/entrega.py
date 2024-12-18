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

# Filas que serão escutadas
FILAS = {
    "Pagamentos_Aprovados": TOPIC_PAGAMENTOS_APROVADOS,
}

# Função para enviar um evento para o RabbitMQ
def enviar_evento(evento, routing_key):
    # Estabelece conexão com o RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    # Publica o evento na exchange com a chave de roteamento
    channel.basic_publish(
        exchange='default',  # Usando a exchange 'default'
        routing_key=routing_key,  # Usando a chave de roteamento
        body=json.dumps(evento)
    )

    print(
        f"Evento enviado para a exchange 'default' com chave {routing_key}: {evento}")
    connection.close()


def callback(ch, method, properties, body):
    try:
        # Recebe os dados do pedido
        pedido = json.loads(body)
        print(f"Pedido recebido para processamento: {pedido}")

        # Validação do formato do pedido
        if not all(key in pedido for key in ["id", "client_id", "product_id", "product_name", "quantity", "status"]):
            print("Erro: Formato de pedido inválido.")
            return

        # Atualiza o status para "enviado" e monta os dados atualizados do pedido
        pedido_enviado = {
            "id": pedido["id"],
            "client_id": pedido["client_id"],
            "product_id": pedido["product_id"],
            "product_name": pedido["product_name"],
            "quantity": pedido["quantity"],
            "status": "enviado",  # Atualiza o status para "enviado"
        }

        # Introduz um delay de 5 segundos antes de enviar o evento
        print("Aguardando 5 segundos antes de enviar o evento...")
        time.sleep(5)

        # Envia o evento de pedido "enviado" para a fila TOPIC_PEDIDOS_ENVIADOS
        enviar_evento(pedido_enviado, TOPIC_PEDIDOS_ENVIADOS)
        print(f"Pedido enviado com sucesso para a fila: {TOPIC_PEDIDOS_ENVIADOS}")

    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")
    except Exception as e:
        print(f"Erro inesperado: {e}")


# Função que consome as mensagens da fila de pagamentos aprovados
def consumir_pedidos():
    try:
        # Conexão com RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST, credentials=CREDENTIALS))
        channel = connection.channel()
        channel.exchange_declare(exchange='default', exchange_type='topic')

        # Vincular filas e consumir mensagens
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


@app.get("/")
def root():
    return {"message": "O serviço de entrega está rodando"}


@app.on_event("startup")
def start_rabbitmq_consumer():
    threading.Thread(target=consumir_pedidos, daemon=True).start()
