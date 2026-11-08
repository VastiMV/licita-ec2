import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AuthService } from '../../../core/auth/auth.service';
import { LoginPage } from './login.page';

describe('LoginPage', () => {
  let fixture: ComponentFixture<LoginPage>;
  let auth: { login: ReturnType<typeof vi.fn> };
  let router: Router;

  beforeEach(() => {
    auth = { login: vi.fn() };
    TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }],
    });
    fixture = TestBed.createComponent(LoginPage);
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    fixture.detectChanges();
  });

  function submeter(): void {
    fixture.debugElement.query(By.css('form')).triggerEventHandler('submit', new Event('submit'));
    fixture.detectChanges();
  }

  it('mostra a marca e nenhum menu — página independente, sem Navbar', () => {
    expect(fixture.debugElement.query(By.css('.brand'))).toBeTruthy();
    expect(fixture.debugElement.query(By.css('nav'))).toBeNull();
  });

  it('não chama o AuthService e mostra os erros de campo quando o form é inválido', () => {
    submeter();

    expect(auth.login).not.toHaveBeenCalled();
    const erros = fixture.debugElement.queryAll(By.css('.field-error'));
    expect(erros.length).toBeGreaterThan(0);
  });

  it('em sucesso, autentica e abre a Torre de Controle', () => {
    auth.login.mockReturnValue(of({ access: 'token-abc' }));

    fixture.componentInstance['form'].setValue({ email: 'user@licita.dev', password: 'segredo' });
    submeter();

    expect(auth.login).toHaveBeenCalledWith({ email: 'user@licita.dev', password: 'segredo' });
    expect(router.navigateByUrl).toHaveBeenCalledWith('/torre');
  });

  it('em falha, mostra mensagem de erro e não navega', () => {
    auth.login.mockReturnValue(throwError(() => new Error('401')));

    fixture.componentInstance['form'].setValue({ email: 'user@licita.dev', password: 'errada' });
    submeter();

    expect(router.navigateByUrl).not.toHaveBeenCalled();
    const erro = fixture.debugElement.query(By.css('.login-erro'));
    expect(erro.nativeElement.textContent.trim()).toBe('E-mail ou senha incorretos.');
  });
});
