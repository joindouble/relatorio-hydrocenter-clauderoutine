"""
clientes/hydrocenter.py
Script de execução do relatório semanal — HydroCenter Piscinas.

HydroCenter só tem Google Ads (sem conta Meta no momento). O motor lida com a
lista Meta vazia: a plataforma ausente simplesmente não aparece no relatório.

Como isso roda dentro da Routine:
  1. O Claude busca os dados do Google via Flyweel (query_metrics) -> salva em
     dados/hydrocenter_google_raw.json.
  2. O Claude roda: python clientes/hydrocenter.py
  3. O script gera output/relatorio_hydrocenter.html
  4. O Claude revisa o HTML e cria o rascunho no Gmail.

Para rodar manualmente/testar, use os fixtures em dados_exemplo/.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from report_engine import (
    gerar_relatorio_html,
    normalizar_campanha_meta,
    normalizar_campanha_google,
    calcular_periodo,
)

# ---------------------------------------------------------------------------
# Config do cliente
# ---------------------------------------------------------------------------
CLIENTE = {
    "nome": "HydroCenter Piscinas",
    "email_destino": "admin@hydrocenterpiscinas.com.br",
    "email_assunto": "Relatório de Desempenho Tráfego Pago HydroCenter Piscinas",
    "meta_ad_account_id": "",  # HydroCenter não tem Meta Ads no momento
    "google_ads_customer_id": "567-210-6894",
    "flyweel_account": "Customer 5672106894",  # nome da conta na Flyweel (trava Google)
    # Nome/contato/logo da agência vêm dos defaults do report_engine (AGENCIA_*).
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)

# Caminhos onde a Routine deve salvar os dados brutos antes de rodar este script
CAMINHO_DADOS_META = os.path.join(REPO_DIR, "dados", "hydrocenter_meta_raw.json")
CAMINHO_DADOS_GOOGLE = os.path.join(REPO_DIR, "dados", "hydrocenter_google_raw.json")

# Fallback pros dados de exemplo (uso apenas em teste manual/local)
CAMINHO_EXEMPLO_META = os.path.join(REPO_DIR, "dados_exemplo", "hydrocenter_meta_raw.json")
CAMINHO_EXEMPLO_GOOGLE = os.path.join(REPO_DIR, "dados_exemplo", "hydrocenter_google_raw.json")

TEMPLATE_PATH = os.path.join(REPO_DIR, "template.html")
SAIDA_PATH = os.path.join(REPO_DIR, "output", "relatorio_hydrocenter.html")


def _carregar_json(caminho_real, caminho_exemplo):
    caminho = caminho_real if os.path.exists(caminho_real) else caminho_exemplo
    with open(caminho, encoding="utf-8") as f:
        return json.load(f), caminho


def main():
    # Meta: só carrega se o cliente tiver conta Meta. HydroCenter não tem, então
    # a lista fica vazia e a plataforma Meta não aparece no relatório.
    if CLIENTE.get("meta_ad_account_id"):
        dados_meta_raw, origem_meta = _carregar_json(CAMINHO_DADOS_META, CAMINHO_EXEMPLO_META)
        print(f"[dados] Meta lido de: {origem_meta}")
        campanhas_meta = [normalizar_campanha_meta(c) for c in dados_meta_raw]
    else:
        print("[dados] Cliente sem Meta Ads — pulando a plataforma Meta.")
        campanhas_meta = []

    dados_google_raw, origem_google = _carregar_json(CAMINHO_DADOS_GOOGLE, CAMINHO_EXEMPLO_GOOGLE)
    print(f"[dados] Google lido de: {origem_google}")

    # Trava de segmentação (Google/Flyweel): só passa campanha cuja conta bate
    # com a do cliente. Evita vazar campanha de outro cliente se o filtro da
    # busca falhar.
    flyweel_account = CLIENTE.get("flyweel_account")
    campanhas_google_raw = [
        c for c in dados_google_raw["campanhas"]
        if not flyweel_account or c.get("account") in (None, flyweel_account)
    ]
    campanhas_google = [normalizar_campanha_google(c) for c in campanhas_google_raw]

    print(f"[dados] Campanhas Meta (antes do filtro de atividade): {len(campanhas_meta)}")
    print(f"[dados] Campanhas Google (conta do cliente, antes do filtro): {len(campanhas_google)}")

    # Período = semana anterior completa (seg–dom), calculado automaticamente.
    cliente_info = dict(CLIENTE)
    cliente_info["periodo_label"] = calcular_periodo()["label"]

    html_final = gerar_relatorio_html(
        template_path=TEMPLATE_PATH,
        cliente=cliente_info,
        campanhas_meta=campanhas_meta,
        campanhas_google=campanhas_google,
        insight_texto=(
            "Relatório gerado automaticamente a partir dos dados da semana. "
            "Revisar manualmente até a Routine ter regra de insight automático definida."
        ),
        dados_por_dia=dados_google_raw.get("por_dia", []),
    )

    os.makedirs(os.path.dirname(SAIDA_PATH), exist_ok=True)
    with open(SAIDA_PATH, "w", encoding="utf-8") as f:
        f.write(html_final)

    print(f"[ok] Relatório gerado em: {SAIDA_PATH}")
    return html_final


def _rel(caminho):
    """Caminho relativo à raiz do repo, com barra normal (p/ o manifest)."""
    return os.path.relpath(caminho, REPO_DIR).replace("\\", "/")


def manifest():
    """Todos os parâmetros variáveis desta execução, num único JSON — a Routine
    lê ISTO e usa os valores exatos. Nada fica hardcoded no prompt."""
    periodo = calcular_periodo()
    return {
        "cliente": CLIENTE["nome"],
        "email_destino": CLIENTE["email_destino"],
        "email_assunto": CLIENTE["email_assunto"],
        "meta_ad_account_id": CLIENTE["meta_ad_account_id"],  # vazio: cliente sem Meta
        "google_ads_customer_id": CLIENTE["google_ads_customer_id"],
        "flyweel_account": CLIENTE["flyweel_account"],
        "periodo": periodo,
        "caminho_meta_json": _rel(CAMINHO_DADOS_META),
        "caminho_google_json": _rel(CAMINHO_DADOS_GOOGLE),
        "output_html": _rel(SAIDA_PATH),
    }


if __name__ == "__main__":
    if "--info" in sys.argv:
        print(json.dumps(manifest(), ensure_ascii=False, indent=2))
    else:
        main()
