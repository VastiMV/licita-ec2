import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import { OportunidadeResponse } from '../../../contracts/licitacoes/oportunidade.contracts';
import { DetalheEstado, EditalCard } from './edital-card.model';
import { EditalCardComponent } from './edital-card.component';

// Construído com componentes locais (não uma string ISO) pra não depender
// do fuso horário de quem roda o teste — ver o mesmo cuidado em `parseData`.
const HOJE = new Date(2026, 7, 27);

const OPORTUNIDADE: OportunidadeResponse = {
  numero_item: '1',
  descricao_resumida: 'Locação de máquina de café expresso',
  descricao_detalhada: null,
  quantidade: 4,
  unidade_medida: 'Diária',
  valor_unitario_estimado: 2370,
  valor_total: 9480,
  tipo_beneficio: null,
  criterio_julgamento: 'Menor preço',
  contratacao_uf: 'GO',
  contratacao_modalidade: 'Dispensa eletrônica',
  contratacao_srp: false,
  contratacao_situacao: 'Divulgada no PNCP',
  situacao_item: null,
  contratacao_data_publicacao: '2026-08-26',
  contratacao_data_encerramento_proposta: '2026-09-01',
  contratacao_orgao_nome: 'Prefeitura Municipal de Rio Verde',
  contratacao_municipio: 'Rio Verde',
  contratacao_uasg: '989571',
  contratacao_objeto: 'LOCAÇÃO DE 01 MÁQUINA PARA CAFÉ EXPRESSO PARA O ESTANDE EM GO, UASG 989571',
  contratacao_cnpj_orgao: '12345678000199',
  contratacao_ano_compra: '2026',
  contratacao_sequencial_compra: '1',
  plataforma_id: 'compras_gov',
  link_plataforma:
    'https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra=98957106000012026',
  link_pncp: 'https://pncp.gov.br/app/editais/12345678000199/2026/1',
  capag: null,
};

function montarCard(itens: readonly OportunidadeResponse[] = [OPORTUNIDADE]): EditalCard {
  return { chave: 'edital-1', contratacao: itens[0], itens };
}

const DETALHE_CARREGADO: DetalheEstado = {
  carregando: false,
  erro: false,
  capag: { nota: 'B', cor: 'amarelo' },
  plataforma: null,
  documentos: [
    {
      titulo: 'Aviso de dispensa.pdf',
      tipo_documento: 'Aviso de Contratação Direta',
      url: 'https://pncp.gov.br/x/1',
    },
  ],
};

@Component({
  imports: [EditalCardComponent],
  template: `<app-edital-card
    [card]="card()"
    [detalhe]="detalhe()"
    [salva]="salva()"
    [salvando]="salvando()"
    [podeSalvar]="podeSalvar()"
    [recolherItens]="recolherItens()"
    (salvar)="salvarPedido.set(true)"
    (baixarEdital)="baixarEdital.set(true)"
  />`,
})
class HostComponent {
  readonly card = signal<EditalCard>(montarCard());
  readonly detalhe = signal<DetalheEstado | undefined>(undefined);
  readonly salva = signal(false);
  readonly salvando = signal(false);
  readonly podeSalvar = signal(true);
  readonly recolherItens = signal(false);
  readonly salvarPedido = signal(false);
  readonly baixarEdital = signal(false);
}

describe('EditalCardComponent', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(() => {
    vi.useFakeTimers().setSystemTime(HOJE);
    TestBed.configureTestingModule({ imports: [HostComponent] });
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function texto(): string {
    return fixture.debugElement.nativeElement.textContent;
  }

  function clicarBotao(seletor: string): void {
    fixture.debugElement.query(By.css(seletor)).nativeElement.click();
    fixture.detectChanges();
  }

  it('normaliza o objeto em CAIXA ALTA do PNCP pra sentence case, preservando siglas', () => {
    const titulo = fixture.debugElement.query(By.css('.titulo')).nativeElement.textContent;
    expect(titulo).toBe(
      'Locação de 01 máquina para café expresso para o estande em GO, UASG 989571',
    );
  });

  it('mostra os dados do edital, com o valor estimado somado dos itens', () => {
    expect(texto()).toContain('Rio Verde / GO');
    expect(texto()).toContain('Dispensa eletrônica');
    expect(texto()).toContain('R$ 9.480,00');
  });

  it('aba "Itens" é a padrão, com a tabela desktop e os cartões mobile preenchidos', () => {
    expect(
      fixture.debugElement.query(By.css('.aba.aba-ativa')).nativeElement.textContent,
    ).toContain('Itens');
    expect(fixture.debugElement.query(By.css('.tabela-linha')).nativeElement.textContent).toContain(
      'Locação de máquina de café expresso',
    );
  });

  describe('itens recolhidos na busca (GEN-30)', () => {
    const CINCO = Array.from({ length: 5 }, (_, i) => ({
      ...OPORTUNIDADE,
      numero_item: String(i + 1),
      descricao_resumida: `Item ${i + 1}`,
    }));

    function linhas(): number {
      return fixture.debugElement.queryAll(By.css('.tabela-linha')).length;
    }

    it('com mais de 3 itens, mostra só os 3 primeiros e "Ver todos"; o total soma todos', () => {
      host.card.set(montarCard(CINCO));
      host.recolherItens.set(true);
      fixture.detectChanges();

      expect(linhas()).toBe(3);
      expect(fixture.debugElement.queryAll(By.css('.cartao-item')).length).toBe(3);
      expect(texto()).toContain('Ver todos os 5 itens');
      expect(texto()).toContain('5 itens · valor');
    });

    it('"Ver todos" abre a lista inteira e "Mostrar menos" recolhe de novo', () => {
      host.card.set(montarCard(CINCO));
      host.recolherItens.set(true);
      fixture.detectChanges();

      clicarBotao('.ver-todos');
      expect(linhas()).toBe(5);
      expect(texto()).toContain('Mostrar menos');

      clicarBotao('.ver-todos');
      expect(linhas()).toBe(3);
    });

    it('com até 3 itens, ou fora da busca, mostra tudo e não tem o botão', () => {
      host.card.set(montarCard(CINCO.slice(0, 3)));
      host.recolherItens.set(true);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('.ver-todos'))).toBeNull();

      host.card.set(montarCard(CINCO));
      host.recolherItens.set(false);
      fixture.detectChanges();
      expect(linhas()).toBe(5);
      expect(fixture.debugElement.query(By.css('.ver-todos'))).toBeNull();
    });
  });

  it('clicar em "Documentos" troca de painel', () => {
    host.detalhe.set(DETALHE_CARREGADO);
    fixture.detectChanges();

    clicarBotao('.aba:nth-child(2)');

    expect(fixture.debugElement.query(By.css('.painel-documentos'))).not.toBeNull();
    expect(fixture.debugElement.query(By.css('.painel-itens'))).toBeNull();
    expect(texto()).toContain('Aviso de dispensa.pdf');
  });

  it('painel "Documentos" mostra carregando/erro/vazio conforme o detalhe', () => {
    host.detalhe.set({
      carregando: true,
      erro: false,
      capag: null,
      plataforma: null,
      documentos: [],
    });
    fixture.detectChanges();
    clicarBotao('.aba:nth-child(2)');
    expect(texto()).toContain('Buscando os documentos no PNCP');

    host.detalhe.set({
      carregando: false,
      erro: true,
      capag: null,
      plataforma: null,
      documentos: [],
    });
    fixture.detectChanges();
    expect(texto()).toContain('Não foi possível buscar os documentos agora');

    host.detalhe.set({
      carregando: false,
      erro: false,
      capag: null,
      plataforma: null,
      documentos: [],
    });
    fixture.detectChanges();
    expect(texto()).toContain('Nenhum documento informado');
  });

  it('selo CAPAG vindo da própria busca aparece na hora, sem esperar o detalhe', () => {
    host.card.set(montarCard([{ ...OPORTUNIDADE, capag: { nota: 'A', cor: 'verde' } }]));
    fixture.detectChanges();

    const selo = fixture.debugElement.query(By.css('.selo-capag'));
    expect(selo.nativeElement.textContent).toContain('CAPAG A');
    expect(selo.nativeElement.className).toContain('capag-verde');
  });

  it('selo CAPAG aparece com a cor certa quando carrega, e "CAPAG…" enquanto isso', () => {
    host.detalhe.set({
      carregando: true,
      erro: false,
      capag: null,
      plataforma: null,
      documentos: [],
    });
    fixture.detectChanges();
    expect(texto()).toContain('CAPAG…');

    host.detalhe.set(DETALHE_CARREGADO);
    fixture.detectChanges();
    const selo = fixture.debugElement.query(By.css('.selo-capag'));
    expect(selo.nativeElement.textContent).toContain('CAPAG B');
    expect(selo.nativeElement.className).toContain('capag-amarelo');
  });

  it('"Baixar edital" só aparece quando há documento, e avisa o pai ao clicar', () => {
    expect(fixture.debugElement.query(By.css('.btn-baixar'))).toBeNull();

    host.detalhe.set(DETALHE_CARREGADO);
    fixture.detectChanges();

    clicarBotao('.btn-baixar');
    expect(host.baixarEdital()).toBe(true);
  });

  it('"Salvar oportunidade" só avisa o pai — quem confirma e persiste é a página', () => {
    expect(texto()).toContain('Salvar oportunidade');

    clicarBotao('.btn-salvar');

    expect(host.salvarPedido()).toBe(true);
    // O card não decide sozinho que salvou: o estado vem do pai.
    expect(texto()).toContain('Salvar oportunidade');
  });

  it('já salva, mostra o estado sem caminho de volta (remover é no módulo de salvas)', () => {
    host.salva.set(true);
    fixture.detectChanges();

    expect(texto()).toContain('Oportunidade salva');
    expect(fixture.debugElement.query(By.css('.btn-salvar'))).toBeNull();
    expect(fixture.debugElement.query(By.css('.link-remover'))).toBeNull();
  });

  it('enquanto a página salva, o botão fica desabilitado e avisa', () => {
    host.salvando.set(true);
    fixture.detectChanges();

    const botao = fixture.debugElement.query(By.css('.btn-salvar'));
    expect(botao.nativeElement.disabled).toBe(true);
    expect(botao.nativeElement.textContent).toContain('Salvando');
  });

  it('não tem "Cotar" — cotar é de dentro da oportunidade salva', () => {
    expect(fixture.debugElement.query(By.css('.btn-cotar'))).toBeNull();
  });

  it('`podeSalvar` desligado tira o botão (modal do módulo de salvas)', () => {
    host.podeSalvar.set(false);
    fixture.detectChanges();

    expect(fixture.debugElement.query(By.css('.btn-salvar'))).toBeNull();
  });

  it('botão dourado abre o link da plataforma, com nome e favicon da registrada', () => {
    const botao = fixture.debugElement.query(By.css('.btn-plataforma'));
    expect(botao.nativeElement.getAttribute('href')).toContain('compra=98957106000012026');
    expect(texto()).toContain('Abrir na plataforma');
    expect(texto()).toContain('Compras.gov.br');
    // Favicon no chip da esquerda; a seta de ação fica à direita.
    expect(fixture.debugElement.query(By.css('.btn-plataforma-chip img'))).not.toBeNull();
    expect(fixture.debugElement.query(By.css('.btn-plataforma-icone'))).not.toBeNull();
  });

  it('o link do detalhe (linkSistemaOrigem) tem prioridade sobre o da busca', () => {
    host.detalhe.set({
      ...DETALHE_CARREGADO,
      plataforma: {
        id: null,
        nome: 'Portal de Compras Públicas',
        link: 'https://www.portaldecompraspublicas.com.br/processos/x',
      },
    });
    fixture.detectChanges();

    const botao = fixture.debugElement.query(By.css('.btn-plataforma'));
    expect(botao.nativeElement.getAttribute('href')).toContain('portaldecompraspublicas');
    expect(texto()).toContain('Portal de Compras Públicas');
    // Plataforma fora do registro: sem favicon próprio, ícone genérico no chip.
    expect(fixture.debugElement.query(By.css('.btn-plataforma-chip img'))).toBeNull();
    expect(fixture.debugElement.query(By.css('.btn-plataforma-chip app-icon'))).not.toBeNull();
  });

  it('o botão dourado aparece sempre — o backend garante o link', () => {
    // Mesmo encerrada, e mesmo antes do detalhe chegar.
    host.card.set(
      montarCard([{ ...OPORTUNIDADE, contratacao_data_encerramento_proposta: '2026-08-01' }]),
    );
    fixture.detectChanges();

    expect(fixture.debugElement.query(By.css('.btn-plataforma'))).not.toBeNull();
  });

  it('licitação encerrada esconde o botão de salvar e mostra "Encerrada"', () => {
    host.card.set(
      montarCard([{ ...OPORTUNIDADE, contratacao_data_encerramento_proposta: '2026-08-01' }]),
    );
    fixture.detectChanges();

    expect(fixture.debugElement.query(By.css('.btn-salvar'))).toBeNull();
    expect(texto()).toContain('Encerrada');
  });

  it('encerrada avisa, em texto, que não dá mais pra gerar proposta', () => {
    host.card.set(
      montarCard([{ ...OPORTUNIDADE, contratacao_data_encerramento_proposta: '2026-08-01' }]),
    );
    fixture.detectChanges();

    const aviso = fixture.debugElement.query(By.css('.aviso-encerrada'));
    expect(aviso).not.toBeNull();
    expect(aviso.nativeElement.textContent).toContain('01/08/2026');
    expect(aviso.nativeElement.textContent).toContain('Não é mais possível gerar proposta');
  });
});
