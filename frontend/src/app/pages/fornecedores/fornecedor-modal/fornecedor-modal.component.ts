import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import {
  CATEGORIAS_FORNECEDOR,
  CONDICOES_PAGAMENTO,
  FornecedorRequest,
  FornecedorResponse,
  SITUACOES_FORNECEDOR,
  SituacaoFornecedor,
  TIPOS_FORNECEDOR,
} from '../../../contracts/fornecedores/fornecedor.contracts';
import { UFS } from '../../../contracts/localidades/uf';
import { FornecedoresService } from '../../../services/fornecedores/fornecedores.service';
import { ModalShellComponent } from '../../../shared/overlay/modal-shell/modal-shell.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { InputTextComponent } from '../../../shared/ui/input-text/input-text.component';
import { SelectComponent } from '../../../shared/ui/select/select.component';
import {
  documentoValido,
  mascararCep,
  mascararDocumento,
  mascararTelefone,
  somenteDigitos,
} from '../../../shared/documento/documento';

/** Campo que o backend pode recusar, mapeado para a mensagem da tela. Só
 * estes viram erro embaixo do campo; o resto cai no aviso do rodapé. */
const CAMPOS = [
  'nome',
  'fantasia',
  'cnpj',
  'inscricao_estadual',
  'email',
  'telefone',
  'celular',
  'responsavel',
  'cep',
  'logradouro',
  'numero',
  'complemento',
  'bairro',
  'cidade',
  'uf',
  'dados_bancarios',
  'chave_pix',
  'observacoes',
  'prazo_entrega_dias',
] as const;

/** Documento é opcional (GEN-19, 10/11/2026): vazio passa; digitado, tem
 * que ser válido. Função de módulo (e não método) porque o
 * `form` é inicializado na declaração do campo, antes de qualquer membro de
 * instância existir. */
function validarDocumento(controle: AbstractControl): ValidationErrors | null {
  const valor = String(controle.value ?? '');
  return !valor || documentoValido(valor) ? null : { documento: true };
}

/**
 * O modal que cadastra **e** edita um fornecedor — um só, porque o
 * formulário é idêntico nos dois casos: o que muda é o título, o rótulo do
 * botão e se há um id para atualizar.
 *
 * Fecha devolvendo o fornecedor salvo (ou `undefined` se cancelaram), e é a
 * página que avisa e recarrega a lista — o modal não conhece a tabela.
 *
 * A validação daqui é conveniência: dizer "confira o dígito" antes do
 * clique. Quem decide é o backend, e o erro que ele devolver por campo
 * aparece embaixo do campo certo (ver `aplicarErrosDoServidor`).
 */
@Component({
  selector: 'app-fornecedor-modal',
  imports: [
    ReactiveFormsModule,
    ModalShellComponent,
    ButtonComponent,
    InputTextComponent,
    SelectComponent,
  ],
  templateUrl: './fornecedor-modal.component.html',
  styleUrl: './fornecedor-modal.component.scss',
})
export class FornecedorModalComponent {
  private readonly dialogRef = inject(DialogRef<FornecedorResponse>);
  private readonly fb = inject(FormBuilder);
  private readonly service = inject(FornecedoresService);

  /** `null` = cadastrar; um registro = editar. */
  protected readonly fornecedor = inject<FornecedorResponse | null>(DIALOG_DATA);

  protected readonly tipos = TIPOS_FORNECEDOR;
  protected readonly categorias = CATEGORIAS_FORNECEDOR;
  protected readonly condicoes = CONDICOES_PAGAMENTO;
  protected readonly situacoes = SITUACOES_FORNECEDOR;
  protected readonly ufs = UFS;

  protected readonly salvando = signal(false);
  protected readonly erroGeral = signal<string | null>(null);
  /** Erros que o backend devolveu por campo, para a mensagem aparecer
   * embaixo do campo certo em vez de num aviso genérico no rodapé. */
  protected readonly errosDoServidor = signal<Record<string, string>>({});

  /** Situação é botão, não `<select>`: é a decisão que pinta a linha na
   * tabela e merece peso visual (ver o handoff em `docs/Mockups/fornecedores`). */
  protected readonly situacao = signal<SituacaoFornecedor>(this.fornecedor?.situacao ?? 'ativo');

  protected readonly form = this.fb.nonNullable.group({
    nome: [this.fornecedor?.nome ?? '', Validators.required],
    fantasia: [this.fornecedor?.fantasia ?? ''],
    tipo: [this.fornecedor?.tipo ?? 'pj'],
    cnpj: [
      this.fornecedor ? mascararDocumento(this.fornecedor.cnpj) : '',
      // Opcional (GEN-19): no Cotador o fornecedor nasce sem CNPJ.
      [validarDocumento],
    ],
    inscricao_estadual: [this.fornecedor?.inscricao_estadual ?? ''],
    categoria: [this.fornecedor?.categoria ?? 'materiais', Validators.required],

    cep: [this.fornecedor ? mascararCep(this.fornecedor.cep) : ''],
    logradouro: [this.fornecedor?.logradouro ?? ''],
    numero: [this.fornecedor?.numero ?? ''],
    complemento: [this.fornecedor?.complemento ?? ''],
    bairro: [this.fornecedor?.bairro ?? ''],
    uf: [this.fornecedor?.uf ?? 'SP'],
    cidade: [this.fornecedor?.cidade ?? ''],

    responsavel: [this.fornecedor?.responsavel ?? ''],
    email: [this.fornecedor?.email ?? '', [Validators.email]],
    telefone: [this.fornecedor ? mascararTelefone(this.fornecedor.telefone) : ''],
    celular: [this.fornecedor ? mascararTelefone(this.fornecedor.celular) : ''],

    condicao_pagamento: [this.fornecedor?.condicao_pagamento ?? '30_dias'],
    prazo_entrega_dias: [
      this.fornecedor?.prazo_entrega_dias != null ? String(this.fornecedor.prazo_entrega_dias) : '',
    ],
    dados_bancarios: [this.fornecedor?.dados_bancarios ?? ''],
    chave_pix: [this.fornecedor?.chave_pix ?? ''],
    observacoes: [this.fornecedor?.observacoes ?? ''],
  });

  constructor() {
    // As máscaras são aplicadas no próprio controle enquanto se digita —
    // `emitEvent: false` evita o laço infinito de reescrever e reagir.
    this.mascarar('cnpj', mascararDocumento);
    this.mascarar('cep', mascararCep);
    this.mascarar('telefone', mascararTelefone);
    this.mascarar('celular', mascararTelefone);
  }

  protected get editando(): boolean {
    return this.fornecedor !== null;
  }

  protected escolherSituacao(situacao: SituacaoFornecedor): void {
    this.situacao.set(situacao);
  }

  /** Mensagem do campo: a do servidor tem prioridade sobre a da tela — ela
   * é mais específica ("já existe um fornecedor com este CNPJ: X"). */
  protected erroDe(campo: string): string | null {
    const doServidor = this.errosDoServidor()[campo];
    if (doServidor) return doServidor;

    const controle = this.form.get(campo);
    if (!controle || controle.valid || !controle.touched) return null;

    if (controle.hasError('required')) return 'Campo obrigatório.';
    if (controle.hasError('email')) return 'E-mail inválido.';
    if (controle.hasError('documento')) return 'CNPJ/CPF inválido — confira os dígitos.';
    return 'Valor inválido.';
  }

  protected salvar(): void {
    this.form.markAllAsTouched();
    this.errosDoServidor.set({});
    this.erroGeral.set(null);

    if (this.form.invalid || this.salvando()) return;

    this.salvando.set(true);
    const payload = this.montarPayload();
    const requisicao = this.fornecedor
      ? this.service.atualizar(this.fornecedor.id, payload)
      : this.service.criar(payload);

    requisicao.subscribe({
      next: (salvo) => {
        this.salvando.set(false);
        this.dialogRef.close(salvo);
      },
      error: (erro) => {
        this.salvando.set(false);
        this.aplicarErrosDoServidor(erro);
      },
    });
  }

  protected fechar(): void {
    this.dialogRef.close();
  }

  /** O documento vai só com dígitos, e o prazo como número ou nulo — é o
   * que o backend espera (ver `FornecedorSerializer`). */
  private montarPayload(): FornecedorRequest {
    const valores = this.form.getRawValue();
    const prazo = valores.prazo_entrega_dias.trim();

    return {
      ...valores,
      cnpj: somenteDigitos(valores.cnpj),
      cep: somenteDigitos(valores.cep),
      prazo_entrega_dias: prazo ? Number(prazo) : null,
      situacao: this.situacao(),
    } as FornecedorRequest;
  }

  private aplicarErrosDoServidor(erro: unknown): void {
    const corpo = (erro as { error?: Record<string, unknown> })?.error;
    if (!corpo || typeof corpo !== 'object') {
      this.erroGeral.set('Não foi possível salvar o fornecedor agora.');
      return;
    }

    const porCampo: Record<string, string> = {};
    for (const campo of CAMPOS) {
      const mensagem = corpo[campo];
      if (mensagem) porCampo[campo] = Array.isArray(mensagem) ? mensagem[0] : String(mensagem);
    }
    this.errosDoServidor.set(porCampo);

    // O que não casou com nenhum campo (`non_field_errors`, 500, rede) ainda
    // precisa aparecer — senão o modal só "não salva", sem dizer por quê.
    const semCampo = corpo['detail'] ?? corpo['non_field_errors'];
    if (Object.keys(porCampo).length === 0) {
      this.erroGeral.set(
        semCampo
          ? String(Array.isArray(semCampo) ? semCampo[0] : semCampo)
          : 'Não foi possível salvar o fornecedor agora.',
      );
    }
  }

  private mascarar(campo: string, mascara: (valor: string) => string): void {
    const controle = this.form.get(campo)!;
    controle.valueChanges.pipe(takeUntilDestroyed()).subscribe((valor) => {
      const formatado = mascara(String(valor ?? ''));
      if (formatado !== valor) controle.setValue(formatado, { emitEvent: false });
    });
  }
}
