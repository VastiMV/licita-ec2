# Licita — Documentação

Plataforma da **Inside Solutions** para encontrar, cotar e acompanhar
licitações públicas (Lei 14.133), integrando com o PNCP e o Compras.gov.br.

## Por onde começar

1. [Torre de Controle](TORRE.md) — o coração do sistema: etapas, de onde vem
   cada dado, em que arquivo está cada regra.
2. [Domínio e regras](DOMINIO.md) — as outras regras de negócio e o
   histórico de decisões (o "porquê").
3. [Sentinela](SENTINELA.md) — a extensão do Chrome que lê o Compras.gov.br.
4. [Arquitetura](ARQUITETURA.md) — como o código se organiza e onde roda.
5. [Tarefas](Tarefas/README.md) — onde paramos e o que vem depois.

## Como esta documentação é mantida

- Fica no repositório, na pasta `docs/`, e é atualizada **no mesmo pull
  request** de cada mudança no código (regra do `AGENTS.md`).
- O README do repositório e os guias de `deploy/ec2/` e `sentinela/` ficam
  fora deste site; estão no GitHub.
