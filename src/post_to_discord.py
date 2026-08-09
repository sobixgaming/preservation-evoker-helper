import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "sources.json"
STATE_PATH = ROOT / "data" / "discord_state.json"


def request_json(url: str, payload: dict, method: str):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "preservation-evoker-sources/2.0",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Discord connection failed: {exc.reason}") from exc


def build_thumbnail_url(source: dict) -> str | None:
    """Build a public raw GitHub URL for an image stored in this repository."""
    thumbnail_path = source.get("thumbnail_path")
    if not thumbnail_path:
        return None

    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        # Useful for local tests. In GitHub Actions this variable is set automatically.
        return None

    encoded_path = urllib.parse.quote(thumbnail_path, safe="/")
    return f"https://raw.githubusercontent.com/{repository}/main/{encoded_path}"


def build_payload(source: dict) -> dict:
    description = (
        f'**Created by:** [{source["author_text"]}]({source["author_url"]})\n\n'
        f'**Updated:** {source["updated"]}\n'
        f'{source["updated_note"]}\n\n'
        f'🔗 **[Guide öffnen]({source["guide_url"]})**'
    )

    embed = {
        "title": source["title"],
        "url": source["guide_url"],
        "description": description,
    }

    thumbnail_url = build_thumbnail_url(source)
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    return {
        "username": "Preservation Evoker Guides",
        "allowed_mentions": {"parse": []},
        "embeds": [embed],
    }


def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def create_message(webhook_url: str, source: dict) -> str:
    sep = "&" if "?" in webhook_url else "?"
    status, result = request_json(
        webhook_url + sep + "wait=true",
        build_payload(source),
        "POST",
    )
    if status not in (200, 201) or not result or "id" not in result:
        raise RuntimeError(f"Discord message creation failed (HTTP {status}).")
    return str(result["id"])


def edit_message(webhook_url: str, message_id: str, source: dict):
    url = f'{webhook_url.rstrip("/")}/messages/{urllib.parse.quote(message_id)}'
    status, _ = request_json(url, build_payload(source), "PATCH")
    if status != 200:
        raise RuntimeError(f"Discord message update failed (HTTP {status}).")


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL is missing.", file=sys.stderr)
        sys.exit(1)

    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    state = load_state()
    state_changed = False

    for source in sources:
        key = source["key"]
        message_id = state.get(key)

        if message_id:
            try:
                edit_message(webhook_url, message_id, source)
                print(f"Updated: {key} -> {message_id}")
            except RuntimeError as exc:
                if "HTTP 404" not in str(exc):
                    raise
                message_id = create_message(webhook_url, source)
                state[key] = message_id
                state_changed = True
                print(f"Recreated: {key} -> {message_id}")
        else:
            message_id = create_message(webhook_url, source)
            state[key] = message_id
            state_changed = True
            print(f"Created: {key} -> {message_id}")

        time.sleep(0.4)

    if state_changed:
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
