import threading
import httpx
import pika # type: ignore
import json

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

NOTIFICACAO_SERVICE_URL = 'http://notificacao:8000'


def enviar_evento(evento, routing_key):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

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

        pagamento_aprovado = {
            "cliente_id": pedido["cliente_id"],
            "produto": pedido["produto"],
            "quantidade": pedido["quantidade"],
            "status": "Aprovado",
            "id": f"pgto_{pedido['produto']}_{pedido['cliente_id']}"
        }

        enviar_evento(pagamento_aprovado, TOPIC_PAGAMENTOS_APROVADOS)

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
