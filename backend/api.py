# Estrutura de Backend com Python (FastAPI)
# Arquivo principal: main.py
from fastapi import FastAPI, HTTPException

# Instância principal do FastAPI
app = FastAPI()

# Rotas para o microsserviço principal
@app.get("/produtos")
async def listar_produtos():
    # TODO: Implementar listagem de produtos
    return {"mensagem": "Listar produtos"}

@app.post("/carrinho")
async def adicionar_ao_carrinho():
    # TODO: Implementar adição de produto ao carrinho
    return {"mensagem": "Produto adicionado ao carrinho"}

@app.delete("/carrinho")
async def remover_do_carrinho():
    # TODO: Implementar remoção de produto do carrinho
    return {"mensagem": "Produto removido do carrinho"}

@app.post("/pedidos")
async def criar_pedido():
    # TODO: Implementar criação de pedido
    return {"mensagem": "Pedido criado"}

@app.delete("/pedidos/{pedido_id}")
async def excluir_pedido(pedido_id: int):
    # TODO: Implementar exclusão de pedido
    return {"mensagem": f"Pedido {pedido_id} excluído"}

# Estruturas para microsserviços adicionais serão implementadas nos arquivos correspondentes.
# Exemplo: estoque.py, pagamento.py, entrega.py, notificacao.py.
