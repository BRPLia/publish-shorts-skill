#!/usr/bin/env python3
"""Export only reviewed public source files; never copy runtime state."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    ".gitignore", ".gitattributes", "SKILL.md", "README.md", "SECURITY.md",
    "scripts/buffer_shorts.py", "scripts/prepare_release.py",
    "examples/copy.json", "references/onboarding.md",
    "references/buffer-contract.md", "references/copy-refresh.md", "tests/test_buffer_shorts.py",
    "tests/test_release.py", "evals/evals.json",
)
PRIVATE_SEGMENTS = {".local", ".state", ".git", "__pycache__", "Content", "media", "videos"}
PATTERNS = {
    "absolute_personal_path": re.compile(r"(?i)(?<![a-z0-9])(?:[a-z]:[\\/]|/(?:Users|home)/)[^\s<>\"']+"),
    "literal_bearer_token": re.compile(r"(?i)Bearer\s+[a-z0-9._-]{24,}"),
    "jwt_token": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\."),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal_secret_assignment": re.compile(
        r"""(?i)["'](?:api[_-]?key|access[_-]?token|password|secret)["']\s*:\s*["']([^\s"']{20,})["']"""),
}


def collect_public(root=ROOT):
    root = Path(root).resolve()
    entries = {}
    for name in PUBLIC_FILES:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or PRIVATE_SEGMENTS.intersection(relative.parts):
            raise ValueError("Ruta no pública en la lista de exportación.")
        source = root / relative
        current = source
        while current != root:
            if current.is_symlink():
                raise ValueError("No se exportan enlaces simbólicos: " + name)
            current = current.parent
        if not source.resolve().is_relative_to(root):
            raise ValueError("El archivo sale de la carpeta del paquete: " + name)
        if not source.is_file():
            raise ValueError("Falta un archivo público requerido: " + name)
        data = source.read_bytes()
        text = data.decode("utf-8")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                # Never echo a matched secret or the affected line.
                raise ValueError("Revisión necesaria en " + name + ": " + label)
        entries[name] = data
    return entries


def export_public(output, archive, root=ROOT):
    root = Path(root).resolve()
    output, archive = Path(output).resolve(), Path(archive).resolve()
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Usa una carpeta de exportación separada del paquete fuente.")
    if archive.is_relative_to(root) or archive.is_relative_to(output):
        raise ValueError("Guarda el ZIP fuera de las carpetas fuente y pública.")
    entries = collect_public(root)
    allowed = set(entries) | {"RELEASE-MANIFEST.json"}
    if output.exists():
        existing = []
        for path in output.rglob("*"):
            if path.is_symlink() or path.name == ".git":
                raise ValueError("La carpeta de salida contiene un repositorio o enlace; usa otra carpeta.")
            if path.is_file():
                existing.append(path.relative_to(output).as_posix())
        if any(name not in allowed for name in existing):
            raise ValueError("La carpeta de salida contiene otros archivos. No se sobrescribirá.")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "files": [{"path": name, "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in entries.items()],
        "runtime_state_included": False,
        "media_included": False,
    }
    entries["RELEASE-MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    for name, data in entries.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    archive.parent.mkdir(parents=True, exist_ok=True)
    temp = archive.with_name(archive.name + ".tmp")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for name, data in entries.items():
                package.writestr("buffer-shorts-skill/" + name, data)
        with zipfile.ZipFile(temp) as package:
            if package.testzip() is not None:
                raise ValueError("Falló la verificación del ZIP.")
            for name, data in entries.items():
                if package.read("buffer-shorts-skill/" + name) != data:
                    raise ValueError("El ZIP no coincide con la carpeta pública.")
        temp.replace(archive)
    finally:
        if temp.exists():
            temp.unlink()
    return {"public_directory": str(output), "zip": str(archive),
            "public_files": len(entries), "runtime_state_included": False,
            "media_included": False}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Prepara una carpeta pública y ZIP sin estado local.")
    parser.add_argument("--output-dir", default=str(ROOT.parent / "buffer-shorts-github"))
    parser.add_argument("--zip", default=str(ROOT.parent / "buffer-shorts-skill.zip"))
    args = parser.parse_args()
    try:
        result = export_public(args.output_dir, args.zip)
    except (OSError, ValueError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
