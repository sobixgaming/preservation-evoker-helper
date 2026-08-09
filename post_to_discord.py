import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "sources.json"
STATE_PATH = ROOT / "data" / "discord_state.json"


def encode_multipart(payload: dict, file_path: Path):
    boundary = f"----preservationevoker{uuid.uuid4().hex}"
    crlf = "\r\n"
    parts = []

    payload_json = json.dumps(payload, ensure_ascii=False)

    parts.append(f"--{boundary}{crlf}")
    parts.append(f'Content-Disposition: form-data; name="payload_json"{crlf}')
    parts.append(f"Content-Type: application/json{crlf}{crlf}")
    parts.append(payload_json)
    parts.append(crlf)

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    header = (
        f"--{boundary}{crlf}"
        f'Content-Disposition: form-data; name="files[0]"; filename="{file_path.name}"{crlf}'
        f"Content-Type: {mime_type}{crlf}{crlf}"
    ).encode("utf-8")

    body = b"".join(
        [
            "".join(parts).encode("utf-8"),
            header,
            file_bytes,
            crlf.encode("utf-8"),
            f"--{boundary}--{crlf}".encode("utf-8"),
        ]
    )

    return body, f"multipart/form-data; boundary={boundary}"


def request_multipart(url: str, payload: dict, file_path: Path, method: str):
    body, content_type = encode_multipart(payload, file_path)

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": content_type,
            "User-Agent": "preservation-evoker-sources/3.0",
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


def build_payload(source: dict, filename: str) -> dict:
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
        "thumbnail": {"url": f"attachment://{filename}"},
    }

    return {
        "username": "Preservation Evoker Guides",
        "allowed_mentions": {"parse": []},
        "attachments": [
            {
                "id": 0,
                "filename": filename,
                "description": source["title"],
            }
        ],
        "embeds": [embed],
    }


def load_state():
    if not STATE_PATH.exists():
        return {}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_image_path(source: dict) -> Path:
    relative_path = source.get("thumbnail_path")
    if not relative_path:
        raise RuntimeError(f'No thumbnail_path configured for {source["key"]}.')

    path = ROOT / relative_path
    if not path.exists():
        raise RuntimeError(f"Thumbnail file does not exist: {path}")

    if path.stat().st_size == 0:
        raise RuntimeError(f"Thumbnail file is empty: {path}")

    return path


def create_message(webhook_url: str, source: dict, image_path: Path) -> str:
    sep = "&" if "?" in webhook_url else "?"
    url = webhook_url + sep + "wait=true"

    payload = build_payload(source, image_path.name)
    status, result = request_multipart(url, payload, image_path, "POST")

    if status not in (200, 201) or not result or "id" not in result:
        raise RuntimeError(f"Discord message creation failed (HTTP {status}).")

    return str(result["id"])


def edit_message(webhook_url: str, message_id: str, source: dict, image_path: Path):
    url = f'{webhook_url.rstrip("/")}/messages/{urllib.parse.quote(message_id)}'

    payload = build_payload(source, image_path.name)
    status, _ = request_multipart(url, payload, image_path, "PATCH")

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
        image_path = get_image_path(source)
        message_id = state.get(key)

        if message_id:
            try:
                edit_message(webhook_url, message_id, source, image_path)
                print(f"Updated with thumbnail: {key} -> {message_id}")
            except RuntimeError as exc:
                if "HTTP 404" not in str(exc):
                    raise

                message_id = create_message(webhook_url, source, image_path)
                state[key] = message_id
                state_changed = True
                print(f"Recreated with thumbnail: {key} -> {message_id}")
        else:
            message_id = create_message(webhook_url, source, image_path)
            state[key] = message_id
            state_changed = True
            print(f"Created with thumbnail: {key} -> {message_id}")

        time.sleep(0.5)

    if state_changed:
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
