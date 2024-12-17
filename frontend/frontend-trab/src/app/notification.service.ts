import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root', // Para standalone, garante que o serviço seja singleton
})
export class NotificacaoService {
  private eventSource: EventSource | null = null;

  constructor() {}
  conectar(url: string): Observable<any> {
    return new Observable((observer) => {
      this.eventSource = new EventSource(url);

      // Evento de mensagem recebida
      this.eventSource.onmessage = (event) => {
        try {
          const dados = JSON.parse(event.data);
          observer.next(dados);
        } catch (error) {
          console.error('Erro ao processar mensagem SSE:', error);
        }
      };

      // Evento de erro
      this.eventSource.onerror = (error) => {
        console.error('Erro no SSE:', error);
        observer.error(error);

        // Fecha e limpa a conexão em caso de erro
        this.eventSource?.close();
        observer.complete();
      };

      // Cleanup da conexão ao finalizar o Observable
      return () => {
        this.eventSource?.close();
        console.log('Conexão SSE encerrada.');
      };
    });
  }

  /**
   * Fecha a conexão manualmente.
   */
  fecharConexao(): void {
    if (this.eventSource) {
      this.eventSource.close();
      console.log('Conexão SSE fechada manualmente.');
    }
  }
}
