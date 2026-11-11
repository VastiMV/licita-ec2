# feat/cadastro-empresa — os CNPJs do licitante e os documentos deles

Proposta: https://claude.ai/code/artifact/46ff524f-1317-4811-9a1c-23bf4c20ccdb
Mockup: [`docs/Mockups/cadastro_empresa/`](https://github.com/VastiMV/licita-ec2/tree/main/docs/Mockups/cadastro_empresa)

`Empresa` é cadastro novo e **não** é o `Fornecedor` com documentos: são os
CNPJs com que a equipe *disputa* (matriz, filial, a segunda empresa que cobre
outro CNAE), e quem monta a proposta escolhe qual usar. Poucos registros, e o
que importa neles é a habilitação.

O motor de documentos nasce aqui. Quando o `Fornecedor` ganhar sua aba, é este
código que ela usa — e aí `Fornecedor.situacao = "documentacao_vencida"`, hoje
marcado na mão, vira conta.

## Tarefas

### Empresa

- [x] **1. `Tenant`, com uma linha só**
  `apps/tenants`: model (nome, slug, ativo), uma linha criada por migração
  (Inside Solutions) e **uma função só** que resolve o tenant da requisição —
  hoje devolve o único que existe, amanhã lê do usuário ou do subdomínio.
  Não há tela de tenant. Os models antigos (`Fornecedor`, `OportunidadeSalva`,
  `Cotacao`) ficam como estão: ganham o campo no dia do segundo cliente, e a
  migração é trivial porque só há um tenant para apontar.
  *Teste antes:* a função devolve o tenant semeado; model novo sem tenant não
  salva.

- [x] **2. Model `Empresa`**
  Tenant obrigatório. Razão social, nome fantasia, CNPJ (dígito verificador
  reaproveitando `apps/fornecedores/documentos.py`, que já é genérico por
  decisão), inscrição estadual e municipal, **porte** (ME / EPP / demais — é o
  que dá empate ficto e prazo para regularizar certidão), CNAE principal,
  endereço, responsável legal, contato, `padrao` e `ativa`.
  Não há exclusão: empresa que já disputou se **inativa** (some do seletor de
  CNPJ, continua no histórico).
  *Teste antes:* CNPJ inválido recusado; CNPJ repetido no mesmo tenant
  recusado; marcar uma empresa como padrão desmarca a anterior; inativar não
  apaga.

- [x] **3. Endpoints de empresa**
  `GET/POST /api/empresas/`, `GET/PUT/DELETE(=inativar) /api/empresas/<id>/`,
  `GET /api/empresas/opcoes/` (o seletor de CNPJ). Mesmo contrato de tabela do
  resto do app: `busca`, `ordering`, `page`, `page_size`, com a whitelist de
  `ORDENACOES`. A contagem de documentos e a pior situação entram aqui junto
  com a tarefa 7, **anotadas na query** — nunca uma requisição por linha.
  *Teste antes:* contrato de cada um, ordenação fora da whitelist cai no
  padrão, busca casa CNPJ com e sem máscara.

- [x] **4. Tela de empresas**
  `pages/empresas/` + `empresa-modal/`, reusando `DataTableComponent`,
  `MenuComponent` + `TabelaAcoesDirective`, `ModalService.abrir()` +
  `ModalShellComponent`, `ToastService` e os tokens de `_tokens.scss` — o
  mockup vira os componentes da casa, não CSS novo. Colunas: razão social,
  CNPJ, cidade, porte, documentação, ações. "Empresas" entra no menu lateral
  ao lado de "Fornecedores". A coluna "Documentação" entra na tarefa 7, quando
  houver documento para contar; até lá a última coluna é a situação do
  cadastro (ativa / inativa).
  *Teste antes:* a empresa padrão é reconhecível na lista; a padrão não
  oferece "Inativar"; o modal devolve a empresa salva e a página recarrega.

### Documentos da empresa

- [x] **5. `TipoDocumento` — o catálogo**
  Os quatro blocos de habilitação da Lei 14.133 (jurídica; fiscal, social e
  trabalhista; econômico-financeira; técnica), semeados por migração, com
  `exige_validade` e `obrigatorio`. Mais um tipo livre "outro documento" para
  o que um edital específico pedir. Lista 100% livre não entra: vira pasta de
  computador em seis meses.
  *Teste antes:* a migração semeia o catálogo; tipo com `exige_validade=False`
  (contrato social, atestado) nunca conta como vencido.

- [x] **6. `Documento` e `VersaoDocumento`**
  `Documento` é a **vaga**: `(empresa, tipo)` única, sem arquivo e sem data.
  `VersaoDocumento` é o arquivo: chave no bucket, nome original, tamanho,
  hash, content-type, **número, emissão e validade**, quem enviou, quando e a
  nota da renovação — imutável depois de gravada. Empresa nova nasce com as
  vagas abertas, todas pendentes.
  *Teste antes:* nova versão vira corrente e empurra a anterior para o
  histórico; a versão antiga continua acessível; validade é da versão, não do
  documento.

- [x] **7. Situação calculada, nunca gravada**
  `pendente` (sem versão) · `valido` · `a_vencer` (≤ 30 dias) · `vencido`
  (validade < hoje) · `arquivado`. No queryset, comparando com hoje — campo
  gravado envelhece sozinho, que é exatamente o que aconteceu com
  `Fornecedor.situacao`. A empresa herda o pior dos seus documentos.
  *Teste antes:* cada estado com data de fronteira (hoje, ontem, hoje+30,
  hoje+31); empresa com um vencido fica vencida.

- [x] **8. `EventoDocumento`**
  Enviou, renovou, baixou, arquivou. Mesmo padrão de
  `EventoOportunidadeSalva` — a história se escreve desde o primeiro dia
  porque depois não dá para reconstruir.
  *Teste antes:* cada ação grava um evento com autor e momento.

- [x] **9. Endpoints de documento**
  Listar por empresa; criar versão (upload `multipart`, validando tipo e
  tamanho, calculando hash e gravando pelo `apps/armazenamento`); listar
  versões; baixar (redireciona para URL assinada de curta duração — o bucket
  nunca é público, certidão tem CNPJ e endereço); arquivar.
  *Teste antes:* upload grava no driver `local`, rejeita acima de 50 MB e
  extensão fora da lista; download não expõe a chave do bucket; arquivar não
  apaga.

- [x] **10. Documentos em modal próprio**
  Os três contadores, a dropzone (`shared/ui/upload-dropzone`, a única peça
  que o projeto ainda não tem — progresso real do `HttpClient`, não simulado),
  os chips de filtro, a lista agrupada por bloco com **coluna de validade** e
  ordenada por quem vence primeiro, e o histórico de versões que expande.
  *Teste antes:* progresso reflete o evento de upload; filtro por vencidos;
  "+ versão" é a ação principal da linha.

- [ ] **11. Fechar o ciclo** — **a confirmar.** *Estava bloqueado esperando o
  app `alertas`, mas Alertas saiu do produto (`feat-remover-legado`). Hoje os
  avisos nascem no sino (`apps/notificacoes`) e vão para o Telegram. Falta a
  operação dizer se este item continua e, se sim, se o aviso de vencimento
  vai para o sino.*
  Alerta de vencimento em 30, 15 e 3 dias, com link para o emissor (segundo
  tipo de alerta do módulo que já existe), e a mesma aba de documentos no
  cadastro de fornecedores — que é o que torna a situação dele calculada em
  vez de digitada.
  *Teste antes:* a task não duplica alerta do mesmo documento no mesmo dia.

- [x] **12. Documentação**
  `docs/DOMINIO.md`: `Empresa`, `TipoDocumento`, `Documento`,
  `VersaoDocumento` e a tabela de situações — no mesmo formato das entidades
  que já estão lá.
