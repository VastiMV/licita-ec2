# Licita no EC2: passo a passo

O Licita inteiro numa máquina só da AWS, com HTTPS em
**insidelicitacoes.com.br**. Sem Kubernetes: `docker compose` com as mesmas
imagens que o GitHub gera.

São 4 etapas, **feitas uma vez só**. Depois disso, atualizar é um botão.

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
