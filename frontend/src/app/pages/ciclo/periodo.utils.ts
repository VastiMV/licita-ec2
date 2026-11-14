/**
 * O campo "Período" de Encerradas e Descartadas: os últimos dias, um mês
 * ou datas escolhidas. As duas telas têm os mesmos filtros (GEN-55).
 */

/** Período que a tela abre consultando — o usuário muda antes de pesquisar. */
export const JANELA_PADRAO_DIAS = 90;

/** Valores especiais do campo Período (os outros são meses `aaaa-mm`). */
export const PADRAO = 'ultimos';
export const PERSONALIZADO = 'datas';

const NOMES_MES = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

/** Os últimos 12 meses, do atual para trás — `value` é `aaaa-mm`. */
export function ultimosMeses(hoje: string, quantos = 12): { value: string; label: string }[] {
  let [ano, mes] = hoje.split('-').map(Number);
  const meses: { value: string; label: string }[] = [];
  for (let i = 0; i < quantos; i++) {
    meses.push({
      value: `${ano}-${String(mes).padStart(2, '0')}`,
      label: `${NOMES_MES[mes - 1]} de ${ano}`,
    });
    mes -= 1;
    if (mes === 0) {
      mes = 12;
      ano -= 1;
    }
  }
  return meses;
}

/** Primeiro e último dia do mês `aaaa-mm`, em `aaaa-mm-dd`. */
export function limitesDoMes(mes: string): { inicio: string; fim: string } {
  const [ano, m] = mes.split('-').map(Number);
  const ultimoDia = new Date(Date.UTC(ano, m, 0)).getUTCDate();
  const mm = String(m).padStart(2, '0');
  return { inicio: `${ano}-${mm}-01`, fim: `${ano}-${mm}-${String(ultimoDia).padStart(2, '0')}` };
}

/** As opções do campo Período: os últimos dias, os 12 meses e "Escolher datas…". */
export function opcoesDePeriodo(hoje: string): { value: string; label: string }[] {
  return [
    { value: PADRAO, label: `Últimos ${JANELA_PADRAO_DIAS} dias` },
    ...ultimosMeses(hoje),
    { value: PERSONALIZADO, label: 'Escolher datas…' },
  ];
}
