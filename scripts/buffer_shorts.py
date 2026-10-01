#!/usr/bin/env python3
"""Portable Buffer video CLI. GraphQL/media flow adapted from Content Publisher."""
import argparse
import contextlib
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = {"youtube", "instagram", "facebook", "tiktok", "linkedin",
             "twitter", "threads", "bluesky", "mastodon"}
API_URL = "https://api.buffer.com"
CREATE = """mutation CreateVideo($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}"""
POST = """query VideoStatus($input: PostInput!) {
  post(input: $input) { id channelId status sentAt externalLink error { message } }
}"""


class UserError(Exception):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def graphql(key, query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept": "application/json", "User-Agent": "BufferShorts/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise UserError("Buffer limitó las solicitudes. Retry-After: " +
                            str(exc.headers.get("Retry-After", "consultar Buffer")))
        raise UserError("Buffer HTTP " + str(exc.code) + ". Revisa clave, permisos y cuenta.")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UserError("No se pudo completar la conexión con Buffer: " + str(exc).replace(key, "[REDACTADO]"))
    if result.get("errors"):
        messages = "; ".join(e.get("message", "Error GraphQL") for e in result["errors"])
        raise UserError(messages.replace(key, "[REDACTADO]"))
    data = result.get("data")
    if not isinstance(data, dict):
        raise UserError("Buffer devolvió una respuesta sin datos.")
    return data


def discover(key):
    data = graphql(key, "query { account { organizations { id name } } }")
    organizations = data.get("account", {}).get("organizations", [])
    if not organizations:
        raise UserError("La key no tiene organizaciones accesibles.")
    found = []
    for organization in organizations:
        channels = graphql(key, """query Channels($input: ChannelsInput!) {
          channels(input: $input) { id name displayName service }
        }""", {"input": {"organizationId": organization["id"]}})["channels"]
        found.append({**organization, "channels": channels})
    return found


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_video(path):
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise UserError("Entrega un archivo de video .mp4 existente.")
    size = path.stat().st_size
    if size == 0 or size > 150 * 1024 * 1024:
        raise UserError("El MP4 debe tener contenido y pesar como máximo 150 MB en esta versión.")
    with path.open("rb") as source:
        header = source.read(32)
    if len(header) < 12 or header[4:8] != b"ftyp":
        raise UserError("El archivo no tiene una cabecera MP4 reconocible.")
    if not shutil.which("ffprobe"):
        return {"verified": False, "note": "Sin ffprobe: comprueba que sea vertical y dure hasta 180 s."}
    try:
        process = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=30)
        info = json.loads(process.stdout)
        stream = info["streams"][0]
        duration = float(info["format"]["duration"])
        width, height = stream["width"], stream["height"]
    except (subprocess.SubprocessError, ValueError, KeyError, IndexError) as exc:
        raise UserError("ffprobe no pudo verificar el MP4: " + str(exc))
    if width > height or duration <= 0 or duration > 180:
        raise UserError("Usa un video vertical o cuadrado de hasta 180 segundos.")
    return {"verified": True, "width": width, "height": height, "duration": duration}


def validate_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UserError("El video requiere una URL HTTPS pública y directa, sin credenciales.")
    return url


def check_media_url(url, expected_sha256=None):
    validate_url(url)
    headers = {"User-Agent": "BufferShorts/1.0"}
    if expected_sha256 is None:
        headers["Range"] = "bytes=0-31"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            validate_url(response.geturl())
            header = response.read(32)
            if expected_sha256 is not None:
                digest = hashlib.sha256(header)
                size = len(header)
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > 150 * 1024 * 1024:
                        raise UserError("El MP4 remoto supera 150 MB.")
                    digest.update(chunk)
                if digest.hexdigest() != expected_sha256:
                    raise UserError("La URL propia no corresponde al mismo MP4 del plan.")
    except (urllib.error.URLError, OSError) as exc:
        raise UserError("El puente de video no es accesible: " + str(exc))
    if len(header) < 12 or header[4:8] != b"ftyp":
        raise UserError("La URL devuelve una página o un archivo distinto del MP4.")


def upload_video(path):
    """Content Publisher's uguu -> filebin -> tmpfiles fallback, without log URLs."""
    data = path.read_bytes()
    filename = uuid.uuid4().hex + ".mp4"
    failures = []
    for host in ("uguu", "filebin", "tmpfiles"):
        try:
            if host == "filebin":
                url = "https://filebin.net/" + uuid.uuid4().hex + "/" + filename
                request = urllib.request.Request(url, data=data, method="POST",
                    headers={"Content-Type": "video/mp4", "User-Agent": "BufferShorts/1.0"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    response.read()
            else:
                boundary = "----BufferShorts" + uuid.uuid4().hex
                field = "files[]" if host == "uguu" else "file"
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                        f'filename="{filename}"\r\nContent-Type: video/mp4\r\n\r\n').encode()
                body += data + f"\r\n--{boundary}--\r\n".encode()
                endpoint = "https://uguu.se/upload.php" if host == "uguu" else "https://tmpfiles.org/api/v1/upload"
                request = urllib.request.Request(endpoint, data=body, headers={
                    "Content-Type": "multipart/form-data; boundary=" + boundary,
                    "User-Agent": "BufferShorts/1.0"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = json.load(response)
                if host == "uguu":
                    url = result["files"][0]["url"]
                else:
                    if result.get("status") != "success":
                        raise UserError("El host rechazó la subida.")
                    url = result["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)
                    if url.startswith("http://"):
                        url = "https://" + url[7:]
            check_media_url(url)
            return url
        except (OSError, ValueError, KeyError, IndexError, UserError) as exc:
            failures.append(host + ": " + type(exc).__name__)
    raise UserError("No se pudo alojar el video. " + "; ".join(failures) +
                    ". Puedes proporcionar --media-url con un MP4 HTTPS público.")


def build_input(target, copy, media_url):
    service = target["service"]
    if service not in SUPPORTED:
        raise UserError("Esta versión no tiene un adaptador de video para " + service)
    title = str(copy.get("title", "")).strip()
    description = str(copy.get("description", "")).strip()
    caption = str(copy.get("caption", description or title)).strip()
    if not title or not caption:
        raise UserError("El título y el texto de publicación no pueden estar vacíos.")
    metadata = {}
    text = caption
    if service == "youtube":
        if len(title) > 100:
            raise UserError("El título de YouTube supera 100 caracteres.")
        text = description or caption
        metadata["youtube"] = {"title": title, "categoryId": str(copy.get("category_id", "24"))}
    elif service == "instagram":
        metadata["instagram"] = {"type": "reel", "shouldShareToFeed": True}
    elif service == "facebook":
        metadata["facebook"] = {"type": "reel"}
    elif service == "linkedin":
        text = title + "\n\n" + caption if title != caption else caption
    if copy.get("ai_generated") is not None:
        if not isinstance(copy["ai_generated"], bool):
            raise UserError("ai_generated debe ser un booleano JSON: true o false.")
        if service in {"youtube", "tiktok"}:
            metadata.setdefault(service, {})["isAiGenerated"] = copy["ai_generated"]
    return {"channelId": target["channel_id"], "text": text, "mode": "shareNow",
            "schedulingType": "automatic", "needsApproval": False,
            "assets": [{"video": {"url": media_url}}], "metadata": metadata}


class Publisher:
    def __init__(self, state_dir=None):
        self.state = Path(state_dir) if state_dir else ROOT / ".local"
        self.config_path = self.state / "config.json"
        self.history_path = self.state / "history.json"

    def config(self):
        return read_json(self.config_path, {"version": 1, "accounts": [], "groups": {}})

    def channels(self):
        rows = []
        for account in self.config()["accounts"]:
            for organization in account["organizations"]:
                for channel in organization["channels"]:
                    service = channel["service"].lower()
                    rows.append({"ref": account["id"] + ":" + channel["id"],
                        "account_id": account["id"], "account_label": account["label"],
                        "organization": organization["name"], "channel_id": channel["id"],
                        "name": channel.get("displayName") or channel["name"], "service": service,
                        "supported": service in SUPPORTED})
        return rows

    def add_account(self, label, key):
        key = key.strip()
        if not key or "\n" in key or "\r" in key:
            raise UserError("La API key está vacía o contiene saltos de línea.")
        if not label.strip():
            raise UserError("Pon un nombre a la cuenta.")
        config = self.config()
        if any(account["api_key"] == key for account in config["accounts"]):
            raise UserError("Esta API key ya está configurada; usa accounts refresh.")
        organizations = discover(key)
        account_id = uuid.uuid4().hex[:8]
        config["accounts"].append({"id": account_id, "label": label.strip(),
                                  "api_key": key, "organizations": organizations})
        write_json(self.config_path, config)
        return {"account_id": account_id, "label": label.strip(),
                "channels": [row for row in self.channels() if row["account_id"] == account_id]}

    def refresh(self, account_id=None):
        config = self.config()
        matched = [a for a in config["accounts"] if account_id is None or a["id"] == account_id]
        if not matched:
            raise UserError("No se encontró esa cuenta.")
        for account in matched:
            account["organizations"] = discover(account["api_key"])
        write_json(self.config_path, config)
        return self.channels()

    def select(self, selectors):
        channels = self.channels()
        selected = []
        seen = set()
        for selector in selectors:
            matches = [c for c in channels if selector.casefold() in
                       {c["ref"].casefold(), c["channel_id"].casefold(),
                        c["name"].casefold(), c["service"].casefold()}]
            if not matches:
                raise UserError("No existe el destino: " + selector + ". Usa channels.")
            if len(matches) > 1:
                raise UserError("Destino ambiguo: " + selector + ". Elige una ref: " +
                                ", ".join(c["ref"] + " (" + c["account_label"] + "/" + c["name"] + ")" for c in matches))
            channel = matches[0]
            if not channel["supported"]:
                raise UserError("Canal detectado sin adaptador de video: " + channel["service"])
            if channel["channel_id"] in seen:
                raise UserError("El mismo canal está seleccionado más de una vez.")
            seen.add(channel["channel_id"])
            selected.append(channel)
        if not selected:
            raise UserError("Selecciona al menos un destino.")
        return selected

    def group(self, name, selectors):
        selected = self.select(selectors)
        if not name.strip():
            raise UserError("El grupo necesita un nombre.")
        config = self.config()
        config["groups"][name] = [c["ref"] for c in selected]
        write_json(self.config_path, config)
        return {"group": name, "targets": selected}

    def prepare(self, video, selectors, title, description, copies=None):
        video = Path(video).resolve()
        check = validate_video(video)
        targets = self.select(selectors)
        copies = copies or {}
        entries = []
        for target in targets:
            copy = {"title": title, "description": description}
            copy.update(copies.get(target["service"], {}))
            copy.update(copies.get(target["ref"], {}))
            build_input(target, copy, "https://example.com/preview.mp4")
            entries.append({"target": target, "copy": copy})
        plan = {"version": 1, "id": uuid.uuid4().hex, "created_at": timestamp(),
                "video": str(video), "sha256": file_hash(video),
                "video_check": check, "entries": entries}
        path = self.state / "plans" / (plan["id"] + ".json")
        write_json(path, plan)
        return {"plan": str(path.resolve()), **plan}

    def load_plan(self, path):
        plan = read_json(Path(path))
        if not plan or plan.get("version") != 1 or not plan.get("entries"):
            raise UserError("El archivo no es un plan de publicación válido.")
        return plan

    def key_for(self, target):
        for account in self.config()["accounts"]:
            if account["id"] == target["account_id"]:
                # Match the cached channel too; old/deleted destinations must not drift.
                for organization in account["organizations"]:
                    if any(c["id"] == target["channel_id"] and c["service"].lower() == target["service"]
                           for c in organization["channels"]):
                        return account["api_key"]
        raise UserError("El destino ya no está configurado. Refresca cuentas y prepara otro plan.")

    @contextlib.contextmanager
    def lock(self):
        self.state.mkdir(parents=True, exist_ok=True)
        path = self.state / "publish.lock"
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise UserError("Hay otra operación de publicación o un lock tras una interrupción. Revisa history.")
        try:
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def publish(self, path, yes=False, media_url=None, republish=False):
        if not yes:
            raise UserError("Revisa el plan y autoriza publicar. Para ejecutarlo usa --yes.")
        plan = self.load_plan(path)
        video = Path(plan["video"])
        if not video.is_file() or file_hash(video) != plan["sha256"]:
            raise UserError("El video cambió o desapareció. Prepara otro plan.")
        keys = [self.key_for(e["target"]) for e in plan["entries"]]
        with self.lock():
            history = read_json(self.history_path, [])
            results = []
            url = media_url
            if media_url is not None:
                check_media_url(media_url, plan["sha256"])
            for entry, key in zip(plan["entries"], keys):
                target = entry["target"]
                previous = [r for r in history if r["sha256"] == plan["sha256"]
                            and r["channel_id"] == target["channel_id"]]
                latest = previous[-1] if previous else None
                if latest and latest["status"] in {"unknown", "submitting"}:
                    results.append({"ref": target["ref"], "status": "blocked",
                        "error": "Envío previo incierto. Comprueba Buffer antes de reintentar."})
                    continue
                if latest and latest["status"] != "error" and not republish:
                    results.append({"ref": target["ref"], "status": "skipped",
                                    "post_id": latest.get("post_id"), "previous_plan_id": latest["plan_id"],
                                    "reason": "Ya enviado; consulta status del plan original."})
                    continue
                if url is None:
                    url = upload_video(video)
                else:
                    check_media_url(url)
                post_input = build_input(target, entry["copy"], url)
                receipt = {"id": uuid.uuid4().hex, "plan_id": plan["id"],
                    "sha256": plan["sha256"], "channel_id": target["channel_id"],
                    "account_id": target["account_id"], "ref": target["ref"],
                    "created_at": timestamp(), "status": "submitting"}
                history.append(receipt)
                write_json(self.history_path, history)
                try:
                    response = graphql(key, CREATE, {"input": post_input}).get("createPost", {})
                except Exception:
                    receipt["status"] = "unknown"
                    write_json(self.history_path, history)
                    raise
                post = response.get("post")
                if post and post.get("id"):
                    receipt.update({"post_id": post["id"], "status": post.get("status", "accepted")})
                else:
                    # Only an explicit MutationError is a known failure. A malformed
                    # response may hide a successful mutation and must block retries.
                    receipt["status"] = "error" if response.get("message") else "unknown"
                    receipt["error"] = str(response.get("message", "Respuesta inesperada; revisa Buffer.")).replace(key, "[REDACTADO]")
                write_json(self.history_path, history)
                results.append(dict(receipt))
            ok = all(r["status"] not in {"error", "unknown", "blocked"} for r in results)
            return {"success": ok, "plan_id": plan["id"], "results": results,
                    "note": "Solo status=sent confirma publicación. Consulta status para los demás."}

    def status(self, path):
        plan = self.load_plan(path)
        with self.lock():
            history = read_json(self.history_path, [])
            results = []
            for receipt in history:
                if receipt["plan_id"] != plan["id"]:
                    continue
                if receipt.get("post_id"):
                    entry = next(e for e in plan["entries"] if e["target"]["ref"] == receipt["ref"])
                    post = graphql(self.key_for(entry["target"]), POST,
                                   {"input": {"id": receipt["post_id"]}}).get("post")
                    if not post:
                        raise UserError("No se pudo leer el post " + receipt["post_id"])
                    receipt["status"] = post["status"]
                    receipt["sent_at"] = post.get("sentAt")
                    receipt["external_link"] = post.get("externalLink")
                    receipt["error"] = (post.get("error") or {}).get("message")
                    receipt["checked_at"] = timestamp()
                results.append(dict(receipt))
            write_json(self.history_path, history)
            for entry in plan["entries"]:
                if not any(r["ref"] == entry["target"]["ref"] for r in results):
                    results.append({"ref": entry["target"]["ref"], "status": "not_submitted"})
            return {"plan_id": plan["id"], "results": results}

    def recover(self, path, target_ref, yes=False, post_id=None, not_sent=False):
        if not yes:
            raise UserError("La recuperación requiere comprobar Buffer y autorizar con --yes.")
        plan = self.load_plan(path)
        target = next((e["target"] for e in plan["entries"] if e["target"]["ref"] == target_ref), None)
        if not target:
            raise UserError("El destino no pertenece a este plan.")
        with self.lock():
            history = read_json(self.history_path, [])
            receipts = [r for r in history if r["plan_id"] == plan["id"] and r["ref"] == target_ref]
            if not receipts or receipts[-1]["status"] not in {"unknown", "submitting"}:
                raise UserError("No hay un envío incierto que recuperar para ese destino.")
            receipt = receipts[-1]
            if post_id:
                post = graphql(self.key_for(target), POST, {"input": {"id": post_id}}).get("post")
                if not post or post["channelId"] != target["channel_id"]:
                    raise UserError("Ese post no existe o pertenece a otro canal.")
                receipt.update({"post_id": post["id"], "status": post["status"],
                                "external_link": post.get("externalLink"), "sent_at": post.get("sentAt")})
            elif not_sent:
                receipt.update({"status": "error", "error": "Usuario comprobó que no se creó el post."})
            else:
                raise UserError("Indica --post-id o --not-sent.")
            receipt["recovered_at"] = timestamp()
            write_json(self.history_path, history)
            return dict(receipt)


def selectors(text):
    return [value.strip() for value in text.split(",") if value.strip()]


def get_key(args):
    if args.key_env:
        return os.environ.get(args.key_env, "")
    if args.key_file:
        return Path(args.key_file).read_text(encoding="utf-8-sig").strip()
    if args.key_stdin:
        return sys.stdin.read().strip()
    return getpass.getpass("API key de Buffer (entrada oculta): ")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Publica videos cortos con Buffer desde tu agente.")
    parser.add_argument("--state-dir", help="Directorio local de configuración; por defecto .local/ del paquete.")
    sub = parser.add_subparsers(dest="command", required=True)
    accounts = sub.add_parser("accounts", help="Añadir, refrescar o listar cuentas.")
    account_sub = accounts.add_subparsers(dest="action", required=True)
    add = account_sub.add_parser("add")
    add.add_argument("--label", required=True)
    secret = add.add_mutually_exclusive_group()
    secret.add_argument("--key-file")
    secret.add_argument("--key-env")
    secret.add_argument("--key-stdin", action="store_true")
    account_sub.add_parser("list")
    refresh = account_sub.add_parser("refresh")
    refresh.add_argument("--account")
    sub.add_parser("channels", help="Destinos detectados y sus referencias.")
    group = sub.add_parser("group", help="Guardar destinos de una marca, incluso entre cuentas.")
    group.add_argument("name")
    group.add_argument("--targets", required=True)
    prepare = sub.add_parser("prepare", help="Preparar un plan local; no sube ni publica.")
    prepare.add_argument("video")
    prepare.add_argument("--title", required=True)
    prepare.add_argument("--description", required=True)
    target_args = prepare.add_mutually_exclusive_group(required=True)
    target_args.add_argument("--targets")
    target_args.add_argument("--group")
    prepare.add_argument("--copy-file", help="JSON con ajustes de texto por servicio o ref.")
    publish = sub.add_parser("publish", help="Enviar un plan aprobado a Buffer ahora.")
    publish.add_argument("plan")
    publish.add_argument("--yes", action="store_true")
    publish.add_argument("--media-url", help="MP4 público propio en vez del puente temporal.")
    publish.add_argument("--republish", action="store_true", help="Republicar expresamente un video ya enviado.")
    status = sub.add_parser("status", help="Consultar estados finales en Buffer.")
    status.add_argument("plan")
    recover = sub.add_parser("recover", help="Resolver un envío incierto después de comprobar Buffer.")
    recover.add_argument("plan")
    recover.add_argument("--target", required=True, help="Ref exacta del destino.")
    recovery = recover.add_mutually_exclusive_group(required=True)
    recovery.add_argument("--post-id", help="ID del post encontrado en Buffer.")
    recovery.add_argument("--not-sent", action="store_true", help="El usuario comprobó que no existe el envío.")
    recover.add_argument("--yes", action="store_true")
    sub.add_parser("history", help="Historial local sin credenciales.")
    args = parser.parse_args(argv)
    publisher = Publisher(args.state_dir)
    try:
        if args.command == "accounts":
            if args.action == "add":
                result = publisher.add_account(args.label, get_key(args))
            elif args.action == "refresh":
                result = publisher.refresh(args.account)
            else:
                result = [{"id": a["id"], "label": a["label"],
                           "organizations": a["organizations"]} for a in publisher.config()["accounts"]]
        elif args.command == "channels":
            result = publisher.channels()
        elif args.command == "group":
            result = publisher.group(args.name, selectors(args.targets))
        elif args.command == "prepare":
            targets = selectors(args.targets) if args.targets else publisher.config()["groups"].get(args.group)
            if not targets:
                raise UserError("No existe el grupo o está vacío.")
            copies = read_json(Path(args.copy_file)) if args.copy_file else None
            if copies is not None and not isinstance(copies, dict):
                raise UserError("--copy-file debe contener un objeto JSON.")
            result = publisher.prepare(args.video, targets, args.title, args.description, copies)
        elif args.command == "publish":
            result = publisher.publish(args.plan, args.yes, args.media_url, args.republish)
        elif args.command == "status":
            result = publisher.status(args.plan)
        elif args.command == "recover":
            result = publisher.recover(args.plan, args.target, args.yes, args.post_id, args.not_sent)
        else:
            result = read_json(publisher.history_path, [])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if isinstance(result, dict) and result.get("success") is False else 0
    except (UserError, OSError, ValueError, KeyError) as exc:
        # Avoid echoing secrets even when Buffer or a local parser includes one.
        message = str(exc)
        try:
            accounts = publisher.config()["accounts"]
        except (OSError, ValueError, KeyError):
            accounts = []
        for account in accounts:
            message = message.replace(account["api_key"], "[REDACTADO]")
        print(json.dumps({"success": False, "error": message}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
