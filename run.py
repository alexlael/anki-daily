"""
anki-daily/run.py
Sistema de geração diária de cards de inglês.
  1. Chama a API do Google Gemini (gratuita) para gerar 10 estruturas
  2. Cria os cards no Anki via AnkiConnect (com áudio gTTS)
  3. Envia email-newsletter com a explicação completa
"""

import os
import re
import sys
import json
import time
import base64
import hashlib
import smtplib
import tempfile
import subprocess
import requests

sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from dotenv import load_dotenv
from gtts import gTTS
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

# ─────────────────────────────────────────
# CONFIGURAÇÕES — via .env
# ─────────────────────────────────────────
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
ANKI_URL          = os.getenv("ANKI_URL", "http://localhost:8765")
ANKI_DECK         = os.getenv("ANKI_DECK", "Inglês Cotidiano")
ANKI_MODEL        = os.getenv("ANKI_MODEL", "Basic")

EMAIL_REMETENTE   = os.environ["EMAIL_REMETENTE"]
EMAIL_DESTINATARIO= os.environ["EMAIL_DESTINATARIO"]
EMAIL_SENHA       = os.environ["EMAIL_SENHA"]
EMAIL_SMTP_HOST   = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT   = int(os.getenv("EMAIL_SMTP_PORT", "587"))

AUDIO_LANG        = os.getenv("AUDIO_LANG", "en")
ANKI_EXE          = os.getenv("ANKI_EXE", r"C:\Program Files\Anki\anki.exe")
HISTORICO_PATH    = os.path.join(os.path.dirname(__file__), "historico.json")
ULTIMO_LOTE_PATH  = os.path.join(os.path.dirname(__file__), "ultimo_lote.json")
# ─────────────────────────────────────────


def garantir_anki_aberto(timeout=30):
    def anki_online():
        try:
            r = requests.post(ANKI_URL, json={"action": "version", "version": 6}, timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    if anki_online():
        print("✅ Anki já está aberto.")
        return

    print("🔍 Anki não encontrado. Tentando abrir...")
    if os.path.exists(ANKI_EXE):
        subprocess.Popen([ANKI_EXE])
    else:
        print(f"⚠️  Executável não encontrado em: {ANKI_EXE}")
        print("   Ajuste ANKI_EXE no .env ou abra o Anki manualmente.")

    print(f"⏳ Aguardando AnkiConnect subir (até {timeout}s)...")
    for _ in range(timeout // 2):
        time.sleep(2)
        if anki_online():
            print("✅ Anki pronto.")
            return

    print("❌ AnkiConnect não respondeu. Verifique se o Anki está aberto e o add-on instalado.")
    sys.exit(1)


SYSTEM_PROMPT = """\
Você é meu curador pessoal de aquisição natural de inglês americano cotidiano.
Seu papel NÃO é ensinar inglês de forma escolar, gramatical ou acadêmica.
Seu papel é me ajudar a internalizar padrões reais da língua através de:

* frequência real de uso
* reconhecimento de padrões
* repetição espaçada
* input compreensível
* contraste entre estruturas parecidas
* progressão natural de complexidade

OBJETIVO PRINCIPAL: Me fazer pensar em inglês através de estruturas reais usadas diariamente por nativos.

PRIORIDADES:
Priorize: chunks, expressões cotidianas, padrões conversacionais, phrasal verbs,
conectores, estruturas altamente frequentes, linguagem informal moderna, inglês americano cotidiano.

Evite: gramática teórica, explicações acadêmicas, vocabulário raro, frases artificiais,
linguagem excessivamente formal, exemplos genéricos de livro didático.

REGRAS DE PROGRESSÃO:
1. Considere sempre as estruturas já estudadas anteriormente.
2. Evite redundância semântica.
3. Introduza novas estruturas em ordem de utilidade e frequência.
4. Priorize estruturas de sobrevivência conversacional e uso diário.
5. Se uma nova estrutura for parecida com outra já estudada, explique a diferença prática.
6. Sempre explique: o significado REAL, a intenção implícita, a sensação que transmite,
   e quando um nativo usaria isso naturalmente.

FORMATO DE SAÍDA — responda APENAS com JSON válido, sem markdown, sem texto extra:

{
  "data": "DD/MM/AAAA",
  "estruturas": [
    {
      "estrutura": "nome da estrutura",
      "frequencia": "...",
      "uso_intuitivo": "...",
      "intencao_implicita": "...",
      "sensacao": "...",
      "quando_usar": "...",
      "exemplos": ["frase 1", "frase 2", "frase 3"],
      "mini_observacao": "...",
      "card": {
        "frente": "frase exemplo em inglês",
        "verso": "tradução em português",
        "estrutura_resumida": "tradução/resumo da estrutura",
        "contexto": "quando usar em uma linha"
      }
    }
  ],
  "conteudos_recomendados": [
    {"titulo": "...", "motivo": "..."}
  ]
}
"""

# ─────────────────────────────────────────
# HISTÓRICO — evita repetição de estruturas
# ─────────────────────────────────────────

def carregar_historico():
    if not os.path.exists(HISTORICO_PATH):
        return []
    with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_historico(data):
    historico = carregar_historico()
    novas = [item["estrutura"] for item in data["estruturas"]]
    historico.extend(novas)
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)
    print(f"📚 Histórico atualizado: {len(historico)} estruturas no total.")


# ─────────────────────────────────────────
# 1. GERAR CONTEÚDO VIA GEMINI
# ─────────────────────────────────────────

def gerar_conteudo():
    historico = carregar_historico()
    hoje = date.today().strftime("%d/%m/%Y")

    if historico:
        lista = "\n".join(f"- {e}" for e in historico)
        prompt = (
            f"Gere as 10 estruturas de inglês americano cotidiano para hoje, {hoje}.\n\n"
            f"ESTRUTURAS JÁ ESTUDADAS — não repita nenhuma delas:\n{lista}\n\n"
            "Siga todas as regras do sistema e retorne apenas o JSON válido, sem markdown, sem blocos de código."
        )
    else:
        prompt = (
            f"Gere as 10 estruturas de inglês americano cotidiano para hoje, {hoje}. "
            "Siga todas as regras do sistema e retorne apenas o JSON válido, sem markdown, sem blocos de código."
        )

    client = genai.Client(api_key=GEMINI_API_KEY)
    print("⏳ Gerando estruturas com Gemini...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
        ),
    )
    raw = response.text.strip()
    # Remove blocos ```json ``` caso o modelo inclua
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    usage = response.usage_metadata
    print(f"✅ {len(data['estruturas'])} estruturas geradas.")
    print(f"🔢 Tokens — entrada: {usage.prompt_token_count} | saída: {usage.candidates_token_count} | total: {usage.total_token_count}")
    return data


# ─────────────────────────────────────────
# 2. ANKI — helpers
# ─────────────────────────────────────────

def anki_request(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    resp = requests.post(ANKI_URL, json=payload, timeout=10)
    result = resp.json()
    if result.get("error"):
        raise Exception(f"AnkiConnect: {result['error']}")
    return result["result"]


def gerar_audio_b64(texto):
    filename = f"tts_{hashlib.md5(texto.encode()).hexdigest()}.mp3"
    tts = gTTS(text=texto, lang=AUDIO_LANG)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tts.save(tmp.name)
    tmp.close()
    with open(tmp.name, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    os.unlink(tmp.name)
    return filename, b64


HIGHLIGHT_STYLE = "color:#0000ff; font-weight:bold;"

def destacar(texto, estrutura):
    """
    Envolve a ocorrência da estrutura no texto com um span azul+negrito.
    Case-insensitive. Preserva a capitalização original da frase.
    """
    pattern = re.compile(re.escape(estrutura), re.IGNORECASE)
    return pattern.sub(
        lambda m: f'<span style="{HIGHLIGHT_STYLE}">{m.group(0)}</span>',
        texto,
        count=1
    )


def criar_cards(data):
    print("🃏 Criando cards no Anki...")

    # Garante que o deck existe
    anki_request("createDeck", deck=ANKI_DECK)

    criados = 0
    for item in data["estruturas"]:
        card      = item["card"]
        estrutura = item["estrutura"]

        # Frente: nome da estrutura destacado + frase em inglês com a estrutura destacada
        frente_html = (
            f'<span style="{HIGHLIGHT_STYLE}">{estrutura}</span>'
            f"<br><br>"
            f"{destacar(card['frente'], estrutura)}"
        )

        # Verso: tradução com a estrutura_resumida destacada +
        #        linha de contexto separada por <br>
        verso_html = (
            f"{destacar(card['verso'], card['estrutura_resumida'])}"
            f"<br><br>"
            f'<span style="font-size:0.85em; color:#666;">'
            f"📌 {card['estrutura_resumida']} &nbsp;·&nbsp; {card['contexto']}"
            f"</span>"
        )

        # Áudio gerado a partir do texto puro (sem HTML)
        filename, audio_b64 = gerar_audio_b64(card["frente"])

        try:
            note_id = anki_request(
                "addNote",
                note={
                    "deckName": ANKI_DECK,
                    "modelName": ANKI_MODEL,
                    "fields": {"Front": frente_html, "Back": verso_html},
                    "tags": ["ingles-cotidiano", estrutura.replace(" ", "-")],
                    "options": {"allowDuplicate": False},
                    "audio": [{
                        "data": audio_b64,
                        "filename": filename,
                        "fields": ["Front"]
                    }]
                }
            )
            print(f"  ✅ [{estrutura}] → ID {note_id}")
            criados += 1
        except Exception as e:
            print(f"  ⚠️  [{estrutura}] ignorado: {e}")

    print(f"🃏 {criados} cards criados no Anki.")


# ─────────────────────────────────────────
# 3. EMAIL — monta HTML da newsletter
# ─────────────────────────────────────────

def montar_html(data):
    hoje = date.today().strftime("%d/%m/%Y")

    estruturas_html = ""
    for i, item in enumerate(data["estruturas"], 1):
        card      = item["card"]
        estrutura = item["estrutura"]

        exemplos_li = "".join(
            f"<li>{destacar(ex, estrutura)}</li>" for ex in item["exemplos"]
        )
        frente_email = destacar(card["frente"], estrutura)
        verso_email  = destacar(card["verso"], card["estrutura_resumida"])

        estruturas_html += f"""
        <div class="item">
          <div class="item-header">
            <span class="num">{i:02d}</span>
            <span class="estrutura">{estrutura}</span>
          </div>
          <div class="exemplo">
            <div class="frase">"{frente_email}"</div>
            <div class="trad">→ {verso_email}</div>
          </div>
          <div class="contexto">{item['quando_usar']}</div>
          <ul class="exemplos">{exemplos_li}</ul>
          <div class="nota">{item['mini_observacao']}</div>
        </div>
        """

    recomendados_html = "".join(
        f"<li><strong>{r['titulo']}</strong> — {r['motivo']}</li>"
        for r in data.get("conteudos_recomendados", [])
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #f0f0f0; color: #111; }}
  .wrap {{ max-width: 600px; margin: 24px auto; background: #fff; }}

  .header {{ padding: 32px 40px 24px; border-bottom: 2px solid #0000ff; }}
  .header-label {{ font-size: 10px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: #999; margin-bottom: 10px; }}
  .header h1 {{ font-size: 20px; font-weight: 700; color: #111; line-height: 1.2; }}
  .header-date {{ font-size: 12px; color: #aaa; margin-top: 5px; }}

  .content {{ padding: 0 40px; }}

  .item {{ padding: 28px 0; border-bottom: 1px solid #ebebeb; }}
  .item:last-child {{ border-bottom: none; }}

  .item-header {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; }}
  .num {{ font-size: 10px; font-weight: 700; color: #0000ff; letter-spacing: 1px; min-width: 18px; }}
  .estrutura {{ font-size: 17px; font-weight: 700; font-family: 'Courier New', Courier, monospace; color: #111; }}

  .exemplo {{ margin-bottom: 12px; }}
  .frase {{ font-size: 15px; color: #111; line-height: 1.5; margin-bottom: 3px; }}
  .trad {{ font-size: 13px; color: #777; }}

  .contexto {{ font-size: 13px; color: #444; line-height: 1.6; margin-bottom: 12px; }}

  .exemplos {{ list-style: none; margin-bottom: 10px; }}
  .exemplos li {{ font-size: 13px; color: #555; line-height: 1.55; padding: 2px 0 2px 14px; position: relative; }}
  .exemplos li::before {{ content: "·"; position: absolute; left: 0; color: #0000ff; font-weight: 700; }}

  .nota {{ font-size: 12px; color: #999; font-style: italic; line-height: 1.5; }}

  .rec {{ padding: 24px 40px; background: #fafafa; border-top: 1px solid #ebebeb; }}
  .rec-title {{ font-size: 10px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; color: #aaa; margin-bottom: 12px; }}
  .rec ul {{ list-style: none; }}
  .rec li {{ font-size: 13px; color: #555; padding: 4px 0; line-height: 1.5; }}
  .rec li strong {{ color: #111; }}

  .footer {{ padding: 16px 40px; font-size: 11px; color: #ccc; text-align: center; border-top: 1px solid #ebebeb; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="header-label">Daily English</div>
    <h1>10 estruturas de hoje</h1>
    <div class="header-date">{hoje} · inglês americano cotidiano</div>
  </div>
  <div class="content">
    {estruturas_html}
  </div>
  <div class="rec">
    <div class="rec-title">Para assistir / ouvir hoje</div>
    <ul>{recomendados_html}</ul>
  </div>
  <div class="footer">anki-daily · {hoje}</div>
</div>
</body>
</html>"""


def enviar_email(html):
    hoje = date.today().strftime("%d/%m/%Y")
    print("📧 Enviando email...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🇺🇸 Daily English — {hoje}"
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINATARIO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
    print("✅ Email enviado.")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  anki-daily · {date.today()}")
    print(f"{'='*50}\n")

    garantir_anki_aberto()
    data = gerar_conteudo()
    with open(ULTIMO_LOTE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    criar_cards(data)
    salvar_historico(data)
    html = montar_html(data)
    enviar_email(html)

    print("\n✅ Tudo pronto! Cards no Anki + email enviado.\n")
