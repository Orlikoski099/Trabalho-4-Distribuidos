import json
import threading
import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "admin"
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

QUEUE_PEDIDOS_CRIADOS = 'Pedidos_Criados'
QUEUE_PEDIDOS_EXCLUIDOS = 'Pedidos_Excluídos'
QUEUE_PEDIDOS_ENVIADOS = 'Pedidos_Enviados'
QUEUE_PAGAMENTOS_APROVADOS = 'Pagamentos_Aprovados'
QUEUE_PAGAMENTOS_RECUSADOS = 'Pagamentos_Recusados'

# Função para carregar o estoque do arquivo JSON


def carregar_estoque():
    try:
        with open("estoque.json", "r") as file:
            content = file.read().strip()
            if not content:
                raise HTTPException(status_code=204, detail="No content")
            return json.loads(content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="Erro ao decodificar o JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

# Função para salvar as alterações no estoque no arquivo JSON


def salvar_estoque(estoque):
    with open("estoque.json", "w") as file:
        json.dump(estoque, file, indent=4)

# Modelo de dados para representar um pedido


class Pedido(BaseModel):
    produto: int
    quantidade: int

# Função para enviar um evento para o RabbitMQ


def enviar_evento(evento, queue):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    # Garante que a fila existe
    channel.queue_declare(queue=queue)

    # Publica o evento na fila
    channel.basic_publish(
        exchange='',
        routing_key=queue,
        body=json.dumps(evento)
    )

    print(f"Evento enviado para a fila {queue}: {evento}")
    connection.close()

# Callback para processar eventos de criação de pedidos


def callback_pedido_criado(ch, method, properties, body):
    try:
        pedido = json.loads(body)
        print(f"Pedido criado recebido: {pedido}")

        # Carrega o estoque, que é um dicionário com a chave 'produtos'
        estoque = carregar_estoque()

        # Busca o produto no estoque pela chave 'id' e pelo 'produto' no pedido
        produto = next(
            (p for p in estoque['produtos'] if p['id'] == pedido['produto']), None)

        if not produto:
            print("Erro: Produto não encontrado.")
            return

        # Verifica se há quantidade suficiente no estoque
        if produto['quantidade'] >= pedido['quantidade']:
            produto['quantidade'] -= pedido['quantidade']
            salvar_estoque(estoque)
            print(f"Estoque atualizado após pedido criado: {produto}")
        else:
            print("Erro: Quantidade insuficiente no estoque.")
    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")

# Callback para processar eventos de exclusão de pedidos


def callback_pedido_excluido(ch, method, properties, body):
    try:
        pedido = json.loads(body)
        print(f"Pedido excluído recebido: {pedido}")

        estoque = carregar_estoque()
        produto = next(
            (p for p in estoque['produtos'] if p['id'] == pedido['produto']), None)

        if produto:
            produto['quantidade'] += pedido['quantidade']
            salvar_estoque(estoque)
            print(f"Estoque atualizado após pedido excluído: {produto}")
        else:
            print("Erro: Produto não encontrado.")
    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")

# Função para iniciar o consumidor de eventos


def consumir_eventos():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    criados = channel.queue_declare(queue='', exclusive=True)
    excluidos = channel.queue_declare(queue='', exclusive=True)

    criadosNome = criados.method.queue
    excluidosNome = excluidos.method.queue

    channel.queue_bind(exchange='default',
                       queue=criadosNome, routing_key=QUEUE_PEDIDOS_CRIADOS)
    channel.basic_consume(
        queue=criadosNome, on_message_callback=callback_pedido_criado, auto_ack=True)

    channel.queue_bind(exchange='default',
                       queue=excluidosNome, routing_key=QUEUE_PEDIDOS_EXCLUIDOS)
    channel.basic_consume(
        queue=excluidosNome, on_message_callback=callback_pedido_criado, auto_ack=True)

    print('Aguardando mensagens nas filas. Para sair, pressione CTRL+C.')
    channel.start_consuming()

# Endpoint para criar um pedido


@app.post("/pedido/criar")
async def criar_pedido(pedido: Pedido):
    estoque = carregar_estoque()
    produto = next(
        (p for p in estoque['produtos'] if p['id'] == pedido.produto), None)

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    if produto['quantidade'] < pedido.quantidade:
        raise HTTPException(
            status_code=400, detail="Quantidade insuficiente no estoque.")

    produto['quantidade'] -= pedido.quantidade
    salvar_estoque(estoque)

    enviar_evento(pedido.dict(), QUEUE_PEDIDOS_CRIADOS)

    return {"message": "Pedido criado com sucesso", "produto": produto}

# Endpoint para excluir um pedido


@app.post("/pedido/excluir")
async def excluir_pedido(pedido: Pedido):
    estoque = carregar_estoque()
    produto = next(
        (p for p in estoque['produtos'] if p['id'] == pedido.produto), None)

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    produto['quantidade'] += pedido.quantidade
    salvar_estoque(estoque)

    enviar_evento(pedido.dict(), QUEUE_PEDIDOS_EXCLUIDOS)

    return {"message": "Pedido excluído com sucesso", "produto": produto}

###################################################################

# Endpoint para consultar o estoque


@app.get("/estoque")
async def consultar_estoque():
    estoque = carregar_estoque()
    return estoque


@app.on_event("startup")
def start_rabbitmq_consumer():
    threading.Thread(target=consumir_eventos, daemon=True).start()
