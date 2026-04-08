import os
import json
import requests

# ─────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────
PIPEFY_TOKEN  = os.environ.get("PIPEFY_TOKEN")
PHASE_ID      = os.environ.get("PHASE_ID", "324693543")   # fase Validação
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")
NOTIFIED_FILE = "notified_cards.json"

REQUIRED_FIELDS = [
    "Nome do titular da conta de internet",
    "CPF/CNPJ do titular da conta de internet",
    "Numero de contato do titular da conta de internet",
]

# ─────────────────────────────────────────
# CONTROLE DE DUPLICATAS
# ─────────────────────────────────────────

def load_notified() -> set:
    """Carrega os IDs já notificados como um conjunto (set) para busca O(1)."""
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    return set()


def save_notified(ids: set):
    """Salva os IDs notificados em ordem para facilitar leitura."""
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(sorted(ids), f, indent=2)


# ─────────────────────────────────────────
# PIPEFY
# ─────────────────────────────────────────

def fetch_cards() -> list:
    query = """
    query($phaseId: ID!) {
      phase(id: $phaseId) {
        cards(first: 50) {
          edges {
            node {
              id
              title
              fields {
                name
                value
              }
            }
          }
        }
      }
    }
    """
    response = requests.post(
        "https://api.pipefy.com/graphql",
        headers={
            "Authorization": f"Bearer {PIPEFY_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": {"phaseId": PHASE_ID}},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        raise Exception(f"Erro na API do Pipefy: {data['errors']}")

    return [edge["node"] for edge in data["data"]["phase"]["cards"]["edges"]]


def all_fields_filled(card) -> bool:
    field_map = {f["name"]: (f["value"] or "").strip() for f in card["fields"]}
    missing = [f for f in REQUIRED_FIELDS if not field_map.get(f)]
    if missing:
        print(f"    Campos faltando: {missing}")
    return len(missing) == 0


def get_field(card, name) -> str:
    for f in card["fields"]:
        if f["name"] == name:
            return (f["value"] or "").strip() or "—"
    return "—"


# ─────────────────────────────────────────
# SLACK
# ─────────────────────────────────────────

def send_slack(card):
    nome     = get_field(card, "Nome do titular da conta de internet")
    cpf      = get_field(card, "CPF/CNPJ do titular da conta de internet")
    telefone = get_field(card, "Numero de contato do titular da conta de internet")

    message = {
        "text": (
            f":white_check_mark: *Novo card pronto para validação*\n\n"
            f"*Card:* {card['title']}\n"
            f"*Nome do titular:* {nome}\n"
            f"*CPF/CNPJ:* {cpf}\n"
            f"*Telefone:* {telefone}\n"
            f"*Abrir no Pipefy:* https://app.pipefy.com/open-cards/{card['id']}"
        )
    }

    response = requests.post(SLACK_WEBHOOK, json=message, timeout=15)
    response.raise_for_status()
    print(f"  ✓ Slack notificado: {card['title']} (ID {card['id']})")


# ─────────────────────────────────────────
# EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────

def main():
    print(f"Buscando cards na fase Validação (ID {PHASE_ID})...")
    cards = fetch_cards()
    print(f"  {len(cards)} card(s) encontrado(s).")

    # Carrega IDs já notificados (set garante que nunca há duplicata)
    notified = load_notified()
    print(f"  {len(notified)} card(s) já notificado(s) anteriormente.")

    new_notified = set(notified)  # copia para não modificar o original durante o loop

    for card in cards:
        card_id = str(card["id"])  # garante que o ID é sempre string
        print(f"\n  Card: {card['title']} (ID {card_id})")

        if card_id in notified:
            print(f"  → Já notificado — pulando.")
            continue

        if all_fields_filled(card):
            print(f"  → Todos os campos preenchidos, enviando para o Slack...")
            send_slack(card)
            new_notified.add(card_id)  # adiciona ao set apenas após envio confirmado
        else:
            print(f"  → Campos incompletos — aguardando próxima execução.")

    # Só salva se houve mudança
    if new_notified != notified:
        save_notified(new_notified)
        print(f"\n  {len(new_notified) - len(notified)} novo(s) card(s) adicionado(s) ao controle.")
    else:
        print("\n  Nenhuma alteração no controle de notificados.")

    print("\nConcluído.")


if __name__ == "__main__":
    main()
