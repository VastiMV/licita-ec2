import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of, throwError } from 'rxjs';

import { FornecedorResponse } from '../../../contracts/fornecedores/fornecedor.contracts';
import { FornecedoresService } from '../../../services/fornecedores/fornecedores.service';
import { FornecedorModalComponent } from './fornecedor-modal.component';

const EXISTENTE = {
  id: 4,
  nome: 'Marucci Distribuidora Ltda',
  fantasia: 'Marucci',
  tipo: 'pj',
  cnpj: '11222333000181',
  cnpj_formatado: '11.222.333/0001-81',
  inscricao_estadual: 'Isento',
  categoria: 'materiais',
  categoria_label: 'Materiais',
  cep: '13010000',
  logradouro: 'Rua das Flores',
  numero: '100',
  complemento: '',
  bairro: 'Centro',
  uf: 'SP',
  cidade: 'Campinas',
  cidade_uf: 'Campinas / SP',
  responsavel: 'Ana',
  email: 'compras@marucci.com.br',
  telefone: '1932221100',
  celular: '',
  condicao_pagamento: '30_dias',
  prazo_entrega_dias: 10,
  dados_bancarios: '',
  chave_pix: '',
  observacoes: '',
  situacao: 'ativo',
  situacao_label: 'Ativo',
  criado_em: '2026-08-25T12:00:00Z',
  atualizado_em: '2026-08-25T12:00:00Z',
} as FornecedorResponse;

function montar(dados: FornecedorResponse | null) {
  const service = {
    criar: vi.fn(() => of({ ...EXISTENTE, id: 9 })),
    atualizar: vi.fn(() => of(EXISTENTE)),
  };
  const dialogRef = { close: vi.fn() };

  TestBed.configureTestingModule({
    imports: [FornecedorModalComponent],
    providers: [
      { provide: DIALOG_DATA, useValue: dados },
      { provide: DialogRef, useValue: dialogRef },
      { provide: FornecedoresService, useValue: service },
    ],
  });
  const fixture = TestBed.createComponent(FornecedorModalComponent);
  fixture.detectChanges();
  return { fixture, service, dialogRef };
}

function digitar(
  fixture: ComponentFixture<FornecedorModalComponent>,
  campo: string,
  valor: string,
) {
  const controle = (
    fixture.componentInstance as never as {
      form: { get: (c: string) => { setValue: (v: string) => void; markAsTouched: () => void } };
    }
  ).form;
  const alvo = controle.get(campo)!;
  alvo.setValue(valor);
  alvo.markAsTouched();
  fixture.detectChanges();
}

function salvar(fixture: ComponentFixture<FornecedorModalComponent>) {
  const botoes = fixture.debugElement.queryAll(By.css('app-button button'));
  botoes[botoes.length - 1].nativeElement.click();
  fixture.detectChanges();
}

describe('FornecedorModalComponent', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('cadastro', () => {
    it('abre em branco, com os padrões do handoff (PJ, materiais, SP, 30 dias, ativo)', () => {
      const { fixture } = montar(null);
      const valores = (
        fixture.componentInstance as never as {
          form: { getRawValue: () => Record<string, string> };
        }
      ).form.getRawValue();

      expect(valores['nome']).toBe('');
      expect(valores['tipo']).toBe('pj');
      expect(valores['categoria']).toBe('materiais');
      expect(valores['uf']).toBe('SP');
      expect(valores['condicao_pagamento']).toBe('30_dias');
      expect(fixture.nativeElement.textContent).toContain('Novo fornecedor');
    });

    it('não salva com o formulário inválido — e mostra o erro no campo', () => {
      const { fixture, service } = montar(null);

      salvar(fixture);

      expect(service.criar).not.toHaveBeenCalled();
      expect(fixture.nativeElement.textContent).toContain('Campo obrigatório');
    });

    it('salva só com a razão social — sem CNPJ e sem e-mail (GEN-19)', () => {
      const { fixture, service } = montar(null);
      digitar(fixture, 'nome', 'Casa das Rações do Zé');

      salvar(fixture);

      expect(service.criar).toHaveBeenCalledWith(
        expect.objectContaining({ nome: 'Casa das Rações do Zé', cnpj: '', email: '' }),
      );
    });

    it('recusa documento com dígito verificador errado antes de ir ao servidor', () => {
      const { fixture, service } = montar(null);
      digitar(fixture, 'nome', 'Empresa X');
      digitar(fixture, 'email', 'x@x.com');
      digitar(fixture, 'cnpj', '11222333000182');

      salvar(fixture);

      expect(service.criar).not.toHaveBeenCalled();
      expect(fixture.nativeElement.textContent).toContain('CNPJ/CPF inválido');
    });

    it('manda o documento só com dígitos, mesmo digitado com máscara', () => {
      const { fixture, service } = montar(null);
      digitar(fixture, 'nome', 'Empresa X');
      digitar(fixture, 'email', 'x@x.com');
      digitar(fixture, 'cnpj', '11.222.333/0001-81');

      salvar(fixture);

      expect(service.criar).toHaveBeenCalledWith(
        expect.objectContaining({ cnpj: '11222333000181' }),
      );
    });

    it('mascara o documento enquanto se digita', () => {
      const { fixture } = montar(null);
      digitar(fixture, 'cnpj', '11222333000181');

      const valores = (
        fixture.componentInstance as never as {
          form: { getRawValue: () => Record<string, string> };
        }
      ).form.getRawValue();
      expect(valores['cnpj']).toBe('11.222.333/0001-81');
    });

    it('prazo em branco vira nulo, não zero', () => {
      const { fixture, service } = montar(null);
      digitar(fixture, 'nome', 'Empresa X');
      digitar(fixture, 'email', 'x@x.com');
      digitar(fixture, 'cnpj', '11222333000181');

      salvar(fixture);

      expect(service.criar).toHaveBeenCalledWith(
        expect.objectContaining({ prazo_entrega_dias: null }),
      );
    });

    it('fecha devolvendo o registro salvo — quem avisa e recarrega é a página', () => {
      const { fixture, dialogRef } = montar(null);
      digitar(fixture, 'nome', 'Empresa X');
      digitar(fixture, 'email', 'x@x.com');
      digitar(fixture, 'cnpj', '11222333000181');

      salvar(fixture);

      expect(dialogRef.close).toHaveBeenCalledWith(expect.objectContaining({ id: 9 }));
    });

    it('erro por campo do servidor aparece embaixo do campo, não num aviso genérico', () => {
      const { fixture, service } = montar(null);
      service.criar.mockReturnValue(
        throwError(() => ({
          error: { cnpj: ['Já existe um fornecedor com este CNPJ/CPF: "Beta".'] },
        })),
      );
      digitar(fixture, 'nome', 'Empresa X');
      digitar(fixture, 'email', 'x@x.com');
      digitar(fixture, 'cnpj', '11222333000181');

      salvar(fixture);

      expect(fixture.nativeElement.textContent).toContain('Já existe um fornecedor');
    });

    it('erro sem campo vira aviso no rodapé, para o modal nunca só "não salvar"', () => {
      const { fixture, service } = montar(null);
      service.criar.mockReturnValue(
        throwError(() => ({ error: { detail: 'Servidor indisponível.' } })),
      );
      digitar(fixture, 'nome', 'Empresa X');
      digitar(fixture, 'email', 'x@x.com');
      digitar(fixture, 'cnpj', '11222333000181');

      salvar(fixture);

      expect(fixture.debugElement.query(By.css('.erro')).nativeElement.textContent).toContain(
        'Servidor indisponível',
      );
    });
  });

  describe('edição', () => {
    it('abre preenchido, com o documento e o telefone já mascarados', () => {
      const { fixture } = montar(EXISTENTE);
      const valores = (
        fixture.componentInstance as never as {
          form: { getRawValue: () => Record<string, string> };
        }
      ).form.getRawValue();

      expect(valores['nome']).toBe('Marucci Distribuidora Ltda');
      expect(valores['cnpj']).toBe('11.222.333/0001-81');
      expect(valores['telefone']).toBe('(19) 3222-1100');
      expect(fixture.nativeElement.textContent).toContain('Editar fornecedor');
    });

    it('salva pelo endpoint de atualização, com o id do registro', () => {
      const { fixture, service } = montar(EXISTENTE);

      salvar(fixture);

      expect(service.atualizar).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ nome: 'Marucci Distribuidora Ltda' }),
      );
    });

    it('a situação escolhida no painel entra no payload', () => {
      const { fixture, service } = montar(EXISTENTE);
      const opcoes = fixture.debugElement.queryAll(By.css('.opcao-situacao'));
      opcoes[3].nativeElement.click();
      fixture.detectChanges();

      salvar(fixture);

      expect(service.atualizar).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ situacao: 'documentacao_vencida' }),
      );
    });
  });
});
