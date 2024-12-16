import threading
import pika
import json

from fastapi import FastAPI

app = FastAPI()

RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "admin"
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

QUEUE_PEDIDOS_CRIADOS = 'Pedidos_Criados'
QUEUE_PAGAMENTOS_APROVADOS = 'Pagamentos_Aprovados'

# Função para enviar um evento para o RabbitMQ


def enviar_evento(evento, routing_key):
    # Estabelece conexão com o RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    # Declarar a exchange que será usada
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

# Função que consome as mensagens do RabbitMQ na fila Pedidos_Criados


def callback(ch, method, properties, body):
    print('aaaaaaaaaa')
    try:
        # Recebe os dados do pedido
        pedido = json.loads(body)
        print(f"Pedido recebido para processamento: {pedido}")

        # Lógica de processamento do pagamento (aqui podemos simular como aprovado)
        pagamento_aprovado = {
            "cliente_id": pedido["cliente_id"],
            "produto": pedido["produto"],
            "quantidade": pedido["quantidade"],
            "status": "Aprovado",  # Status do pagamento
            # Gerar ID do pagamento
            "id": f"pgto_{pedido['produto']}_{pedido['cliente_id']}"
        }

        # Enviar evento de pagamento aprovado para a fila Pagamentos_Aprovados
        # Agora você envia para uma exchange com a chave de roteamento apropriada
        enviar_evento(pagamento_aprovado, "pagamento.aprovado")

    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")


def consumir_pedidos():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    result = channel.queue_declare(queue='', exclusive=True)
    selected = result.method.queue
    channel.queue_bind(exchange='default',
                       queue=selected, routing_key=QUEUE_PEDIDOS_CRIADOS)
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
