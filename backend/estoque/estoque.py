import json
import threading
import pika # type: ignore
from fastapi import FastAPI, HTTPException

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

###################################################################

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

def carregar_estoque_por_id(product_id: int):
    try:
        with open("estoque.json", "r") as file:
            content = file.read().strip()
            if not content:
                raise HTTPException(status_code=204, detail="No content")
            
            estoque = json.loads(content)
            if not isinstance(estoque, list):
                raise HTTPException(
                    status_code=400, 
                    detail="Formato inválido: O estoque deve ser uma lista"
                )
            
            produto = next((item for item in estoque if item.get("id") == product_id), None)
            
            if produto is None:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Produto com ID {product_id} não encontrado"
                )
            
            return produto
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="Erro ao decodificar o JSON"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

def salvar_estoque(estoque):
    with open("estoque.json", "w") as file:
        json.dump(estoque, file, indent=4)

###################################################################

def enviar_evento(evento, queue):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    channel.exchange_declare(exchange='default', exchange_type='topic')

    channel.queue_declare(queue=queue)

    channel.basic_publish(
        exchange='',
        routing_key=queue,
        body=json.dumps(evento)
    )

    print(f"Evento enviado para a fila {queue}: {evento}")
    connection.close()

def callback_pedido_criado(ch, method, properties, body):
    try:
        pedido = json.loads(body)
        print(f"Pedido criado recebido: {pedido}")

        if not all(key in pedido for key in ["id", "client_id", "product_id", "product_name", "quantity", "status"]):
            print("Erro: Formato de pedido inválido.")
            return

        estoque = carregar_estoque()

        product = next((p for p in estoque if p['id'] == pedido['product_id']), None)

        if not product:
            print(f"Erro: Produto com ID {pedido['product_id']} não encontrado no estoque.")
            return

        if product['stock'] >= pedido['quantity']:
            product['stock'] -= pedido['quantity']
            salvar_estoque(estoque)
            print(f"Estoque atualizado após pedido criado: {product}")
        else:
            print(f"Erro: Estoque insuficiente para o produto '{product['name']}' (ID: {product['id']}).")
    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")
    except Exception as e:
        print(f"Erro no callback: {str(e)}")

def callback_pedido_excluido(ch, method, properties, body):
    try:
        pedido = json.loads(body)
        print(f"Pedido criado recebido: {pedido}")

        if not all(key in pedido for key in ["id", "client_id", "product_id", "product_name", "quantity", "status"]):
            print("Erro: Formato de pedido inválido.")
            return

        estoque = carregar_estoque()

        product = next((p for p in estoque if p['id'] == pedido['product_id']), None)

        if product:
            product['stock'] += pedido['quantity']
            salvar_estoque(estoque)
            print(f"Estoque atualizado após pedido criado: {product}")
            return
        else:
            print(f"Erro: Produto com ID {pedido['product_id']} não encontrado no estoque.")
            return
        
    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")
    except Exception as e:
        print(f"Erro no callback: {str(e)}")
        
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
                       queue=criadosNome, routing_key=TOPIC_PEDIDOS_CRIADOS)
    channel.basic_consume(
        queue=criadosNome, on_message_callback=callback_pedido_criado, auto_ack=True)

    channel.queue_bind(exchange='default',
                       queue=excluidosNome, routing_key=TOPIC_PAGAMENTOS_RECUSADOS)
    channel.basic_consume(
        queue=excluidosNome, on_message_callback=callback_pedido_excluido, auto_ack=True)

    print('Aguardando mensagens nas filas. Para sair, pressione CTRL+C.')
    channel.start_consuming()

###################################################################

@app.get("/estoque")
async def consultar_estoque():
    estoque = carregar_estoque()
    return estoque

@app.get("/estoque/{product_id}")
async def get_product_stock(product_id: int):
    product = carregar_estoque_por_id(product_id)
    print(product)
    return product["stock"]
    
@app.on_event("startup")
def start_rabbitmq_consumer():
    threading.Thread(target=consumir_eventos, daemon=True).start()
