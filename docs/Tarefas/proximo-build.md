# Próximo build (definido com a operação em 09/11/2026)

Feito em partes pequenas: cada uma testada, salva e publicada sozinha.

| # | O quê | Situação |
|---|---|---|
| 9 | Servidor à prova de duas Sentinelas ligadas (não duplicar propostas; tarefa da lixeira feita não vira "erro") | feito (ramo claude/proximo-build), falta publicar |
| 10a | **Relatório do mês**: participou, ganhou, perdeu, faturamento, lucro (só com cotação no Licita) | feito, falta publicar |
| 11 | **Perdeu por pouco** (até 5%): uma linha só no relatório do mês, abre a lista curta ao clicar | feito, falta publicar |
| 10b | **Mercado de cada item** (itens em que ele participou): preço médio em 3/6/12/24 meses (gráfico pequeno), preço médio que ele ofereceu, 3 marcas que mais venceram. Item **exato** (CATMAT): descrição do edital → PDM (`modulo-material/3_consultarPdmMaterial`) → item do catálogo (`4_consultarItemMaterial?codigoPdm=`, semelhança ≥ 0,98) → `modulo-pesquisa-preco/1_consultarMaterial?tipo=codigoItemCatalogo`. O grupo (PDM) aparece só como referência; menos de 3 compras = "poucos dados". Testado em 09/11/2026: cadeira 171–200 kg = CATMAT 637928, 4 compras em 24 meses | feito (`mercado.py`), falta publicar |
| 12 | Fim da vigia por **contrato publicado no PNCP** (reserva: Portal da Transparência, federal) | a fazer |
| 13 | **Caixa de mensagens** do Compras.gov (`comprasnet-mensagem/v1/mensagens`) na ronda → sino. Ler a lista; se o texto não vier, abrir (marca como lida — autorizado pela operação) | feito (a lista já traz o texto: nada é aberto), falta publicar · Sentinela 0.2.4 |
| 14 | **Telegram**: os avisos do sino no celular (robô criado pela operação; chave só no `.env`) | a fazer |
| 16 | Tirar o "Ciclo de Licitação" antigo do código | a fazer |

Fora deste build:
- Painel da camada só com o item aberto e aviso de lance abaixo do piso: dependem de um .har da tela de lances (próximo pregão em disputa).
- Guarulhos 461/2026: o Compras.gov diz que está nos favoritos, mas não aparece em "Minhas participações". Investigar se repetir.
- Metabase: ainda não.
