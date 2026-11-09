import { Component, ElementRef, HostListener, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { UsuarioResponse } from '../../contracts/usuarios/usuario.contracts';
import { AuthService } from '../../core/auth/auth.service';
import {
  UsuarioModalComponent,
  UsuarioModalDados,
} from '../../pages/configuracoes/usuarios/usuario-modal/usuario-modal.component';
import { UsuariosService } from '../../services/usuarios/usuarios.service';
import { ModalService } from '../../shared/overlay/modal.service';
import { IconComponent } from '../../shared/ui/icon/icon.component';
import { ToastService } from '../../shared/ui/toast/toast.service';
import { reduzirFoto } from './reduzir-foto';

/**
 * Substitui os links horizontais de conta na topbar por um único gatilho
 * (ícone de usuário) que abre um dropdown com nome/e-mail e as ações de
 * conta: "Editar perfil" (o mesmo modal da tela de Usuários, sem o super
 * usuário) e "Sair".
 *
 * Fecha sozinho ao clicar fora ou apertar Esc — não usa o `ModalService`/
 * `@angular/cdk/dialog` de propósito: aquilo é pra diálogo modal centrado
 * com backdrop bloqueante; isso aqui é um dropdown ancorado no próprio
 * botão, não trava a página.
 */
@Component({
  selector: 'app-profile-menu',
  imports: [IconComponent],
  templateUrl: './profile-menu.component.html',
  styleUrl: './profile-menu.component.scss',
})
export class ProfileMenuComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly elementRef = inject(ElementRef<HTMLElement>);
  private readonly usuarios = inject(UsuariosService);
  private readonly modal = inject(ModalService);
  private readonly toast = inject(ToastService);

  protected readonly aberto = signal(false);
  protected readonly usuario = this.auth.usuario;

  /** A foto do próprio perfil (`usuarios/eu/`); vazia = a inicial. */
  protected readonly foto = signal('');

  constructor() {
    // Lida uma vez ao montar o topo; troca na hora quando a pessoa muda.
    this.usuarios.perfil().subscribe({
      next: (eu) => this.foto.set(eu.foto ?? ''),
      error: () => undefined,
    });
  }

  /** "Trocar foto": reduz no navegador e envia. */
  protected escolherFoto(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const arquivo = campo.files?.[0];
    campo.value = '';
    if (!arquivo) return;
    this.aberto.set(false);
    reduzirFoto(arquivo)
      .then((foto) =>
        this.usuarios.trocarFoto(foto).subscribe({
          next: (eu) => {
            this.foto.set(eu.foto ?? '');
            this.toast.sucesso('Foto atualizada.');
          },
          error: () => this.toast.erro('Não foi possível salvar a foto agora.'),
        }),
      )
      .catch((erro: Error) => this.toast.erro(erro.message));
  }

  protected tirarFoto(): void {
    this.aberto.set(false);
    this.usuarios.tirarFoto().subscribe({
      next: () => this.foto.set(''),
      error: () => this.toast.erro('Não foi possível tirar a foto agora.'),
    });
  }

  /** A inicial do nome no círculo escuro, como no protótipo v2. */
  protected readonly inicial = computed(() =>
    (this.usuario()?.nome || this.usuario()?.email || '?').trim().charAt(0).toUpperCase(),
  );

  @HostListener('document:click', ['$event'])
  protected fecharAoClicarFora(evento: MouseEvent): void {
    if (this.aberto() && !this.elementRef.nativeElement.contains(evento.target as Node)) {
      this.aberto.set(false);
    }
  }

  @HostListener('document:keydown.escape')
  protected fecharComEsc(): void {
    this.aberto.set(false);
  }

  protected alternar(): void {
    this.aberto.update((valor) => !valor);
  }

  protected editarPerfil(): void {
    this.aberto.set(false);
    this.usuarios.perfil().subscribe({
      next: (usuario) => {
        const dados: UsuarioModalDados = { usuario, ehEu: true, perfil: true };
        this.modal
          .abrir<UsuarioResponse, UsuarioModalDados>(UsuarioModalComponent, dados)
          .subscribe((salvo) => {
            if (!salvo) return;
            this.toast.sucesso('Perfil atualizado.');
            // Nome e e-mail do menu vêm do token — um token novo traz os
            // dados novos sem precisar sair e entrar.
            this.auth.refresh().subscribe();
          });
      },
      error: () => this.toast.erro('Não foi possível abrir o seu perfil agora.'),
    });
  }

  protected sair(): void {
    this.aberto.set(false);
    this.auth.logout().subscribe(() => this.router.navigateByUrl('/login'));
  }
}
