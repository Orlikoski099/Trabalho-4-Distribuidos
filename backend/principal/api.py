import os
import pika # type: ignore
import json
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

RABBITMQ_HOST = 'rabbitmq' 
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "admin"
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

TOPIC_PEDIDOS_CRIADOS = 'pedidos.criados'
TOPIC_PEDIDOS_EXCLUIDOS = 'pedidos.excluídos'
TOPIC_PEDIDOS_ENVIADOS = 'pedidos.enviados'
TOPIC_PAGAMENTOS_APROVADOS = 'pagamentos.aprovados'
TOPIC_PAGAMENTOS_RECUSADOS = 'pagamentos.recusados'

ESTOQUE_SERVICE_URL = 'http://estoque:8000'
NOTIFICACAO_SERVICE_URL = 'http://notificacao:8000'
ENTREGA_SERVICE_URL = 'http://entrega:8000'
PAGAMENTO_SERVICE_URL = 'http://pagamento:8000'

CARRINHO_FILE_PATH = "carrinho.json"
PEDIDOS_FILE_PATH = 'pedidos.json'

# Modelo do Produto
class Produto(BaseModel):
    id: int
    name: str
    stock: int

# Modelo do Carrinho
class Carrinho(BaseModel):
    client_id: int
    product_name: str
    product_id: int
    available_stock: Optional[int] = None  
    quantity: int

# Modelo de Pedido
class Pedido(BaseModel):
    id: Optional[int]
    client_id: int
    product_id: int
    product_name: str
    quantity: int
    status: Optional[str]  # 'pendente', 'aprovado', 'recusado'

###################################################################

def enviar_evento(evento: dict, routing_key: str):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    
    channel.exchange_declare(exchange='default', exchange_type='topic')
    
    channel.basic_publish(exchange='default', routing_key=routing_key, body=json.dumps(evento))
    
    connection.close()

def consumir_eventos():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=CREDENTIALS))
        channel = connection.channel()

        channel.exchange_declare(exchange='default', exchange_type='topic')

        result_pagamentos_aprovados = channel.queue_declare(queue='', exclusive=True)
        result_pagamentos_recusados = channel.queue_declare(queue='', exclusive=True)
        result_pedidos_enviados = channel.queue_declare(queue='', exclusive=True)

        fila_pagamentos_aprovados = result_pagamentos_aprovados.method.queue
        fila_pagamentos_recusados = result_pagamentos_recusados.method.queue
        fila_pedidos_enviados = result_pedidos_enviados.method.queue

        channel.queue_bind(exchange='default', queue=fila_pagamentos_aprovados, routing_key=TOPIC_PAGAMENTOS_APROVADOS)
        channel.queue_bind(exchange='default', queue=fila_pagamentos_recusados, routing_key=TOPIC_PAGAMENTOS_RECUSADOS)
        channel.queue_bind(exchange='default', queue=fila_pedidos_enviados, routing_key=TOPIC_PEDIDOS_ENVIADOS)

        def callback(ch, method, properties, body):
            try:
                evento = json.loads(body)
                print(f"Evento recebido na fila '{method.routing_key}': {evento}")

                if method.routing_key == TOPIC_PAGAMENTOS_APROVADOS:
                    print(f"Atualizando status do pedido {evento['id']} para 'aprovado'")
                    evento["status"] = "aprovado"
                    atualizar_pedido(evento)

                elif method.routing_key == TOPIC_PAGAMENTOS_RECUSADOS:
                    print(f"Atualizando status do pedido {evento['id']} para 'recusado'")
                    evento["status"] = "recusado"
                    atualizar_pedido(evento)

                elif method.routing_key == TOPIC_PEDIDOS_ENVIADOS:
                    print(f"Atualizando status do pedido {evento['id']} para 'enviado'")
                    evento["status"] = "enviado"
                    atualizar_pedido(evento)

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except json.JSONDecodeError:
                print("Erro ao decodificar o evento recebido.")
            except Exception as e:
                print(f"Erro ao processar evento: {e}")

        channel.basic_consume(queue=fila_pagamentos_aprovados, on_message_callback=callback)
        channel.basic_consume(queue=fila_pagamentos_recusados, on_message_callback=callback)
        channel.basic_consume(queue=fila_pedidos_enviados, on_message_callback=callback)

        print("Esperando por eventos. Pressione Ctrl+C para sair.")
        channel.start_consuming()

    except Exception as e:
        print(f"Erro ao consumir eventos: {e}")

def ler_carrinho():
    if not os.path.exists(CARRINHO_FILE_PATH):
        with open(CARRINHO_FILE_PATH, 'w') as file:
            json.dump([], file)
        print(f"Arquivo {CARRINHO_FILE_PATH} criado com carrinho vazio.") 
        return [] 
    with open(CARRINHO_FILE_PATH, 'r') as file:
        try:
            carrinho = json.load(file)
            print(f"Carrinho carregado: {carrinho}")
            return carrinho
        except json.JSONDecodeError:
            print(f"Erro ao decodificar JSON no arquivo {CARRINHO_FILE_PATH}. Retornando carrinho vazio.")
            return [] 
        
def salvar_carrinho(carrinho):
    try:
        with open(CARRINHO_FILE_PATH, 'w') as file:
            json.dump(carrinho, file, indent=4)
            print(f"Carrinho salvo com sucesso em {CARRINHO_FILE_PATH}.") 
    except Exception as e:
        print(f"Erro ao salvar o carrinho no arquivo {CARRINHO_FILE_PATH}: {e}")

def ler_pedidos() -> List[dict]:
    if not os.path.exists(PEDIDOS_FILE_PATH):
        with open(PEDIDOS_FILE_PATH, 'w') as file:
            json.dump([], file)
        print(f"Arquivo {PEDIDOS_FILE_PATH} criado com pedidos vazios.") 
        return [] 

    with open(PEDIDOS_FILE_PATH, 'r') as file:
        try:
        
            pedidos = json.load(file)
            print(f"Pedidos carregados: {pedidos}") 
            return pedidos
        except json.JSONDecodeError:
        
            print(f"Erro ao decodificar JSON no arquivo {PEDIDOS_FILE_PATH}. Retornando pedidos vazios.")
            return [] 

def salvar_pedidos(pedidos: List[dict]):
    try:
        with open(PEDIDOS_FILE_PATH, 'w') as file:
            json.dump(pedidos, file, indent=4)
            print(f"Pedidos salvos com sucesso em {PEDIDOS_FILE_PATH}.") 
    except Exception as e:
        print(f"Erro ao salvar os pedidos no arquivo {PEDIDOS_FILE_PATH}: {e}") 

def atualizar_pedido(evento: dict):
    try:
        pedidos = ler_pedidos()

        pedido_encontrado = False
        for pedido in pedidos:
            if pedido["id"] == evento["id"]:
                pedido["status"] = evento["status"]
                pedido_encontrado = True
                print(f"Pedido {evento['id']} atualizado para status '{evento['status']}'.")

        if not pedido_encontrado:
            pedidos.append(evento)
            print(f"Novo pedido {evento['id']} adicionado com status '{evento['status']}'.")

        salvar_pedidos(pedidos)

    except Exception as e:
        print(f"Erro ao atualizar pedido: {e}")
    
###################################################################

@app.get("/")
async def root():
    return {"message": "CORS configurado para localhost"}

###################################################################

@app.get("/produtos")
async def listar_products():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f'{ESTOQUE_SERVICE_URL}/estoque')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Erro ao obter products do estoque")
    
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão com o serviço de estoque: {str(e)}")
    
###################################################################

@app.get("/carrinho", response_model=List[Carrinho])
async def listar_carrinho():
    carrinho = ler_carrinho()

    async with httpx.AsyncClient() as client:
        for item in carrinho:
            try:
                response = await client.get(f"{ESTOQUE_SERVICE_URL}/estoque/{item['product_id']}")
                response.raise_for_status()
                estoque_data = response.json()
                
                item["available_stock"] = estoque_data
            except httpx.HTTPStatusError as e:
                print(f"Erro ao buscar estoque para o produto {item['product_id']}: {e}")
                item["available_stock"] = 0 

    return carrinho

@app.post("/carrinho", response_model=Carrinho)
async def adicionar_ao_carrinho(novo_item: Carrinho):
    carrinho = ler_carrinho()

    for item in carrinho:
        if item["product_id"] == novo_item.product_id and item["client_id"] == novo_item.client_id:
            item["quantity"] += novo_item.quantity
            salvar_carrinho(carrinho)
            return item
    
    carrinho.append({
        "client_id": novo_item.client_id,
        "product_name": novo_item.product_name,
        "product_id": novo_item.product_id,
        "quantity": novo_item.quantity,
    })
    salvar_carrinho(carrinho)
    return carrinho[-1]

@app.patch("/carrinho/{client_id}/{product_id}/{quantity}", response_model=Carrinho)
async def atualizar_quantity(client_id: int, product_id: int, quantity: int):
    carrinho = ler_carrinho()
    
    for item in carrinho:
        if item["client_id"] == client_id and item["product_id"] == product_id:
            if quantity <= 0:
                raise HTTPException(status_code=400, detail="Quantidade deve ser maior que zero.")
                        
            item["quantity"] = quantity
            salvar_carrinho(carrinho)
            return item
    
    raise HTTPException(status_code=404, detail="Produto não encontrado no carrinho.")

@app.delete("/carrinho/{client_id}/{product_id}")
async def remover_product(client_id: int, product_id: int):
    carrinho = ler_carrinho()
    
    novo_carrinho = [item for item in carrinho if not (item["client_id"] == client_id and item["product_id"] == product_id)]
    
    if len(novo_carrinho) == len(carrinho):
        raise HTTPException(status_code=404, detail="Produto não encontrado no carrinho.")
    
    salvar_carrinho(novo_carrinho)
    return {"mensagem": f"Produto {product_id} removido do carrinho do cliente {client_id}."}

###################################################################

@app.post("/pedidos", response_model=Pedido)
async def criar_pedido(pedido: Pedido):
    if pedido.quantity <= 0:
        raise HTTPException(status_code=400, detail="A quantidade do produto deve ser maior que zero.")
    
    pedidos = ler_pedidos()

    novo_id = len(pedidos) + 1

    pedido_criado = Pedido(
        id=novo_id,
        client_id=pedido.client_id,
        product_id=pedido.product_id,
        product_name=pedido.product_name,
        quantity=pedido.quantity,
        status="pendente"
    )

    pedidos.append(pedido_criado.dict())

    salvar_pedidos(pedidos)

    evento_pedido = {
        "id": pedido_criado.id,
        "client_id": pedido_criado.client_id,
        "product_id": pedido_criado.product_id,
        "product_name": pedido_criado.product_name,
        "quantity": pedido_criado.quantity,
        "status": "criado"
    }
    enviar_evento(evento_pedido, TOPIC_PEDIDOS_CRIADOS)
    
    # Acordar os microserviços relacionados
    urls = [NOTIFICACAO_SERVICE_URL, PAGAMENTO_SERVICE_URL, ENTREGA_SERVICE_URL]
    async with httpx.AsyncClient() as client:
        for url in urls:
            response = await client.get(f'{url}/')
            print(response)

    return pedido_criado

# Rota GET para obter todos os pedidos
@app.get("/pedidos", response_model=List[Pedido])
async def listar_pedidos():
    pedidos = ler_pedidos()
    return pedidos

###################################################################

@app.on_event("startup")
async def iniciar_consumo_de_eventos():
    import threading
    thread = threading.Thread(target=consumir_eventos, daemon=True)
    thread.start()