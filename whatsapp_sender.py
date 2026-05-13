import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


GRAPH_URL = "https://graph.facebook.com"
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


@dataclass
class Contact:
    name: str
    phone: str
    message: str
    row_number: int
    raw: dict[str, str]


def normalize_phone(value: str) -> str:
    phone = value.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        phone = f"+{phone}"
    return phone


def read_contacts(path: str) -> list[Contact]:
    contacts: list[Contact] = []
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or "phone" not in reader.fieldnames:
            raise ValueError("O CSV precisa ter uma coluna chamada 'phone'.")

        for index, row in enumerate(reader, start=2):
            phone = normalize_phone(row.get("phone", ""))
            if not PHONE_RE.match(phone):
                raise ValueError(f"Linha {index}: telefone invalido '{row.get('phone', '')}'. Use formato internacional, ex: +5511999999999.")

            message = (row.get("message") or "").strip()
            contacts.append(
                Contact(
                    name=(row.get("name") or "").strip(),
                    phone=phone,
                    message=message,
                    row_number=index,
                    raw={key: (value or "").strip() for key, value in row.items()},
                )
            )

    return contacts


def build_text_payload(contact: Contact) -> dict[str, Any]:
    if not contact.message:
        raise ValueError(f"Linha {contact.row_number}: mensagem vazia.")

    return {
        "messaging_product": "whatsapp",
        "to": contact.phone.lstrip("+"),
        "type": "text",
        "text": {
            "preview_url": False,
            "body": contact.message,
        },
    }


def build_template_payload(contact: Contact, template_name: str, language: str, template_vars: list[str]) -> dict[str, Any]:
    template: dict[str, Any] = {
        "name": template_name,
        "language": {"code": language},
    }

    if template_vars:
        parameters = []
        for field in template_vars:
            value = contact.raw.get(field, "")
            if field == "phone":
                value = contact.phone
            if not value:
                raise ValueError(f"Linha {contact.row_number}: variavel de template '{field}' vazia.")
            parameters.append({"type": "text", "text": value})

        template["components"] = [
            {
                "type": "body",
                "parameters": parameters,
            }
        ]

    return {
        "messaging_product": "whatsapp",
        "to": contact.phone.lstrip("+"),
        "type": "template",
        "template": template,
    }


def send_payload(payload: dict[str, Any], access_token: str, phone_number_id: str, api_version: str, timeout: int) -> dict[str, Any]:
    url = f"{GRAPH_URL}/{api_version}/{phone_number_id}/messages"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {json.dumps(body, ensure_ascii=False)}")

    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Envia mensagens para contatos via WhatsApp Cloud API.")
    parser.add_argument("--contacts", required=True, help="Caminho do CSV de contatos.")
    parser.add_argument("--send", action="store_true", help="Envia de verdade. Sem isso, apenas simula.")
    parser.add_argument("--delay", type=float, default=2.0, help="Pausa em segundos entre contatos.")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP em segundos.")
    parser.add_argument("--template", help="Nome do template aprovado. Se omitido, envia texto livre da coluna message.")
    parser.add_argument("--language", default="pt_BR", help="Idioma do template, ex: pt_BR.")
    parser.add_argument("--template-vars", nargs="*", default=[], help="Colunas do CSV usadas como variaveis do corpo do template.")
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    api_version = os.getenv("WHATSAPP_API_VERSION", "v23.0").strip()

    if args.send and (not access_token or not phone_number_id):
        print("Erro: preencha WHATSAPP_ACCESS_TOKEN e WHATSAPP_PHONE_NUMBER_ID no arquivo .env.", file=sys.stderr)
        return 2

    try:
        contacts = read_contacts(args.contacts)
    except Exception as error:
        print(f"Erro ao ler contatos: {error}", file=sys.stderr)
        return 2

    print(f"Contatos carregados: {len(contacts)}")
    print("Modo: ENVIO REAL" if args.send else "Modo: SIMULACAO")

    successes = 0
    failures = 0

    for position, contact in enumerate(contacts, start=1):
        label = contact.name or contact.phone
        try:
            if args.template:
                payload = build_template_payload(contact, args.template, args.language, args.template_vars)
            else:
                payload = build_text_payload(contact)

            if not args.send:
                print(f"[{position}/{len(contacts)}] Simularia envio para {label}: {json.dumps(payload, ensure_ascii=False)}")
                successes += 1
                continue

            result = send_payload(payload, access_token, phone_number_id, api_version, args.timeout)
            message_id = result.get("messages", [{}])[0].get("id", "sem-id")
            print(f"[{position}/{len(contacts)}] Enviado para {label}: {message_id}")
            successes += 1

            if position < len(contacts):
                time.sleep(max(args.delay, 0))
        except Exception as error:
            failures += 1
            print(f"[{position}/{len(contacts)}] Falha para {label}: {error}", file=sys.stderr)

    print(f"Finalizado. Sucessos: {successes}. Falhas: {failures}.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
