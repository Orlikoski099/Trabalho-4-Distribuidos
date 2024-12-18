export interface Products {
  id: number;
  name: string;
  stock: number;
  quantity: number;
  available_stock: number; //Used to allow lock or unlock the payment button
  originalStock: number; //Only local for auto adjust stock
}

export interface Orders {
  id: number;
  client_id: number;
  product_id: string;
  product_name: string;
  quantity: number;
  status: 'pendente' | 'aprovado' | 'recusado';
}

export interface Cart {
  client_id: number;
  product_name: string;
  product_id: number;
  available_stock: number;
  quantity: number;
  updatedQuantity: number; //Only local for auto adjust action button text
}
