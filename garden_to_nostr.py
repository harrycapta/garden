#!/usr/bin/env python3
import json
import os
import ssl
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from nostr.key import PrivateKey
from nostr.event import Event
from nostr.relay_manager import RelayManager


# ========================
# CONFIG & IO
# ========================

def load_config():
    load_dotenv()
    repo_path = Path(os.environ.get("GARDEN_REPO_PATH", ".")).resolve()
    json_file = os.environ.get("GARDEN_JSON_FILE", "garden.json")
    json_path = repo_path / json_file

    nsec = os.environ.get("NOSTR_NSEC")
    if not nsec:
        raise RuntimeError("NOSTR_NSEC non impostato nel .env")

    relays_env = os.environ.get("NOSTR_RELAYS", "")
    relays = [r.strip() for r in relays_env.split(",") if r.strip()]
    if not relays:
        relays = ["wss://nostr-pub.wellorder.net", "wss://relay.damus.io"]

    kind_default_env = os.environ.get("NOSTR_KIND_DEFAULT", "1")
    try:
        nostr_kind_default = int(kind_default_env)
    except ValueError:
        nostr_kind_default = 1

    min_diid_env = os.environ.get("MIN_DIID", "").strip()
    min_diid = None
    if min_diid_env:
        try:
            min_diid = int(min_diid_env)
        except ValueError:
            min_diid = None

    return repo_path, json_path, nsec, relays, nostr_kind_default, min_diid


def load_garden(json_path: Path):
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_garden(json_path: Path, data: dict):
    tmp = json_path.with_suffix(".tmp.json")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(json_path)


# ========================
# HELPER
# ========================

def holocene_today() -> str:
    """Ritorna la data tipo 12025-11-18."""
    today = date.today()
    year = today.year + 10000
    return f"{year:05d}-{today.month:02d}-{today.day:02d}"


def safe_int_input(prompt: str, default: int) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Valore non valido, uso default.")
        return default


def next_diid(garden: dict) -> int:
    diids = []
    for entry in garden.values():
        if isinstance(entry, dict) and isinstance(entry.get("DIID"), int):
            diids.append(entry["DIID"])
    return (max(diids) + 1) if diids else 0


# ========================
# CONTENT FORMATTING
# ========================

def format_entry_content(title: str, entry: dict) -> str:
    """
    Costruisce il testo del post Nostr a partire dalla entry del garden.
    """
    lines = []

    # Titolo
    lines.append(f"{title}")

    # Type & date
    types = entry.get("TYPE", [])
    if isinstance(types, list):
        type_str = ", ".join(types)
    else:
        type_str = str(types) if types else ""

    date_str = entry.get("DATE")
    meta_bits = []
    if type_str:
        meta_bits.append(type_str)
    if date_str:
        meta_bits.append(date_str)
    if meta_bits:
        lines.append(" · ".join(meta_bits))

    # Tags inline
    tags = entry.get("TAGS", [])
    if tags:
        hash_tags = " ".join(f"#{t.replace(' ', '_')}" for t in tags)
        lines.append(hash_tags)

    # Quote / testo
    qote = entry.get("QOTE")
    if qote:
        if isinstance(qote, str):
            q_lines = [qote]
        else:
            q_lines = qote
        lines.append("")
        for q in q_lines:
            if isinstance(q, str) and q.strip().startswith(">"):
                lines.append(q)
            else:
                lines.append(f"> {q}")

    # Link finale
    link = entry.get("LINK")
    if link:
        lines.append("")
        lines.append(f"🔗 {link}")

    return "\n".join(lines).strip()


# ========================
# NOSTR
# ========================

def publish_to_nostr(content: str, nsec: str, relays: list[str], kind: int = 1) -> str:
    """
    Pubblica un evento Nostr con kind selezionabile.
    """
    private_key = PrivateKey.from_nsec(nsec)
    event = Event(private_key.public_key.hex(), content, kind=kind)
    private_key.sign_event(event)

    relay_manager = RelayManager()
    for r in relays:
        relay_manager.add_relay(r)

    relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE})
    time.sleep(1.25)

    relay_manager.publish_event(event)
    time.sleep(1)

    relay_manager.close_connections()
    return event.id


# ========================
# GIT
# ========================

def git_commit_and_push(repo_path: Path, message: str, json_path: Path):
    subprocess.run(
        ["git", "-C", str(repo_path), "add", str(json_path.relative_to(repo_path))],
        check=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo_path), "commit", "-m", message],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        subprocess.run(["git", "-C", str(repo_path), "push"], check=True)
    else:
        print("ℹ️ Nessun nuovo commit da pushare:", result.stderr.strip())


# ========================
# LOGICA: CREAZIONE NUOVO POST
# ========================

def create_entry_interactive(garden: dict, nostr_kind_default: int) -> tuple[str, dict]:
    print("=== Nuova nota per il digital garden + Nostr ===")

    # Titolo
    title = input("Titolo della nota: ").strip()
    if not title:
        raise RuntimeError("Titolo obbligatorio.")

    # TYPE
    type_raw = input("TYPE (lista separata da virgola, es: quote,article,video) [quote]: ").strip()
    if not type_raw:
        types = ["quote"]
    else:
        types = [t.strip() for t in type_raw.split(",") if t.strip()]

    # TAGS
    tags_raw = input("TAGS (lista separata da virgola, opzionale): ").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    # LINK
    link = input("LINK (opzionale): ").strip()
    if not link:
        link = None

    # DATA
    default_date = holocene_today()
    date_str = input(f"DATE (formato 12025-11-18) [{default_date}]: ").strip()
    if not date_str:
        date_str = default_date

    # NOSTR_KIND
    nostr_kind = safe_int_input("NOSTR_KIND (1=text note, 30023=long-form ecc.)", nostr_kind_default)

    # QOTE / testo
    print("Testo / QOTE (linee multiple, invio su riga vuota per terminare):")
    q_lines = []
    while True:
        line = input()
        if line == "":
            break
        q_lines.append(line)

    if not q_lines:
        qote = ""
    elif len(q_lines) == 1:
        qote = q_lines[0]
    else:
        qote = q_lines  # mantiene array come nel tuo schema

    diid = next_diid(garden)

    entry = {
        "TYPE": types,
        "TAGS": tags,
        "DATE": date_str,
        "DONE": True,
        "DIID": diid,
        "NOSTR_KIND": nostr_kind,
    }

    if link:
        entry["LINK"] = link
    if qote != "":
        entry["QOTE"] = qote

    return title, entry


def should_publish(entry: dict, min_diid: int | None) -> bool:
    if not entry.get("DONE"):
        return False
    if entry.get("POSTED_TO_NOSTR", False):
        return False

    diid = entry.get("DIID")
    if min_diid is not None and isinstance(diid, int) and diid < min_diid:
        return False

    return True


# ========================
# MODALITÀ MAIN
# ========================

def mode_create_and_publish(repo_path, json_path, nsec, relays, nostr_kind_default):
    garden = load_garden(json_path)

    # 1) Creazione entry
    title, entry = create_entry_interactive(garden, nostr_kind_default)

    # 2) Format contenuto per Nostr
    content = format_entry_content(title, entry)
    print("\n--- Anteprima contenuto Nostr ---")
    print(content)
    print("---------------------------------")

    confirm = input("Pubblico su Nostr? [Y/n]: ").strip().lower()
    if confirm and confirm not in ("y", "yes"):
        print("Annullato, nessuna pubblicazione.")
        return

    # 3) Pubblica
    kind = entry["NOSTR_KIND"]
    event_id = publish_to_nostr(content, nsec, relays, kind=kind)
    print(f"✓ Pubblicato su Nostr. Event ID: {event_id}")

    # 4) Aggiorna entry con info Nostr e scrivi su JSON
    entry["POSTED_TO_NOSTR"] = True
    entry["NOSTR_EVENT_ID"] = event_id

    garden[title] = entry
    save_garden(json_path, garden)

    # 5) Git commit + push
    git_commit_and_push(
        repo_path,
        message=f"Add garden note + Nostr post: {title}",
        json_path=json_path,
    )
    print("✅ Garden aggiornato e pushato su git.")


def mode_publish_pending(repo_path, json_path, nsec, relays, min_diid):
    garden = load_garden(json_path)
    published_any = False

    print(f"=== Pubblico pending (MIN_DIID={min_diid}) ===")

    for title, entry in garden.items():
        if not isinstance(entry, dict):
            continue
        if not should_publish(entry, min_diid):
            continue

        kind = entry.get("NOSTR_KIND", 1)
        print(f"▶ Pubblico: {title} (DIID={entry.get('DIID')} kind={kind})")

        content = format_entry_content(title, entry)
        event_id = publish_to_nostr(content, nsec, relays, kind=kind)
        print(f"   ✓ Event ID: {event_id}")

        entry["POSTED_TO_NOSTR"] = True
        entry["NOSTR_EVENT_ID"] = event_id
        published_any = True

    if not published_any:
        print("Niente da pubblicare: nessuna entry pending rispettando MIN_DIID.")
        return

    save_garden(json_path, garden)
    git_commit_and_push(
        repo_path,
        message="Publish pending garden notes to Nostr",
        json_path=json_path,
    )
    print("✅ Garden aggiornato e pushato su git.")


def main():
    repo_path, json_path, nsec, relays, nostr_kind_default, min_diid = load_config()

    if len(sys.argv) > 1 and sys.argv[1] == "--pending":
        mode_publish_pending(repo_path, json_path, nsec, relays, min_diid)
    else:
        mode_create_and_publish(repo_path, json_path, nsec, relays, nostr_kind_default)


if __name__ == "__main__":
    main()
