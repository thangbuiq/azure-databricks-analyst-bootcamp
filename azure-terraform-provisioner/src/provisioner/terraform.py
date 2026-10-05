"""Terraform automation. Students configure .env and run Python commands only."""

import hashlib
import io
import json
import os
import platform
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from provisioner.config import TERRAFORM_VERSION


def verify_archive(data: bytes, expected: str):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Terraform download checksum mismatch")


def ensure_terraform(root: Path) -> Path:
    system = {"Darwin": "darwin", "Linux": "linux", "Windows": "windows"}.get(platform.system())
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64", "AMD64": "amd64"}.get(platform.machine())
    if not system or not arch:
        raise RuntimeError("Unsupported Terraform platform; use macOS, Linux or Windows x64/ARM64")
    executable = "terraform.exe" if system == "windows" else "terraform"
    dest = root / ".runtime/tools" / TERRAFORM_VERSION / executable
    if dest.is_file():
        return dest
    base = f"https://releases.hashicorp.com/terraform/{TERRAFORM_VERSION}"
    name = f"terraform_{TERRAFORM_VERSION}_{system}_{arch}.zip"
    print(f"Downloading Terraform {TERRAFORM_VERSION} to .runtime/tools…", flush=True)
    with urllib.request.urlopen(f"{base}/terraform_{TERRAFORM_VERSION}_SHA256SUMS", timeout=60) as response:
        sums = response.read().decode()
    expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == name)
    with urllib.request.urlopen(f"{base}/{name}", timeout=120) as response:
        data = response.read()
    verify_archive(data, expected)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        content = archive.read(executable)
    temporary = dest.with_suffix(".download")
    temporary.write_bytes(content)
    temporary.chmod(0o755)
    temporary.replace(dest)
    return dest


def terraform_env(settings) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        ARM_SUBSCRIPTION_ID=settings.subscription_id,
        ARM_TENANT_ID=settings.tenant_id,
        ARM_CLIENT_ID=settings.client_id,
        ARM_CLIENT_SECRET=settings.client_secret,
        TF_IN_AUTOMATION="1",
        TF_INPUT="0",
    )
    for name in (
        "location",
        "resource_group",
        "storage_account",
        "factory_name",
        "principal_object_id",
    ):
        env[f"TF_VAR_{name}"] = getattr(settings, name)
    return env


def _run(settings, *args, capture=False):
    binary = ensure_terraform(settings.root)
    directory = settings.root / "azure-terraform-provisioner"
    return subprocess.run(
        [str(binary), f"-chdir={directory}", *args],
        env=terraform_env(settings),
        check=True,
        text=True,
        capture_output=capture,
    )


def decode_outputs(value: str) -> dict:
    return {name: item["value"] for name, item in json.loads(value).items()}


def resources(settings) -> dict:
    # Terraform state remains the source of truth, no second manual config file.
    result = decode_outputs(_run(settings, "output", "-json", capture=True).stdout)
    if not result:
        raise ValueError("No Terraform outputs found. Run: uv run solution provision")
    return result


def provision_resources(settings) -> dict:
    settings.validate_cloud()
    _run(settings, "init", "-input=false")
    _run(settings, "validate")
    _run(settings, "apply", "-auto-approve", "-input=false")
    return resources(settings)


def cleanup_resources(settings, confirmed_resource_group: str):
    if confirmed_resource_group != settings.resource_group:
        raise ValueError("Cleanup requires the exact configured resource group name")
    settings.validate_cloud()
    _run(settings, "init", "-input=false")
    recorded_group = resources(settings).get("resource_group")
    if recorded_group != confirmed_resource_group:
        raise ValueError(
            f"Terraform state belongs to {recorded_group!r}, not the confirmed group. "
            "Restore the matching .env before cleanup."
        )
    _run(settings, "destroy", "-auto-approve", "-input=false")
