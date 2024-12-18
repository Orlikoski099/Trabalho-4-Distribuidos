from fastapi import FastAPI, Request
from pydantic import BaseModel
import random

app = FastAPI()

class Pagamento(BaseModel):
    transacao_id: str
    client_id: int 
    product_id: int
    product_name: str
    quantity: int

###################################################################

@app.post("/webhook/pagamento")
async def webhook_pagamento(pagamento: Pagamento):
    status = "aprovado" if random.choice([True, False]) else "recusado"

    resposta = {
        "transacao_id": pagamento.transacao_id,
        "client_id": pagamento.client_id,
        "product_id": pagamento.product_id,
        "product_name": pagamento.product_name,
        "quantity": pagamento.quantity,
        "status": status,
    }

    print(f"Pagamento processado: {resposta}")
    return resposta

@app.get("/")
def root():
    return {"message": "Sistema de Pagamento Webhook está rodando!"}
