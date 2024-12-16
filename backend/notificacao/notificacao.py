import threading
import pika
import json
import queue
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

app = FastAPI()

# Configurações do RabbitMQ
RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "admin"
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

# Filas que serão escutadas
FILAS = {
    "Pedidos_Criados": "pedido.criado",
    "Pedidos_Excluídos": "pedido.excluido",
    "Pedidos_Enviados": "pedido.enviado",
    "Pagamentos_Aprovados": "pagamento.aprovado",
    "Pagamentos_Recusados": "pagamento.recusado"
}

# Fila de mensagens para SSE
notificacao_queue = queue.Queue()

# Função para notificar eventos
def notificar_evento(evento, routing_key):
    try:
        print(f"Notificação recebida na chave '{routing_key}': {evento}")

        # Enfileira a notificação para ser enviada via SSE
        notificacao_queue.put({
            "evento": routing_key,
            "dados": evento
        })
    except Exception as e:
        print(f"Erro ao processar a notificação: {str(e)}")

# Callback genérico para processar mensagens de qualquer fila
def callback(ch, method, properties, body):
    try:
        mensagem = json.loads(body)
        print(f"Mensagem recebida da fila '{method.routing_key}': {mensagem}")
        notificar_evento(mensagem, method.routing_key)
    except json.JSONDecodeError:
        print(f"Erro ao decodificar mensagem na fila '{method.routing_key}'.")
    except Exception as e:
        print(f"Erro ao processar mensagem: {str(e)}")

# Consumidor para todas as filas
def consumir_filas():
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

# SSE Generator: Gera mensagens contínuas para o cliente
async def sse_notificacoes():
    while True:
        try:
            # Obtém a próxima notificação da fila
            notificacao = await run_in_threadpool(notificacao_queue.get)
            if notificacao:
                # Envia como evento no formato SSE
                yield f"data: {json.dumps(notificacao)}\n\n"
        except Exception as e:
            print(f"Erro no SSE: {str(e)}")
            break

# Endpoint SSE para enviar notificações ao cliente
@app.get("/notificacoes")
async def notificacoes_sse():
    return StreamingResponse(sse_notificacoes(), media_type="text/event-stream")

# Endpoint raiz para verificar se o serviço está rodando
@app.get("/")
def root():
    return {"message": "Serviço de Notificação com SSE está rodando"}

# Evento de inicialização para iniciar o consumidor em uma thread separada
@app.on_event("startup")
def start_rabbitmq_consumer():
    threading.Thread(target=consumir_filas, daemon=True).start()
