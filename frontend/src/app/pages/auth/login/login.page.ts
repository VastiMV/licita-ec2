import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';
import { BrandComponent } from '../../../layout/brand/brand.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { InputTextComponent } from '../../../shared/ui/input-text/input-text.component';

/**
 * Página independente — não é filha do `ShellComponent` em app.routes.ts,
 * então não tem `Navbar`/menu nenhum. Só a `Brand`.
 */
@Component({
  selector: 'app-login-page',
  imports: [ReactiveFormsModule, BrandComponent, InputTextComponent, ButtonComponent],
  templateUrl: './login.page.html',
  styleUrl: './login.page.scss',
})
export class LoginPage {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);

  protected entrar(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.enviando.set(true);
    this.erro.set(null);

    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => {
        this.enviando.set(false);
        this.router.navigateByUrl('/torre');
      },
      error: () => {
        this.enviando.set(false);
        this.erro.set('E-mail ou senha incorretos.');
      },
    });
  }
}
