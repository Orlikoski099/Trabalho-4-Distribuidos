import pika
import json
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Instância principal do FastAPI
app = FastAPI()

# Configurações do RabbitMQ
RABBITMQ_HOST = 'rabbitmq'  # Nome do serviço RabbitMQ no Docker Compose
QUEUE_PEDIDOS_CRIADOS = 'Pedidos_Criados'
QUEUE_PEDIDOS_EXCLUIDOS = 'Pedidos_Excluídos'
QUEUE_PAGAMENTOS_APROVADOS = 'Pagamentos_Aprovados'
QUEUE_PAGAMENTOS_RECUSADOS = 'Pagamentos_Recusados'
QUEUE_PEDIDOS_ENVIADOS = 'Pedidos_Enviados'


ESTOQUE_SERVICE_URL = 'http://estoque:8000'

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

# Rota para visualizar o carrinho de compras
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

# Rota para adicionar produto ao carrinho
@app.post("/carrinho")
async def adicionar_ao_carrinho(pedido: Pedido):
    # Implementar lógica de adicionar ao carrinho
    return {"mensagem": f"Produto {pedido.produto_id} adicionado ao carrinho"}

# Rota para remover produto do carrinho
@app.delete("/carrinho/{produto_id}")
async def remover_do_carrinho(produto_id: int):
    # Implementar lógica de remoção do carrinho
    return {"mensagem": f"Produto {produto_id} removido do carrinho"}

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
