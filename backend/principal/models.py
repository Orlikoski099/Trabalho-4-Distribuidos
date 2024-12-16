
# Definindo o modelo de produto com base na interface Products
from typing import Optional
from pydantic import BaseModel


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
    produto: int
    quantidade: int
    status: Optional[str]  # 'pendente', 'aprovado', 'recusado'
