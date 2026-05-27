"""
retry_cards.py
Insere no Anki os cards do último lote gerado (ultimo_lote.json).
Use quando o run.py executou mas o Anki estava fechado.
"""

from run import criar_cards, garantir_anki_aberto, ULTIMO_LOTE_PATH
import json
import os

garantir_anki_aberto()

if not os.path.exists(ULTIMO_LOTE_PATH):
    print("❌ ultimo_lote.json não encontrado. Rode run.py primeiro com o Anki aberto.")
    exit(1)

with open(ULTIMO_LOTE_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

if not isinstance(data, dict) or "estruturas" not in data:
    print("❌ ultimo_lote.json inválido. Delete o arquivo e rode run.py novamente com o Anki aberto.")
    exit(1)

print(f"🔄 Reinserindo {len(data['estruturas'])} cards no Anki...")
criar_cards(data)
