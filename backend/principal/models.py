
# Definindo o modelo de product com base na interface Products
from typing import Optional
from pydantic import BaseModel


class Produto(BaseModel):
    id: int
    name: str
    originalStock: int
    stock: int
    quantity: int

# Modelo de Pedido
class Pedido(BaseModel):
    id: Optional[int]
    client_id: int
    product: int
    quantidade: int
    status: Optional[str]  # 'pendente', 'aprovado', 'recusado'
