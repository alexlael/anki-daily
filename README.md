# anki-daily

Geração automática diária de 10 cards de inglês americano cotidiano com foco em aquisição natural da língua.

Todo dia o script:
1. Chama a API do **Google Gemini** para gerar 10 estruturas reais do inglês americano cotidiano
2. Cria os cards no **Anki** com áudio em inglês gerado via gTTS
3. Envia um **email-newsletter** com a explicação completa de cada estrutura

O histórico de estruturas já geradas é mantido localmente para evitar repetições ao longo do tempo.

---

## Requisitos

- Python 3.10+
- **Anki** desktop aberto com o add-on [AnkiConnect](https://ankiweb.net/shared/info/2055492159) instalado (código: `2055492159`)
- Conta **Gmail** com App Password habilitada
- Chave de API do **Google AI Studio** (gratuita)

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/anki-daily.git
cd anki-daily

# 2. Crie e ative a venv
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais
```

---

## Configuração do `.env`

```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-flash-latest

EMAIL_REMETENTE=seu@gmail.com
EMAIL_DESTINATARIO=seu@gmail.com
EMAIL_SENHA=sua_app_password_aqui

ANKI_URL=http://localhost:8765
ANKI_DECK=Inglês Cotidiano
ANKI_MODEL=Basic

EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587

AUDIO_LANG=en
```

### Onde obter a chave do Gemini

1. Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Clique em **Create API key** → **Create API key in new project**
3. Copie a chave e cole no `.env`

### Onde obter o App Password do Gmail

1. Acesse [myaccount.google.com](https://myaccount.google.com) → Segurança
2. Ative a verificação em duas etapas (obrigatório)
3. Pesquise por **Senhas de app** → crie uma para "Mail"
4. Use a senha de 16 caracteres gerada no campo `EMAIL_SENHA`

---

## Uso

Com o Anki aberto e o AnkiConnect ativo:

```bash
python run.py
```

O script vai:
- Gerar 10 estruturas novas (nunca repetindo as do `historico.json`)
- Criar os cards no deck configurado com destaque visual e áudio
- Salvar as estruturas no histórico local
- Enviar o email-newsletter

---

## Automação no Windows (Task Scheduler)

1. Abra o **Agendador de Tarefas**
2. Crie uma nova tarefa básica com o nome `anki-daily`
3. Gatilho: **Diariamente** no horário desejado
4. Ação: **Iniciar um programa**
   - Programa: `C:\caminho\anki-daily\.venv\Scripts\python.exe`
   - Argumentos: `C:\caminho\anki-daily\run.py`
5. Certifique-se de que o Anki abre junto com o Windows (pasta de inicialização)

## Automação no macOS / Linux (cron)

```bash
crontab -e
```

Adicione (roda todo dia às 7h):

```
0 7 * * * /caminho/anki-daily/.venv/bin/python /caminho/anki-daily/run.py >> /caminho/anki-daily/anki-daily.log 2>&1
```

---

## Estrutura do projeto

```
anki-daily/
├── run.py            # script principal
├── requirements.txt  # dependências Python
├── .env              # credenciais (não vai pro git)
├── .env.example      # template do .env
├── historico.json    # estruturas já geradas (não vai pro git)
└── README.md
```

---

## Como funcionam os cards

Cada card gerado tem:

- **Frente:** nome da estrutura em destaque + frase de exemplo em inglês com a estrutura marcada em azul
- **Verso:** tradução com a estrutura marcada + contexto de uso
- **Áudio:** pronúncia em inglês americano gerada automaticamente

O email enviado após cada execução traz a explicação completa de cada estrutura: exemplo principal, quando usar, frases adicionais e observações.
