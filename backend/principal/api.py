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
RABBITMQ_HOST = 'rabbitmq'  # Nome do serviço RabbitMQ no Docker Compose
QUEUE_PEDIDOS_CRIADOS = 'Pedidos_Criados'
QUEUE_PEDIDOS_EXCLUIDOS = 'Pedidos_Excluídos'
QUEUE_PAGAMENTOS_APROVADOS = 'Pagamentos_Aprovados'
QUEUE_PAGAMENTOS_RECUSADOS = 'Pagamentos_Recusados'
QUEUE_PEDIDOS_ENVIADOS = 'Pedidos_Enviados'


ESTOQUE_SERVICE_URL = 'http://estoque:8000'
NOTIFICACAO_SERVICE_URL = 'http://notificacao:8000'
ENTREGA_SERVICE_URL = 'http://entrega:8000'
PAGAMENTO_SERVICE_URL = 'http://pagamento:8000'

CARRINHO_FILE_PATH = "carrinho.json"

# Definindo o modelo de produto com base na interface Products
class Produto(BaseModel):
    id: int
    name: str
    originalStock: int
    inStock: int
    quantity: int

# Modelo Pydantic para Pedido
class Pedido(BaseModel):
    produto_id: int
    quantidade: int
    cliente_id: int
    status: Optional[str] = "Pendente"

def enviar_evento(corpo, fila):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Declarar a fila
        channel.queue_declare(queue=fila, durable=True)

        # Enviar mensagem
        channel.basic_publish(
            exchange='',
            routing_key=fila,
            body=json.dumps(corpo),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Tornar a mensagem persistente
            )
        )

        connection.close()
    except Exception as e:
        print(f"Erro ao enviar evento para o RabbitMQ: {e}")

def consumir_eventos():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Declarar as filas que o serviço irá consumir
        channel.queue_declare(queue=QUEUE_PAGAMENTOS_APROVADOS, durable=True)
        channel.queue_declare(queue=QUEUE_PAGAMENTOS_RECUSADOS, durable=True)
        channel.queue_declare(queue=QUEUE_PEDIDOS_ENVIADOS, durable=True)

        # Função de callback para processar os eventos
        def callback(ch, method, properties, body):
            evento = json.loads(body)
            if method.routing_key == QUEUE_PAGAMENTOS_APROVADOS:
                print(f"Pagamento aprovado para pedido {evento['pedido_id']}")
                # Atualizar status do pedido para "Aprovado"
            elif method.routing_key == QUEUE_PAGAMENTOS_RECUSADOS:
                print(f"Pagamento recusado para pedido {evento['pedido_id']}")
                # Atualizar status do pedido para "Recusado"
            elif method.routing_key == QUEUE_PEDIDOS_ENVIADOS:
                print(f"Pedido {evento['pedido_id']} enviado")
                # Atualizar status do pedido para "Enviado"
            
            ch.basic_ack(delivery_tag=method.delivery_tag)

        # Consumir os eventos
        channel.basic_consume(queue=QUEUE_PAGAMENTOS_APROVADOS, on_message_callback=callback)
        channel.basic_consume(queue=QUEUE_PAGAMENTOS_RECUSADOS, on_message_callback=callback)
        channel.basic_consume(queue=QUEUE_PEDIDOS_ENVIADOS, on_message_callback=callback)

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
            print(f'{ESTOQUE_SERVICE_URL}/estoque')
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


# Rota para criar pedido
@app.post("/pedidos")
async def criar_pedido(pedido: Pedido):
    # Criar o pedido e publicar evento no RabbitMQ
    enviar_evento(pedido.dict(), QUEUE_PEDIDOS_CRIADOS)
    return {"mensagem": f"Pedido criado e evento enviado para o estoque"}

# Rota para excluir pedido
@app.delete("/pedidos/{pedido_id}")
async def excluir_pedido(pedido_id: int):
    # Excluir o pedido e publicar evento no RabbitMQ
    pedido = {"pedido_id": pedido_id}  # Exemplo de dado a ser enviado
    enviar_evento(pedido, QUEUE_PEDIDOS_EXCLUIDOS)
    return {"mensagem": f"Pedido {pedido_id} excluído e evento enviado"}

# Função de inicialização para consumir eventos
@app.on_event("startup")
async def iniciar_consumo_de_eventos():
    import threading
    thread = threading.Thread(target=consumir_eventos, daemon=True)
    thread.start()
