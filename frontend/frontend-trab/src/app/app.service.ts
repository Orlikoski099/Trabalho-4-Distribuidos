import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Products } from './models';

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

  addToCart(item: Products) {
    const headers = this.headers;
    const payload = { ...item };

    return this.http.post(`${this.apiUrl}/carrinho`, payload, { headers });
  }
  removeFromCart(id: number) {
    const headers = this.headers;

    return this.http.delete(`${this.apiUrl}/carrinho/${id}`, { headers });
  }

  adjustInCart(item: Products) {
    const headers = this.headers;

    return this.http.patch(
      `${this.apiUrl}/carrinho/${item.id}/${item.quantity}`,
      {
        headers,
      }
    );
  }
}
