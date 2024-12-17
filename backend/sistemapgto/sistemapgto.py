from fastapi import FastAPI, Request
from pydantic import BaseModel
import random

app = FastAPI()

class Pagamento(BaseModel):
    transacao_id: str
    cliente_id: int 
    produto: str
    quantidade: int

@app.post("/webhook/pagamento")
async def webhook_pagamento(pagamento: Pagamento):
    status = "aprovado" if random.choice([True, False]) else "recusado"
    
    resposta = {
        "transacao_id": pagamento.transacao_id,
        "status": status,
        "cliente_id": pagamento.cliente_id,
        "produto": pagamento.produto,
        "quantidade": pagamento.quantidade
    }

    print(f"Pagamento processado: {resposta}")
    return resposta

@app.get("/")
def root():
    return {"message": "Sistema de Pagamento Webhook está rodando!"}
