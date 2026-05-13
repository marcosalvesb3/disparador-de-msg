# Enviador de WhatsApp em Python

App simples para enviar mensagens para varios contatos usando a API oficial WhatsApp Cloud API da Meta.

Use apenas com contatos que autorizaram receber suas mensagens. Para iniciar conversas fora da janela de atendimento do WhatsApp, use templates aprovados pela Meta.

## Configuracao

1. Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Copie `.env.example` para `.env` e preencha:

```powershell
Copy-Item .env.example .env
```

Campos:

- `WHATSAPP_ACCESS_TOKEN`: token da Meta.
- `WHATSAPP_PHONE_NUMBER_ID`: ID do numero de telefone no WhatsApp Business.
- `WHATSAPP_API_VERSION`: versao da Graph API, por exemplo `v23.0`.

4. Crie seu CSV de contatos baseado em `contacts.example.csv`.

## Envio de texto

Por seguranca, o app roda em modo simulacao por padrao:

```powershell
python whatsapp_sender.py --contacts contacts.example.csv
```

Para enviar de verdade, use `--send`:

```powershell
python whatsapp_sender.py --contacts contacts.csv --send
```

## Interface grafica

Para abrir a interface:

```powershell
python whatsapp_gui.py
```

Na tela, escolha o CSV, preencha as credenciais, clique em `Simular` para testar e use `Enviar` somente quando estiver tudo conferido.

## Envio com template aprovado

Use quando a conversa precisa ser iniciada pela empresa:

```powershell
python whatsapp_sender.py --contacts contacts.csv --template nome_do_template --language pt_BR --send
```

Se o template tiver variaveis, elas usam `name` e `message` do CSV, nessa ordem:

```powershell
python whatsapp_sender.py --contacts contacts.csv --template aviso_cliente --language pt_BR --template-vars name message --send
```

## CSV

Colunas obrigatorias:

- `phone`: telefone em formato internacional, exemplo `+5511999999999`.

Colunas opcionais:

- `name`: nome usado em logs e variaveis de template.
- `message`: mensagem de texto ou variavel de template.

## Observacoes importantes

- Mensagens de texto livres normalmente so podem ser enviadas dentro da janela de atendimento apos o cliente iniciar contato.
- Para comunicacoes ativas, use templates aprovados.
- Evite disparos em massa sem consentimento. Alem de ser ruim para as pessoas, pode bloquear sua conta.
