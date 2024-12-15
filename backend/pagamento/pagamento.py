import pika
import json

RABBITMQ_HOST = 'rabiitmq'
QUEUE_PEDIDOS_CRIADOS = 'Pedidos_Criados'
QUEUE_PAGAMENTOS_APROVADOS = 'Pagamentos_Aprovados'

# Função para enviar um evento para o RabbitMQ
def enviar_evento(evento, queue):
    # Estabelece conexão com o RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

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

# Função que consome as mensagens do RabbitMQ na fila Pedidos_Criados
def callback(ch, method, properties, body):
    try:
        # Recebe os dados do pedido
        pedido = json.loads(body)
        print(f"Pedido recebido para processamento: {pedido}")

        # Lógica de processamento do pagamento (aqui podemos simular como aprovado)
        pagamento_aprovado = {
            "cliente_id": pedido["cliente_id"],
            "produto_id": pedido["produto_id"],
            "quantidade": pedido["quantidade"],
            "status": "Aprovado",  # Status do pagamento
            "id": f"pgto_{pedido['produto_id']}_{pedido['cliente_id']}"  # Gerar ID do pagamento
        }

        # Enviar evento de pagamento aprovado para a fila Pagamentos_Aprovados
        enviar_evento(pagamento_aprovado, QUEUE_PAGAMENTOS_APROVADOS)

    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem recebida.")

# Função para iniciar o consumidor de mensagens da fila Pedidos_Criados
def consumir_pedidos():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    # Garante que a fila Pedidos_Criados existe
    channel.queue_declare(queue=QUEUE_PEDIDOS_CRIADOS)

    # Definir o consumidor da fila
    channel.basic_consume(queue=QUEUE_PEDIDOS_CRIADOS, on_message_callback=callback, auto_ack=True)

    print('Aguardando mensagens na fila Pedidos_Criados. Para sair pressione CTRL+C')
    channel.start_consuming()

if __name__ == "__main__":
    consumir_pedidos()
