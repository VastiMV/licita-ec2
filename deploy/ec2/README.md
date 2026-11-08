# Licita no EC2: passo a passo

O Licita inteiro numa máquina só da AWS, com HTTPS em
**insidelicitacoes.com.br**. Sem Kubernetes: `docker compose` com as mesmas
imagens que o GitHub gera.

São 4 etapas, **feitas uma vez só**. Depois disso, atualizar é um botão.

## Como está instalado hoje

| Item | Valor |
|---|---|
| Máquina | EC2 `licita`, **t3.small**, Ubuntu 24.04, região **us-east-2 (Ohio)** |
| IP fixo (Elastic IP) | `16.59.20.70` |
| Endereço provisório | `https://16-59-20-70.sslip.io` (teste: `https://teste.16-59-20-70.sslip.io`) |
| Domínio definitivo | `insidelicitacoes.com.br` — **DNS ainda não configurado** (ver "Trocar para o domínio definitivo") |
| Senhas | `/opt/licita/.env` (produção) e `/opt/licita-teste/.env` (teste) — só no servidor; a dona guarda cópia fora dele |
| Acesso ao terminal | AWS → EC2 → `licita` → Connect → EC2 Instance Connect |
| Segredos do GitHub | `EC2_HOST`, `EC2_SSH_KEY` (chave `licita.pem`) |
| Backup do banco | automático a cada deploy, em `/opt/licita/backups/` (ver "Backup do banco") — **só dentro da máquina** |
| Chave do Portal da Transparência | `PORTAL_TRANSPARENCIA_CHAVE` em `/opt/licita/.env` (ver "Sincronias diárias") |

O sslip.io é um serviço gratuito em que o nome já contém o IP — serve para
ter HTTPS antes do DNS do domínio estar pronto. É provisório.

---

## Etapa 1: criar a máquina (EC2)

No console da AWS → **EC2** → **Launch instance**:

| Campo | O que escolher |
|---|---|
| Região (canto de cima) | **São Paulo (sa-east-1)** |
| Name | `licita` |
| Imagem (AMI) | **Ubuntu Server 24.04 LTS** |
| Instance type | **t3.small** (2 GB). Mais folga: t3.medium |
| Key pair | **Create new key pair** → nome `licita` → tipo RSA → formato **.pem**. **Guarde o arquivo baixado.** |
| Network settings | Marque **Allow SSH**, **Allow HTTPS** e **Allow HTTP** |
| Storage | **30 GB** (gp3) |

Clique **Launch instance**.

### IP fixo (obrigatório)

Sem isto, o IP muda quando a máquina reinicia e o site sai do ar.

EC2 → **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**.
Depois: **Actions** → **Associate Elastic IP address** → escolha a
instância `licita` → **Associate**. **Anote esse IP.**

## Etapa 2: apontar o domínio (registro.br)

No registro.br → **insidelicitacoes.com.br** → **DNS** → **Editar zona**
(se pedir, ative o "Modo avançado"). Crie duas entradas:

| Tipo | Nome | Valor |
|---|---|---|
| A | *(vazio)* | o IP da Etapa 1 |
| A | `www` | o IP da Etapa 1 |

Salve. Pode levar de alguns minutos a algumas horas para valer.

## Etapa 3: preparar a máquina

No console da AWS → EC2 → selecione `licita` → **Connect** → aba
**EC2 Instance Connect** → **Connect**. Abre um terminal no navegador.

Cole este comando e aperte Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/VastiMV/licita-ec2/main/deploy/ec2/instalar.sh | bash -s -- insidelicitacoes.com.br
```

Ele instala o Docker, cria `/opt/licita` e gera as senhas em
`/opt/licita/.env`.

**Faça uma cópia do `.env`** (`cat /opt/licita/.env` e salve o texto num
lugar seguro). Sem ele, o banco não abre.

## Etapa 4: ligar o GitHub ao EC2

No GitHub → **VastiMV/licita-ec2** → **Settings** → **Secrets and
variables** → **Actions** → **New repository secret**. Crie dois:

| Nome | Valor |
|---|---|
| `EC2_HOST` | o IP da Etapa 1 |
| `EC2_SSH_KEY` | abra o arquivo `licita.pem` no Bloco de Notas e cole **tudo**, das linhas `-----BEGIN` até `-----END` |

## Primeiro deploy

GitHub → **Actions** → **Deploy EC2** → **Run workflow** → **Run workflow**.

Leva uns 10 minutos (gera as imagens e sobe tudo). Quando ficar verde,
volte ao terminal da Etapa 3 e crie o seu login:

```bash
cd /opt/licita && sudo docker compose exec backend python manage.py createsuperuser
```

Abra **https://insidelicitacoes.com.br**.

---

## Trocar para o domínio definitivo

Quando o registro.br liberar a edição do DNS:

1. No registro.br, crie as entradas **A** (Etapa 2): vazio, `www` e
   `teste`, todas com o IP fixo.
2. Espere o domínio responder (pode levar até algumas horas).
3. No terminal do EC2:

```bash
sudo sed -i 's/^DOMINIO=.*/DOMINIO=insidelicitacoes.com.br/' /opt/licita/.env
```

4. Rode **Deploy EC2** (pode desmarcar "Gerar imagens"). O Caddy tira os
   certificados do domínio novo sozinho.

`DJANGO_ALLOWED_HOSTS` já aceita `insidelicitacoes.com.br` e o `www`.

## No dia a dia

**Atualizar a produção** depois de um merge na `main`:
Actions → **Deploy EC2** → Run workflow. Só isso.

**Ver se está tudo de pé** (no terminal do EC2):

```bash
cd /opt/licita && sudo docker compose ps
```

**Ver os erros do backend:**

```bash
cd /opt/licita && sudo docker compose logs --tail 100 backend
```

## Sincronias diárias (PNCP e Portal da Transparência)

De segunda a sexta, sozinho (Celery Beat) — fim de semana não tem movimentação:

- **8h — PNCP:** traz os itens que a empresa ganhou e as atas de registro de
  preços, para cada CNPJ ativo em Cadastros › Empresas. Licitação ganha que
  não estava salva no Licita é criada.
- **8h10 — Portal da Transparência:** traz empenho, liquidação e pagamento
  dos órgãos **federais** e liga cada um à licitação.

O Portal da Transparência precisa de uma **chave** (pessoal e gratuita:
cadastro com gov.br em portaldatransparencia.gov.br/api-de-dados/cadastrar-email).
Ela fica no `.env` do servidor, nunca no código. Para colocar (troque
`SUA_CHAVE` pela chave que chegou por e-mail):

```bash
echo 'PORTAL_TRANSPARENCIA_CHAVE=SUA_CHAVE' | sudo tee -a /opt/licita/.env > /dev/null
```

```bash
cd /opt/licita && sudo docker compose up -d backend worker beat
```

Sem a chave, a sincronia do Portal só avisa no log e não roda; o resto
funciona.

**Rodar na hora** (sem esperar as 8h), logo depois de um deploy:

```bash
cd /opt/licita && sudo docker compose exec backend python manage.py sincronizar_pncp
```

```bash
cd /opt/licita && sudo docker compose exec backend python manage.py sincronizar_transparencia
```

## Sentinela (a extensão do Chrome)

A extensão fala com o Licita usando uma **chave** que só existe no servidor
e nas opções da extensão. Para criar (uma vez só), no terminal do EC2:

```bash
CHAVE=$(openssl rand -hex 24); echo "SENTINELA_CHAVE=$CHAVE" | sudo tee -a /opt/licita/.env > /dev/null; echo "$CHAVE"
```

O comando mostra a chave **uma vez**: copie e cole nas opções da extensão
(nunca em chat ou e-mail). Depois reinicie:

```bash
cd /opt/licita && sudo docker compose up -d --force-recreate backend worker beat
```

Sem a chave no servidor, a API da Sentinela recusa tudo. Para trocar a
chave, apague a linha `SENTINELA_CHAVE` do `.env`, rode de novo o primeiro
comando e cole a nova na extensão. Instalação da extensão:
[`sentinela/README.md`](../../sentinela/README.md).

## Backup do banco (automático)

Todo deploy faz um backup do banco **antes** de rodar as migrações
(`atualizar.sh`). Se o backup falhar, o deploy para e nada muda.

- Onde fica: `/opt/licita/backups/licita-AAAAMMDD-HHMMSS.dump`
- Quantos: os **10 mais recentes** (os mais velhos são apagados sozinhos).
- Ficam **no próprio EC2**. Se a máquina morrer, eles vão junto: de vez em
  quando, baixe o mais recente para fora.

**Fazer um backup na mão** (sem deploy):

```bash
cd /opt/licita && sudo docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' | sudo tee backups/licita-manual-$(date +%Y%m%d-%H%M%S).dump > /dev/null
```

## Voltar um deploy que deu errado

**1. Ver os backups** (o nome tem data e hora; use o feito logo antes do
deploy que deu problema):

```bash
ls -lt /opt/licita/backups/
```

**2. Parar quem usa o banco:**

```bash
cd /opt/licita && sudo docker compose stop backend worker beat
```

**3. Restaurar** (troque `ARQUIVO` pelo nome do passo 1):

```bash
cd /opt/licita && sudo docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backups/ARQUIVO.dump
```

**4. Voltar o código:** Actions → **Deploy EC2** → Run workflow, escolhendo
em *Use workflow from* a branch anterior (ex.: `backup/antes-da-torre`).
Isso gera as imagens daquela versão e reinicia tudo.

**5. Conferir:**

```bash
cd /opt/licita && sudo docker compose ps
```

Restaurar o banco **apaga** o que foi gravado depois do backup. Faça só se o
dado estiver estragado; se o problema for só tela ou código, o passo 4 basta.

## Ambiente de teste (antes de publicar)

Um segundo Licita na mesma máquina, **separado da produção**: outro banco,
outras senhas, outro endereço. Serve para testar uma branch antes do merge.

| | Produção | Teste |
|---|---|---|
| Endereço | `https://<domínio>` | `https://teste.<domínio>` |
| Roda | a `main` | a branch que você escolher |
| Banco | o real | separado (pode bagunçar) |

### Ligar (ou atualizar com a versão mais nova da branch)

Actions → **Teste: ligar** → **Run workflow** → em **Use workflow from**
escolha a **branch** → **Run workflow**. Uns 10 minutos.

### Desligar (quando terminar)

Actions → **Teste: desligar** → **Run workflow**. Marque **Apagar também
os dados do teste** só se quiser que o banco do teste volte vazio.

Ligado, o teste divide a memória com a produção: **desligue quando
terminar**.

### Login no teste (só na primeira vez)

O banco do teste é outro, então o login também. No terminal do EC2:

```bash
cd /opt/licita-teste && sudo docker compose -f docker-compose.teste.yml exec teste-backend python manage.py createsuperuser
```

### Domínio próprio para o teste

Com o endereço provisório (`sslip.io`), `teste.` já funciona sozinho. Com
`insidelicitacoes.com.br`, crie no registro.br mais uma entrada **A**:
nome `teste`, valor = o IP do EC2.

## O que roda na máquina

| Serviço | Para quê |
|---|---|
| caddy | HTTPS (certificado automático) e manda `/api` para o backend |
| frontend | as telas (Angular) |
| backend | a API (Django) — roda `migrate` antes de subir |
| worker, beat | tarefas agendadas (Celery) |
| postgres | o banco — dados no volume `licita_pgdata` |
| rabbitmq | fila das tarefas |

## Problemas comuns

- **Site sem cadeado / "não seguro":** o DNS ainda não aponta para o IP.
  Confira a Etapa 2 e espere. O Caddy tenta de novo sozinho.
- **Deploy falha em "Enviar arquivos":** confira `EC2_HOST` e
  `EC2_SSH_KEY`, e se a Etapa 3 já foi feita (ela cria `/opt/licita`).
- **Máquina lenta / travando:** troque para t3.medium (EC2 → Instance
  state → Stop → Actions → Instance settings → Change instance type).
