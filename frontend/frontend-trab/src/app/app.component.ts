import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AppService } from './app.service';
import { Products } from './models';

@Component({
  selector: 'app-root',
  standalone: true,
  // imports: [RouterOutlet, CommonModule, FormsModule],
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit {
  title = 'frontend-trab';
  activeTab = 'products'; // Aba ativa inicialmente
  products: Products[] = [];
  cart: Products[] = [];

  constructor(private appService: AppService) {}

  ngOnInit(): void {
    this.reloadProducts();
  }

  reloadProducts(): void {
    this.appService.getProducts().subscribe({
      next: (prods) => {
        this.products = prods.map((p: any) => {
          return { ...p, originalStock: p.inStock };
        });
      },
      error: (err) => {
        console.error('Erro ao buscar produtos:', err);
      },
    });

    this.appService.updateCart().subscribe({
      next: (prods) => {
        this.cart = prods.map((p: any) => {
          return { ...p, originalStock: p.inStock, updatedQuantity: null };
        });
      },
      error: (err) => {
        console.error('Erro ao buscar carrinho:', err);
      },
    });
  }

  updateStock(stock: number, quantity: number) {}

  setActiveTab(tab: string) {
    this.reloadProducts();
    this.activeTab = tab;
  }

  addToCart(product: Products) {
    this.appService.addToCart(product).subscribe({
      next: () => {
        alert('Produto adicionado ao carrinho');
      },
    });
  }

  removeFromCart(product: number) {
    this.appService.removeFromCart(product).subscribe({
      next: () => {
        alert('Produto removido do carrinho');
      },
      complete: () => this.reloadProducts(),
    });
  }

  adjustInCart(product: Products) {
    this.appService.adjustInCart(product).subscribe({
      next: () => {
        alert('Produto atualizado no carrinho');
      },
      complete: () => this.reloadProducts(),
    });
  }

  cartActionButton(product: Products) {
    console.log(product);
    if (!product.updatedQuantity) {
      this.removeFromCart(product.id);
    } else {
      const payload = {
        ...product,
        quantity: product.updatedQuantity,
      };
      this.adjustInCart(payload);
    }
  }

  payItem(item: any) {
    this.appService.payItem(item).subscribe({
      next: () => {
        alert('Produto submetido a pagamento');
      },
      complete: () => this.reloadProducts(),
    });
  }
}
