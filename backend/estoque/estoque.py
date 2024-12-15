import json
import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from threading import Thread

app = FastAPI()

# Função para carregar o estoque do arquivo JSON
def carregar_estoque():
    try:
        with open("estoque.json", "r") as file:
            # Verifica se o arquivo está vazio
            content = file.read().strip()  # Lê o conteúdo e remove espaços em branco
            if not content:
                raise HTTPException(status_code=204, detail="No content")
            
            # Se o arquivo não estiver vazio, carrega os dados JSON
            return json.loads(content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Erro ao decodificar o JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

# Função para salvar as alterações no estoque no arquivo JSON
def salvar_estoque(estoque):
    with open("estoque.json", "w") as file:
        json.dump(estoque, file, indent=4)

# Modelo de dados para representar um pedido
class Pedido(BaseModel):
    produto_id: int
    quantidade: int

# Função para enviar mensagens ao RabbitMQ
def enviar_mensagem(pedido, evento):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    
    # Declarar as filas para envio
    channel.queue_declare(queue='Pedidos_Criados')
    channel.queue_declare(queue='Pedidos_Excluídos')
    
    # Enviar a mensagem
    if evento == 'criar':
        channel.basic_publish(exchange='',
                              routing_key='Pedidos_Criados',
                              body=json.dumps(pedido))
    elif evento == 'excluir':
        channel.basic_publish(exchange='',
                              routing_key='Pedidos_Excluídos',
                              body=json.dumps(pedido))
    
    connection.close()

# Conexão RabbitMQ e consumo de mensagens
def consumir_mensagens():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # Declarar as filas para consumir
    channel.queue_declare(queue='Pedidos_Criados')
    channel.queue_declare(queue='Pedidos_Excluídos')

    # Função que vai processar a mensagem quando receber um pedido criado
    def callback_pedido_criado(ch, method, properties, body):
        pedido = json.loads(body)
        produto_id = pedido['produto_id']
        quantidade = pedido['quantidade']
        
        estoque = carregar_estoque()
        produto = next((p for p in estoque['produtos'] if p['id'] == produto_id), None)
        
        if produto and produto['quantidade'] >= quantidade:
            produto['quantidade'] -= quantidade
            salvar_estoque(estoque)
            print(f"Estoque atualizado após pedido criado: {produto}")
        else:
            print("Erro: Estoque insuficiente ou produto não encontrado.")
    
    # Função que vai processar a mensagem quando receber um pedido excluído
    def callback_pedido_excluido(ch, method, properties, body):
        pedido = json.loads(body)
        produto_id = pedido['produto_id']
        quantidade = pedido['quantidade']
        
        estoque = carregar_estoque()
        produto = next((p for p in estoque['produtos'] if p['id'] == produto_id), None)
        
        if produto:
            produto['quantidade'] += quantidade
            salvar_estoque(estoque)
            print(f"Estoque atualizado após pedido excluído: {produto}")
        else:
            print("Erro: Produto não encontrado.")
    
    # Consumindo as mensagens das filas
    channel.basic_consume(queue='Pedidos_Criados', on_message_callback=callback_pedido_criado, auto_ack=True)
    channel.basic_consume(queue='Pedidos_Excluídos', on_message_callback=callback_pedido_excluido, auto_ack=True)
    
    print('Aguardando mensagens...')
    channel.start_consuming()

# Iniciando o consumo em uma thread separada
def iniciar_consumo():
    thread = Thread(target=consumir_mensagens)
    thread.start()

# Endpoint para criar um pedido (agora também envia um evento para RabbitMQ)
@app.post("/pedido/criar")
async def criar_pedido(pedido: Pedido):
    estoque = carregar_estoque()
    produto = next((p for p in estoque['produtos'] if p['id'] == pedido.produto_id), None)
    
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    if produto['quantidade'] < pedido.quantidade:
        raise HTTPException(status_code=400, detail="Quantidade insuficiente no estoque.")
    
    # Atualizando o estoque
    produto['quantidade'] -= pedido.quantidade
    salvar_estoque(estoque)
    
    # Enviar o evento para RabbitMQ
    enviar_mensagem(pedido.dict(), 'criar')
    
    return {"message": "Pedido criado com sucesso", "produto": produto}

# Endpoint para excluir um pedido (agora também envia um evento para RabbitMQ)
@app.post("/pedido/excluir")
async def excluir_pedido(pedido: Pedido):
    estoque = carregar_estoque()
    produto = next((p for p in estoque['produtos'] if p['id'] == pedido.produto_id), None)
    
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    # "Restaurando" a quantidade excluída
    produto['quantidade'] += pedido.quantidade
    salvar_estoque(estoque)
    
    # Enviar o evento para RabbitMQ
    enviar_mensagem(pedido.dict(), 'excluir')
    
    return {"message": "Pedido excluído com sucesso", "produto": produto}

###################################################################

# Endpoint para consultar o estoque
@app.get("/estoque")
async def consultar_estoque():
    estoque = carregar_estoque()
    return estoque

# Iniciar o consumo das mensagens do RabbitMQ
if __name__ == "__main__":
    iniciar_consumo()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
