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

# Modelo de produto com base na interface Products
class Produto(BaseModel):
    id: int
    name: str
    originalStock: int
    inStock: int
    quantity: int

# Modelo de Pedido
class Pedido(BaseModel):
    id: Optional[int]
    cliente_id: int
    produto: str
    quantidade: int
    status: Optional[str]  # 'pendente', 'aprovado', 'recusado'


def enviar_evento(evento: dict, routing_key: str):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    
    channel.exchange_declare(exchange='default', exchange_type='topic')
    
    channel.basic_publish(exchange='default', routing_key=routing_key, body=json.dumps(evento))
    
    connection.close()

def consumir_eventos():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        channel.exchange_declare(exchange='default', exchange_type='topic')
        
        result_1 = channel.queue_declare(queue='', exclusive=True)
        result_2 = channel.queue_declare(queue='', exclusive=True)
        result_3 = channel.queue_declare(queue='', exclusive=True)

        selected_1 = result_1.method.queue
        selected_2 = result_2.method.queue
        selected_3 = result_3.method.queue

        channel.queue_bind(exchange='default', queue=selected_1, routing_key=TOPIC_PAGAMENTOS_APROVADOS)
        channel.queue_bind(exchange='default', queue=selected_2, routing_key=TOPIC_PAGAMENTOS_RECUSADOS)
        channel.queue_bind(exchange='default', queue=selected_3, routing_key=TOPIC_PEDIDOS_ENVIADOS)

        def callback(ch, method, properties, body):
            evento = json.loads(body)
            if method.routing_key == TOPIC_PAGAMENTOS_APROVADOS:
                print(f"Pagamento aprovado para pedido {evento['pedido_id']}")
            elif method.routing_key == TOPIC_PAGAMENTOS_RECUSADOS:
                print(f"Pagamento recusado para pedido {evento['pedido_id']}")
            elif method.routing_key == TOPIC_PEDIDOS_ENVIADOS:
                print(f"Pedido {evento['pedido_id']} enviado")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(
            queue=selected_1, on_message_callback=callback, auto_ack=True)
        
        channel.basic_consume(
            queue=selected_2, on_message_callback=callback, auto_ack=True)
        
        channel.basic_consume(
            queue=selected_3, on_message_callback=callback, auto_ack=True)

        print("Esperando por eventos. Pressione Ctrl+C para sair.")
        channel.start_consuming()

    except Exception as e:
        print(f"Erro ao consumir eventos: {e}")

def ler_carrinho():
    if not os.path.exists(CARRINHO_FILE_PATH):
        # Caso o arquivo não exista, cria um arquivo vazio
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
        # Caso o arquivo não exista, cria um arquivo vazio
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

@app.get("/")
async def root():
    return {"message": "CORS configurado para localhost"}

###################################################################

@app.get("/produtos")
async def listar_produtos():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f'{ESTOQUE_SERVICE_URL}/estoque')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Erro ao obter produtos do estoque")
    
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão com o serviço de estoque: {str(e)}")
    
###################################################################

# Rota GET para obter todos os produtos do carrinho
@app.get("/carrinho", response_model=List[Produto])
async def listar_carrinho():
    carrinho = ler_carrinho()
    return carrinho

@app.post("/carrinho", response_model=Produto)
async def adicionar_ao_carrinho(produto: Produto):
    carrinho = ler_carrinho()

    for item in carrinho:
        if item["id"] == produto.id:
            item["quantity"]
            item["inStock"]
            salvar_carrinho(carrinho)
            return item
    
    carrinho.append({
        "id": produto.id,
        "name": produto.name,
        "originalStock": produto.originalStock,
        "inStock": produto.originalStock - produto.quantity,  # Subtrai do estoque
        "quantity": produto.quantity
    })
    salvar_carrinho(carrinho)
    return carrinho[-1]

# Rota PATCH para atualizar a quantidade de um produto no carrinho
@app.patch("/carrinho/{produto_id}/{quantity}", response_model=Produto)
async def atualizar_quantidade(produto_id: int, quantity: int):
    carrinho = ler_carrinho()
    
    for item in carrinho:
        if item["id"] == produto_id:
            if quantity <= 0:
                raise HTTPException(status_code=400, detail="Quantidade deve ser maior que zero.")
            item["quantity"] = quantity
            item["inStock"] = item["originalStock"] - item["quantity"]  # Atualiza o estoque disponível
            salvar_carrinho(carrinho)
            return item
    
    raise HTTPException(status_code=404, detail="Produto não encontrado no carrinho.")

# Rota DELETE para remover um produto do carrinho
@app.delete("/carrinho/{produto_id}")
async def remover_produto(produto_id: int):
    carrinho = ler_carrinho()
    
    carrinho = [item for item in carrinho if item["id"] != produto_id]
    
    if len(carrinho) == len(ler_carrinho()):
        raise HTTPException(status_code=404, detail="Produto não encontrado no carrinho.")
    
    salvar_carrinho(carrinho)
    return {"mensagem": f"Produto {produto_id} removido do carrinho."}

###################################################################

# Rota para criar um pedido
@app.post("/pedidos", response_model=Pedido)
async def criar_pedido(pedido: Pedido):
    if pedido.quantidade <= 0:
        raise HTTPException(status_code=400, detail="A quantidade do produto deve ser maior que zero.")
    
    pedidos = ler_pedidos()

    # Gerar um ID único para o pedido (baseado na quantidade de pedidos existentes)
    novo_id = len(pedidos) + 1

    # Criar o pedido com o ID gerado
    pedido_criado = Pedido(
        id=novo_id,
        cliente_id=pedido.cliente_id,
        produto=pedido.produto,
        quantidade=pedido.quantidade,
        status="pendente"  # Definindo status inicial como "pendente"
    )

    pedidos.append(pedido_criado.dict())

    salvar_pedidos(pedidos)

    evento_pedido = {
        "cliente_id": pedido.cliente_id,
        "produto": pedido.produto,
        "quantidade": pedido.quantidade,
        "status": 'Criado'
    }
    enviar_evento(evento_pedido, TOPIC_PEDIDOS_CRIADOS)
    
    #Acordando o microserviço de notificações
    async with httpx.AsyncClient() as client:
        response = await client.get(f'{NOTIFICACAO_SERVICE_URL}/')
        print(response)

    #Acordando o microserviço de pagamentos
    async with httpx.AsyncClient() as client:
        response = await client.get(f'{PAGAMENTO_SERVICE_URL}/')
        print(response)

        #Acordando o microserviço de entrega
    async with httpx.AsyncClient() as client:
        response = await client.get(f'{ENTREGA_SERVICE_URL}/')
        print(response)

    return pedido_criado


# Rota GET para obter todos os pedidos
@app.get("/pedidos", response_model=List[Pedido])
async def listar_carrinho():
    pedidos = ler_pedidos()
    return pedidos

# Função de inicialização para consumir eventos
@app.on_event("startup")
async def iniciar_consumo_de_eventos():
    import threading
    thread = threading.Thread(target=consumir_eventos, daemon=True)
    thread.start()