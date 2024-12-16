export interface Products {
  id: number;
  name: string;
  originalStock: number;
  inStock: number;
  quantity: number;
  updatedQuantity: number;
}

export interface Orders {
  id: number;
  cliente_id: number;
  produto: string;
  quantidade: number;
  status: 'pendente' | 'aprovado' | 'recusado';
}
