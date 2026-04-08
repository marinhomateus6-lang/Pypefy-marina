import os
import json
import requests

# ─────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────
PIPEFY_TOKEN  = os.environ.get("PIPEFY_TOKEN")   # secret do GitHub
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")  # secret do GitHub
PHASE_ID      = "324693543"                       # fase Validação
NOTIFIED_FILE = "notified_cards.json"

REQUIRED_FIELDS = [
    "Nome do titular da conta de internet",
    "CPF/CNPJ do titular da conta de internet",
    "Numero de contato do titular da conta de internet",
]

# ─────────────────────────────────────────
# FUNÇÕES
# ─────────────────────────────────────────

def load_notified():
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            return json.load(f)
    return []


def save_notified(ids):
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(ids, f, indent=2)


def fetch_cards():
    query = """
    query($phaseId: ID!) {
      phase(id: $phaseId) {
        name
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
    )
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        raise Exception(f"Erro na API do Pipefy: {data['errors']}")

    edges = data["data"]["phase"]["cards"]["edges"]
    return [edge["node"] for edge in edges]


def all_fields_filled(card):
    field_map = {f["name"]: f["value"] for f in card["fields"]}
    for field in REQUIRED_FIELDS:
        value = field_map.get(field, "")
        if not value or str(value).strip() == "":
            return False
    return True


def get_field(card, name):
    for f in card["fields"]:
        if f["name"] == name:
            return f["value"] or "—"
    return "—"


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
            f"*Link:* https://app.pipefy.com/open-cards/{card['id']}"
        )
    }

    response = requests.post(SLACK_WEBHOOK, json=message)
    response.raise_for_status()
    print(f"  Notificado: {card['title']} (ID {card['id']})")


# ─────────────────────────────────────────
# EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────

def main():
    print("Buscando cards na fase Validacao (ID 324693543)...")
    cards = fetch_cards()
    print(f"  {len(cards)} card(s) encontrado(s).")

    notified = load_notified()
    new_notified = list(notified)

    for card in cards:
        if card["id"] in notified:
            print(f"  Ja notificado: {card['title']}")
            continue

        if all_fields_filled(card):
            print(f"  Campos OK, enviando Slack: {card['title']}")
            send_slack(card)
            new_notified.append(card["id"])
        else:
            print(f"  Campos incompletos: {card['title']}")

    save_notified(new_notified)
    print("Concluido.")


if __name__ == "__main__":
    main()
