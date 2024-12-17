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


# Função que consome as mensagens do RabbitMQ na fila Pagamentos_Aprovados
def callback(ch, method, properties, body):
    try:
        # Recebe os dados do pedido
        pedido = json.loads(body)
        print(f"Pedido recebido para processamento: {pedido}")

        # Lógica de processamento do pagamento (aqui podemos simular como aprovado)
        pedido_enviado = {
            "cliente_id": pedido["cliente_id"],
            "produto": pedido["produto"],
            "quantidade": pedido["quantidade"],
            "status": "Enviado", 
            "id": f"pgto_{pedido['produto']}_{pedido['cliente_id']}"
        }

        # Introduz um delay de 5 segundos antes de enviar o evento
        print("Aguardando 5 segundos antes de enviar o evento...")
        time.sleep(5)

        # Enviar evento de pagamento aprovado para a fila Pedidos_Enviados
        enviar_evento(pedido_enviado, TOPIC_PEDIDOS_ENVIADOS)

    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")


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
