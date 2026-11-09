import { COTADA, FARROUPILHA, PMDF } from './torre.testing';
import {
  ganhandoDoCartao,
  localDoCartao,
  moeda,
  nivelDoCartao,
  prazoDoCartao,
  resumoDoItem,
  rotaDaEtapa,
  sinalDoItem,
  temRelatorio,
  trilhaDoCartao,
} from './torre.utils';

describe('torre.utils', () => {
  it('Oportunidade e Cotação abrem as listas que já existiam; as outras, a da Torre', () => {
    expect(rotaDaEtapa('oportunidade')).toBe('/oportunidades/salvas');
    expect(rotaDaEtapa('cotacao')).toBe('/ciclo/cotador');
    expect(rotaDaEtapa('homologado')).toBe('/torre/etapa/homologado');
  });

  it('valor em texto decimal vira moeda', () => {
    expect(moeda('239980.00')).toBe('R$\u00a0239.980,00');
    expect(moeda(null)).toBeNull();
  });

  it('o espaço depois de "R$" não quebra: o valor nunca se parte em duas linhas', () => {
    expect(moeda('15500.00')).not.toContain('R$ ');
    expect(moeda('15500.00')?.startsWith('R$\u00a0')).toBe(true);
  });

  it('resume o item numa linha: número, posição, situação e valor', () => {
    expect(resumoDoItem(FARROUPILHA.itens[0])).toBe(
      'Item 22 · 1º · Aguardando julgamento · R$\u00a0239.980,00',
    );
    expect(resumoDoItem(PMDF.itens[0])).toBe('Item 6 · 4º · perdendo · R$\u00a013.750,00');
    expect(resumoDoItem(PMDF.itens[2])).toBe(
      'Item 22 · 1º · Fornecedor habilitado · R$\u00a015.500,00',
    );
  });

  it('local e nível do cartão', () => {
    expect(localDoCartao(FARROUPILHA)).toBe('UASG 158127 · Santa Maria/RS');
    expect(nivelDoCartao(FARROUPILHA)).toBe('alerta');
    expect(nivelDoCartao(PMDF)).toBe('neutro');
  });

  it('prazo: aviso quando faltam 3 dias ou menos; fora de Preparar, nada', () => {
    expect(prazoDoCartao(COTADA, new Date(2026, 10, 14))).toEqual({
      texto: 'Proposta até 17/11',
      urgente: true,
    });
    expect(prazoDoCartao(COTADA, new Date(2026, 10, 7))?.urgente).toBe(false);
    expect(prazoDoCartao(FARROUPILHA)).toBeNull();
  });

  it('a trilha de Preparar começa na etapa de agora', () => {
    expect(trilhaDoCartao(COTADA).map((p) => p.rotulo)).toEqual([
      'Cotação',
      'Cadastro de proposta',
    ]);
  });

  it('👍 / 🟠 / 👎 de cada item e "ganhando 1 de 3" no cartão', () => {
    expect(sinalDoItem(FARROUPILHA.itens[0])?.icone).toBe('👍');
    expect(sinalDoItem({ ...PMDF.itens[0], sinal: 'proximo' })).toEqual({
      icone: '🟠',
      texto: 'Próximo a ser chamado',
    });
    expect(
      sinalDoItem({ ...PMDF.itens[0], perdido: 'homologado para outro fornecedor' })?.texto,
    ).toBe('Perdeu: homologado para outro fornecedor');
    expect(sinalDoItem({ ...PMDF.itens[0], sinal: '' })).toBeNull();
    expect(ganhandoDoCartao(PMDF)).toBe('👍 ganhando 1 de 3');
    expect(ganhandoDoCartao({ ...PMDF, itens_com_posicao: 0 })).toBeNull();
  });

  it('relatório só do Disputar em diante, com itens', () => {
    expect(temRelatorio(PMDF)).toBe(true);
    expect(temRelatorio(COTADA)).toBe(false);
  });
});
