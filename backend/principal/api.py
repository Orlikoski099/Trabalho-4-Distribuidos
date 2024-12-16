import os
import pika
import json
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

# Instância principal do FastAPI
app = FastAPI()

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite qualquer origem (CUIDADO EM PRODUÇÃO)
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos HTTP
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

# Configurações do RabbitMQ
RABBITMQ_HOST = 'rabbitmq' 
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "admin"
CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

QUEUE_PEDIDOS_CRIADOS = 'Pedidos_Criados'
QUEUE_PEDIDOS_EXCLUIDOS = 'Pedidos_Excluídos'
QUEUE_PEDIDOS_ENVIADOS = 'Pedidos_Enviados'
QUEUE_PAGAMENTOS_APROVADOS = 'Pagamentos_Aprovados'
QUEUE_PAGAMENTOS_RECUSADOS = 'Pagamentos_Recusados'


ESTOQUE_SERVICE_URL = 'http://estoque:8000'
NOTIFICACAO_SERVICE_URL = 'http://notificacao:8000'
ENTREGA_SERVICE_URL = 'http://entrega:8000'
PAGAMENTO_SERVICE_URL = 'http://pagamento:8000'

CARRINHO_FILE_PATH = "carrinho.json"
PEDIDOS_FILE_PATH = 'pedidos.json'

# Definindo o modelo de produto com base na interface Products
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


# Função para enviar eventos para o RabbitMQ
def enviar_evento(evento: dict, routing_key: str):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=CREDENTIALS))
    channel = connection.channel()
    
    # Declarar a exchange, por exemplo, do tipo "topic"
    channel.exchange_declare(exchange='default', exchange_type='topic')
    
    # Publicar a mensagem na exchange com a chave de roteamento
    channel.basic_publish(exchange='default', routing_key=routing_key, body=json.dumps(evento))
    
    connection.close()

def consumir_eventos():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Declarar a exchange que será usada
        channel.exchange_declare(exchange='default', exchange_type='topic')
        
        # Declarar as filas que o serviço irá consumir
        result_1 = channel.queue_declare(queue='', exclusive=True)
        result_2 = channel.queue_declare(queue='', exclusive=True)
        result_3 = channel.queue_declare(queue='', exclusive=True)

        selected_1 = result_1.method.queue
        selected_2 = result_2.method.queue
        selected_3 = result_3.method.queue


        # Vincular as filas à exchange com suas respectivas chaves de roteamento
        channel.queue_bind(exchange='default', queue=selected_1, routing_key=QUEUE_PAGAMENTOS_APROVADOS)
        channel.queue_bind(exchange='default', queue=selected_2, routing_key=QUEUE_PAGAMENTOS_RECUSADOS)
        channel.queue_bind(exchange='default', queue=selected_3, routing_key=QUEUE_PEDIDOS_ENVIADOS)

        # Função de callback para processar os eventos
        def callback(ch, method, properties, body):
            evento = json.loads(body)
            if method.routing_key == QUEUE_PAGAMENTOS_APROVADOS:
                print(f"Pagamento aprovado para pedido {evento['pedido_id']}")
            elif method.routing_key == QUEUE_PAGAMENTOS_RECUSADOS:
                print(f"Pagamento recusado para pedido {evento['pedido_id']}")
            elif method.routing_key == QUEUE_PEDIDOS_ENVIADOS:
                print(f"Pedido {evento['pedido_id']} enviado")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)

        # Consumir os eventos
        channel.basic_consume(
            queue=selected_1, on_message_callback=callback, auto_ack=True)
        # Consumir os eventos
        channel.basic_consume(
            queue=selected_2, on_message_callback=callback, auto_ack=True)
        # Consumir os eventos
        channel.basic_consume(
            queue=selected_3, on_message_callback=callback, auto_ack=True)

        print("Esperando por eventos. Pressione Ctrl+C para sair.")
        channel.start_consuming()

    except Exception as e:
        print(f"Erro ao consumir eventos: {e}")

# Função para ler o carrinho
def ler_carrinho():
    if not os.path.exists(CARRINHO_FILE_PATH):
        # Caso o arquivo não exista, cria um arquivo vazio
        with open(CARRINHO_FILE_PATH, 'w') as file:
            json.dump([], file)
        print(f"Arquivo {CARRINHO_FILE_PATH} criado com carrinho vazio.")  # Log de criação do arquivo
        return []  # Retorna uma lista vazia

    with open(CARRINHO_FILE_PATH, 'r') as file:
        try:
            # Tenta carregar o conteúdo do arquivo JSON
            carrinho = json.load(file)
            print(f"Carrinho carregado: {carrinho}")  # Log para verificar o conteúdo carregado
            return carrinho
        except json.JSONDecodeError:
            # Caso o arquivo esteja vazio ou com conteúdo inválido
            print(f"Erro ao decodificar JSON no arquivo {CARRINHO_FILE_PATH}. Retornando carrinho vazio.")
            return []  # Retorna uma lista vazia se o arquivo estiver vazio ou corrompido
        
# Função para salvar o conteúdo do carrinho
def salvar_carrinho(carrinho):
    try:
        with open(CARRINHO_FILE_PATH, 'w') as file:
            json.dump(carrinho, file, indent=4)
            print(f"Carrinho salvo com sucesso em {CARRINHO_FILE_PATH}.")  # Log para confirmar a gravação
    except Exception as e:
        print(f"Erro ao salvar o carrinho no arquivo {CARRINHO_FILE_PATH}: {e}")  # Log de erro ao salvar

# Função para ler os pedidos do arquivo
def ler_pedidos() -> List[dict]:
    if not os.path.exists(PEDIDOS_FILE_PATH):
        # Caso o arquivo não exista, cria um arquivo vazio
        with open(PEDIDOS_FILE_PATH, 'w') as file:
            json.dump([], file)
        print(f"Arquivo {PEDIDOS_FILE_PATH} criado com pedidos vazios.")  # Log de criação do arquivo
        return []  # Retorna uma lista vazia

    with open(PEDIDOS_FILE_PATH, 'r') as file:
        try:
            # Tenta carregar o conteúdo do arquivo JSON
            pedidos = json.load(file)
            print(f"Pedidos carregados: {pedidos}")  # Log para verificar o conteúdo carregado
            return pedidos
        except json.JSONDecodeError:
            # Caso o arquivo esteja vazio ou com conteúdo inválido
            print(f"Erro ao decodificar JSON no arquivo {PEDIDOS_FILE_PATH}. Retornando pedidos vazios.")
            return []  # Retorna uma lista vazia se o arquivo estiver vazio ou corrompido

# Função para salvar os pedidos no arquivo
def salvar_pedidos(pedidos: List[dict]):
    try:
        with open(PEDIDOS_FILE_PATH, 'w') as file:
            json.dump(pedidos, file, indent=4)
            print(f"Pedidos salvos com sucesso em {PEDIDOS_FILE_PATH}.")  # Log para confirmar a gravação
    except Exception as e:
        print(f"Erro ao salvar os pedidos no arquivo {PEDIDOS_FILE_PATH}: {e}")  # Log de erro ao salvar

@app.get("/")
async def root():
    return {"message": "CORS configurado para localhost"}

###################################################################

# Visualização de todos os produtos
@app.get("/produtos")
async def listar_produtos():
    try:
        # Fazendo uma requisição HTTP GET para o microserviço de estoque
        async with httpx.AsyncClient() as client:
            response = await client.get(f'{ESTOQUE_SERVICE_URL}/estoque')
        
        # Se a resposta do microserviço de estoque for bem-sucedida
        if response.status_code == 200:
            return response.json()  # Retorna os dados do estoque
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

# Rota POST para adicionar um produto ao carrinho
@app.post("/carrinho", response_model=Produto)
async def adicionar_ao_carrinho(produto: Produto):
    carrinho = ler_carrinho()

    # Verifica se o produto já está no carrinho
    for item in carrinho:
        if item["id"] == produto.id:
            item["quantity"]
            item["inStock"]
            salvar_carrinho(carrinho)
            return item
    
    # Se não estiver, adiciona o novo produto
    carrinho.append({
        "id": produto.id,
        "name": produto.name,
        "originalStock": produto.originalStock,
        "inStock": produto.inStock - produto.quantity,  # Subtrai do estoque
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

    # Adicionar o novo pedido à lista de pedidos
    pedidos.append(pedido_criado.dict())

    # Salvar o pedido no arquivo
    salvar_pedidos(pedidos)

    # Publicar evento no RabbitMQ (simulado)
    evento_pedido = {
        "cliente_id": pedido.cliente_id,
        "produto": pedido.produto,
        "quantidade": pedido.quantidade,
    }
    enviar_evento(evento_pedido, "Pedidos_Criados")
    
    #Acordando o microserviço de pagamentos
    async with httpx.AsyncClient() as client:
        response = await client.get(f'{PAGAMENTO_SERVICE_URL}/')
        print(response)

    # Retornar a resposta com a mensagem e o pedido criado
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