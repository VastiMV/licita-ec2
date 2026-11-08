import { FARROUPILHA, PMDF } from './torre.testing';
import { localDoCartao, moeda, nivelDoCartao, resumoDoItem, rotaDaEtapa } from './torre.utils';

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
});
