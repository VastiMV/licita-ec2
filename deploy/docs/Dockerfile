# syntax=docker/dockerfile:1
#
# A imagem do site da documentação (GEN-63, 10/11/2026). Contexto: a raiz do
# repositório (precisa de mkdocs.yml e de docs/). Servida em /documentacao,
# atrás do login do Licita: quem confere é o Caddy (forward_auth no backend).

FROM python:3.13-slim AS build
WORKDIR /src
COPY docs/requirements.txt docs/requirements.txt
RUN pip install --no-cache-dir -r docs/requirements.txt
COPY mkdocs.yml ./
COPY docs ./docs
# --strict: link quebrado ou página fora do menu derruba o build.
RUN mkdocs build --strict

FROM nginx:1.27-alpine AS runtime
COPY deploy/docs/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/site /usr/share/nginx/html/documentacao
EXPOSE 80
