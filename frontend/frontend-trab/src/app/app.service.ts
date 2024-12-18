import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Cart, Products } from './models';

@Injectable({
  providedIn: 'root',
})
export class AppService {
  private apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  // Adicione os headers aqui
  headers = new HttpHeaders({
    'Content-Type': 'application/json',
    //   'Authorization': 'Bearer meu-token-aqui', // Exemplo de token
  });
  getProducts(): Observable<any> {
    const headers = this.headers;

    return this.http.get(`${this.apiUrl}/produtos`, { headers });
  }

  updateCart(): Observable<any> {
    const headers = this.headers;

    return this.http.get(`${this.apiUrl}/carrinho`, { headers });
  }

  updateOrders(): Observable<any> {
    const headers = this.headers;

    return this.http.get(`${this.apiUrl}/pedidos`, { headers });
  }

  addToCart(item: Products) {
    const headers = this.headers;
    const payload = {
      client_id: 1,
      product_name: item.name,
      product_id: item.id,
      available_stock: 0,
      quantity: item.quantity,
    };

    return this.http.post(`${this.apiUrl}/carrinho`, payload, { headers });
  }
  removeFromCart(id: number, client_id: number) {
    const headers = this.headers;

    return this.http.delete(`${this.apiUrl}/carrinho/${client_id}/${id}`, {
      headers,
    });
  }

  adjustInCart(item: Cart, client_id: number) {
    const headers = this.headers;

    return this.http.patch(
      `${this.apiUrl}/carrinho/${client_id}/${item.product_id}/${item.quantity}`,
      {
        headers,
      }
    );
  }

  payItem(item: Cart) {
    const headers = this.headers;
    const payload = {
      id: 0,
      client_id: 1,
      product_id: item.product_id,
      product_name: item.product_name,
      quantity: item.quantity,
      status: 'pendente',
    };

    return this.http.post(`${this.apiUrl}/pedidos`, payload, { headers });
  }
}
