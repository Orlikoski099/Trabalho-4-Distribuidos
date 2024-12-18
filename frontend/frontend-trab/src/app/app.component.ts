import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AppService } from './app.service';
import { NotificacaoService } from './notification.service';
import { Cart, Orders, Products } from './models';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  // imports: [RouterOutlet, CommonModule, FormsModule],
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'frontend-trab';
  activeTab = 'products'; // Aba ativa inicialmente
  products: Products[] = [];
  cart: Cart[] = [];
  orders: Orders[] = [];

  notificacoes: any[] = [];
  private notificacaoSub: Subscription | null = null;

  constructor(
    private appService: AppService,
    private notificacaoService: NotificacaoService
  ) {}

  ngOnInit(): void {
    this.reloadProducts();
    this.startNotificator();
  }

  startNotificator() {
    // Conecta ao SSE e escuta as notificações
    this.notificacaoSub = this.notificacaoService
      .conectar('http://localhost:8004/notificacoes') // URL do SSE
      .subscribe({
        next: (data) => {
          console.log('Notificação recebida:', data);
          this.notificacoes.push(data);
        },
        error: (err) => console.error('Erro no SSE:', err),
        complete: () => console.log('Conexão SSE concluída.'),
      });
  }

  ngOnDestroy(): void {
    // Fecha a conexão ao destruir o componente
    this.notificacaoSub?.unsubscribe();
    this.notificacaoService.fecharConexao();
  }

  reloadProducts(): void {
    switch (this.activeTab) {
      case 'products': {
        this.appService.getProducts().subscribe({
          next: (prods) => {
            this.products = prods.map((p: any) => {
              return { ...p, originalStock: p.stock };
            });
          },
          error: (err) => {
            console.error('Erro ao buscar produtos:', err);
          },
        });
        break;
      }
      case 'cart': {
        this.appService.updateCart().subscribe({
          next: (prods) => {
            this.cart = prods.map((p: any) => {
              return { ...p, updatedQuantity: null };
            });
          },
          error: (err) => {
            console.error('Erro ao buscar carrinho:', err);
          },
        });
        break;
      }
      case 'orders': {
        this.appService.updateOrders().subscribe({
          next: (orders) => {
            this.orders = orders.map((p: any) => {
              return { ...p, originalStock: p.stock, updatedQuantity: null };
            });
          },
          error: (err) => {
            console.error('Erro ao buscar carrinho:', err);
          },
        });
      }
    }
  }

  setActiveTab(tab: string) {
    this.activeTab = tab;
    this.reloadProducts();
  }

  addToCart(product: Products) {
    this.appService.addToCart(product).subscribe({
      next: () => {
        alert('Produto adicionado ao carrinho');
      },
      complete: () => this.reloadProducts(),
    });
  }

  removeFromCart(product: number) {
    this.appService.removeFromCart(product, 1).subscribe({
      next: () => {
        alert('Produto removido do carrinho');
      },
      complete: () => this.reloadProducts(),
    });
  }

  adjustInCart(product: Cart) {
    this.appService.adjustInCart(product, 1).subscribe({
      next: () => {
        alert('Produto atualizado no carrinho');
      },
      complete: () => this.reloadProducts(),
    });
  }

  cartActionButton(product: Cart) {
    if (!product.updatedQuantity) {
      this.removeFromCart(product.product_id);
    } else {
      const payload = {
        ...product,
        quantity: product.updatedQuantity,
      };
      this.adjustInCart(payload);
    }
  }

  payItem(item: any, item_id: any) {
    this.appService.payItem(item).subscribe({
      next: () => {
        alert('Produto submetido a pagamento');
      },
      complete: () => {
        this.reloadProducts();
        this.removeFromCart(item.product_id);
      },
    });
  }
}
