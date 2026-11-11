import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  Injectable,
  OnInit,
  inject,
  signal,
} from '@angular/core';

import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

/** Sai do Licita para outra página do mesmo servidor (separado para o teste). */
@Injectable({ providedIn: 'root' })
export class Navegador {
  private readonly documento = inject(DOCUMENT);

  ir(url: string): void {
    this.documento.location.assign(url);
  }
}

/**
 * Abre o site da documentação (/documentacao, GEN-63, 10/11/2026).
 *
 * O site é estático e fica atrás do mesmo login do Licita: esta tela (já
 * protegida pelo login) pede ao servidor o "passe da documentação" — um
 * cookie que só vale em /documentacao — e então vai para o site. O Caddy
 * confere o passe a cada página; sem passe, ele manda de volta para cá.
 */
@Component({
  selector: 'app-abrir-documentacao',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (erro()) {
      <p role="alert">Não foi possível abrir a documentação agora. Tente de novo.</p>
    } @else {
      <p>Abrindo a documentação…</p>
    }
  `,
})
export class AbrirDocumentacaoPage implements OnInit {
  private readonly api = inject(ApiClient);
  private readonly navegador = inject(Navegador);

  protected readonly erro = signal(false);

  ngOnInit(): void {
    this.api.post<void>(ENDPOINTS.auth.documentacao, {}).subscribe({
      next: () => this.navegador.ir('/documentacao/'),
      error: () => this.erro.set(true),
    });
  }
}
