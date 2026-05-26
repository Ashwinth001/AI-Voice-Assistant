#!/usr/bin/env python3
"""
ASTRA - One-Click Oracle Cloud Deployment
Region: India South (Hyderabad) - ap-hyderabad-1

Run from project root:
    python cloud/deploy_oracle_oneclick.py

Or double-click:
    deploy_oracle.bat

SECURITY: Never put your Oracle password in this file.
          OCI CLI uses API keys (Identity → Users → API Keys).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLOUD_DIR = ROOT / "cloud"
DEPLOY_CONFIG = CLOUD_DIR / "deployment_config.json"
ENV_FILE = CLOUD_DIR / ".env.deploy"

# Oracle Cloud - Hyderabad (matches your console URL)
OCI_REGION = "ap-hyderabad-1"
OCI_REGION_NAME = "India South (Hyderabad)"
OCIR_HOST = f"{OCI_REGION}.ocir.io"

DEFAULTS = {
    "region": OCI_REGION,
    "compartment_name": "astra-compartment",
    "vcn_name": "astra-vcn",
    "subnet_name": "astra-subnet-public",
    "instance_name": "astra-server",
    "bucket_name": "astra-deploy",
    "image_repo": "astra-server",
    "app_port": 5000,
    # Always Free ARM (best for free tier). Change if unavailable in your tenancy.
    "shape": "VM.Standard.A1.Flex",
    "ocpus": 2,
    "memory_gb": 12,
    "boot_volume_gb": 50,
}


class Colors:
    OK = "\033[92m"
    WARN = "\033[93m"
    ERR = "\033[91m"
    INFO = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def log(msg: str, level: str = "info"):
    prefix = {
        "info": f"{Colors.INFO}[*]{Colors.END}",
        "ok": f"{Colors.OK}[+]{Colors.END}",
        "warn": f"{Colors.WARN}[!]{Colors.END}",
        "err": f"{Colors.ERR}[X]{Colors.END}",
    }.get(level, "[*]")
    print(f"{prefix} {msg}")


def to_file_uri(path: Path) -> str:
    p = path.resolve().as_posix()
    if len(p) > 1 and p[1] == ":":
        return f"file:///{p}"
    return f"file://{p}"


def run(cmd: str | list, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        display = cmd if len(cmd) < 200 else cmd[:200] + "..."
        shell = True
    else:
        display = " ".join(cmd)
        shell = False
    log(display, "info")
    return subprocess.run(
        cmd,
        shell=shell,
        check=check,
        capture_output=capture,
        text=True,
    )


def run_oci(args: str, check: bool = False) -> dict:
    cmd = f'oci {args} --region {OCI_REGION} --output json'
    result = run(cmd, check=False)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        if check:
            raise RuntimeError(err or "OCI command failed")
        return {"error": err}
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"raw": result.stdout}


def security_warning():
    print("\n" + "=" * 70)
    print(f"{Colors.WARN}{Colors.BOLD}  SECURITY NOTICE{Colors.END}")
    print("=" * 70)
    print(textwrap.dedent("""
    • Do NOT put your Oracle Cloud password in any script or git repo.
    • If you shared your password in chat, CHANGE IT NOW in Oracle Console.
    • OCI deployment uses API keys, not your login password.

    Create API keys (one-time):
      1. Open https://cloud.oracle.com/?region=ap-hyderabad-1
      2. Profile (top-right) → My profile → API Keys → Add API Key
      3. Download private key → run: oci setup config
    """).strip())
    print("=" * 70 + "\n")


def check_prerequisites() -> bool:
    ok = True

    if shutil.which("oci"):
        ver = run("oci --version", check=False).stdout.strip()
        log(f"OCI CLI: {ver}", "ok")
    else:
        log("OCI CLI not found", "err")
        log("Install: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm", "info")
        ok = False

    oci_config = Path.home() / ".oci" / "config"
    if oci_config.exists():
        log(f"OCI config: {oci_config}", "ok")
    else:
        log("OCI not configured. Run: oci setup config", "warn")
        ok = False

    if shutil.which("docker"):
        ver = run("docker --version", check=False).stdout.strip()
        log(f"Docker: {ver}", "ok")
    else:
        log("Docker not found — will deploy source bundle via SSH instead", "warn")

    if shutil.which("ssh"):
        log("SSH client available", "ok")
    else:
        log("OpenSSH not found — install Git for Windows or OpenSSH", "warn")

    return ok


def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.setdefault("ASTRA_SECRET_KEY", secrets.token_hex(32))
    env.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    return env


def save_env(env: dict):
    lines = [
        "# ASTRA Oracle deploy secrets — DO NOT COMMIT",
        f"ASTRA_SECRET_KEY={env.get('ASTRA_SECRET_KEY', '')}",
        f"GROQ_API_KEY={env.get('GROQ_API_KEY', '')}",
        f"OCI_REGION={OCI_REGION}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")
    log(f"Saved {ENV_FILE}", "ok")


def prompt_env_if_needed(env: dict) -> dict:
    if not env.get("GROQ_API_KEY"):
        log("Groq API key (free): https://console.groq.com — press Enter to skip", "warn")
        key = getpass.getpass("GROQ_API_KEY (hidden): ").strip()
        if key:
            env["GROQ_API_KEY"] = key
    save_env(env)
    return env


def read_oci_config() -> dict:
    cfg = {}
    path = Path.home() / ".oci" / "config"
    if not path.exists():
        return cfg
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def get_tenancy_id() -> str:
    cfg = read_oci_config()
    return cfg.get("tenancy") or cfg.get("tenancy_id", "")


def get_user_id() -> str:
    return read_oci_config().get("user", "")


def get_namespace() -> str:
    result = run_oci("os ns get")
    return result.get("data", "")


def find_or_create_compartment(tenancy_id: str) -> str:
    name = DEFAULTS["compartment_name"]
    listed = run_oci(f'iam compartment list --compartment-id {tenancy_id} --compartment-id-in-subtree true')
    for comp in listed.get("data", []):
        if comp.get("name") == name and comp.get("lifecycle-state") == "ACTIVE":
            log(f"Compartment exists: {comp['id']}", "ok")
            return comp["id"]

    log(f"Creating compartment: {name}", "info")
    created = run_oci(
        f'iam compartment create --compartment-id {tenancy_id} '
        f'--name {name} --description "ASTRA AI Assistant"'
    )
    if "data" in created:
        cid = created["data"]["id"]
        log(f"Compartment created: {cid}", "ok")
        time.sleep(8)
        return cid
    raise RuntimeError(f"Failed to create compartment: {created.get('error')}")


def ensure_network(compartment_id: str) -> dict:
    """Create VCN, IGW, route table, security list, subnet if missing."""
    vcn_name = DEFAULTS["vcn_name"]
    subnet_name = DEFAULTS["subnet_name"]

    vcns = run_oci(f'network vcn list --compartment-id {compartment_id}')
    vcn_id = None
    for v in vcns.get("data", []):
        if v.get("display-name") == vcn_name or v.get("displayName") == vcn_name:
            vcn_id = v["id"]
            break

    if not vcn_id:
        log("Creating VCN 10.0.0.0/16", "info")
        vcn = run_oci(
            f'network vcn create --compartment-id {compartment_id} '
            f'--cidr-blocks \'["10.0.0.0/16"]\' --display-name {vcn_name} '
            f'--dns-label astra'
        )
        vcn_id = vcn["data"]["id"]
        log(f"VCN: {vcn_id}", "ok")
    else:
        log(f"VCN exists: {vcn_id}", "ok")

    # Internet Gateway
    igws = run_oci(f'network internet-gateway list --compartment-id {compartment_id} --vcn-id {vcn_id}')
    igw_id = None
    for g in igws.get("data", []):
        if g.get("lifecycle-state") == "AVAILABLE":
            igw_id = g["id"]
            break
    if not igw_id:
        igw = run_oci(
            f'network internet-gateway create --compartment-id {compartment_id} '
            f'--vcn-id {vcn_id} --is-enabled true --display-name astra-igw'
        )
        igw_id = igw["data"]["id"]
        log(f"Internet Gateway: {igw_id}", "ok")

    # Default security list — open 22 and app port
    vcn_detail = run_oci(f'network vcn get --vcn-id {vcn_id}')
    sec_list_id = vcn_detail["data"]["default-security-list-id"]
    app_port = DEFAULTS["app_port"]

    ingress_rules = [
        {
            "protocol": "6",
            "source": "0.0.0.0/0",
            "tcpOptions": {"destinationPortRange": {"min": 22, "max": 22}},
            "description": "SSH",
        },
        {
            "protocol": "6",
            "source": "0.0.0.0/0",
            "tcpOptions": {"destinationPortRange": {"min": app_port, "max": app_port}},
            "description": "ASTRA API",
        },
    ]
    run_oci(
        f'network security-list update --security-list-id {sec_list_id} '
        f'--ingress-security-rules \'{json.dumps(ingress_rules)}\' --force'
    )
    log(f"Security list updated (ports 22, {app_port})", "ok")

    # Route table — default route to IGW
    rt_id = vcn_detail["data"]["default-route-table-id"]
    route_rules = [{"destination": "0.0.0.0/0", "networkEntityId": igw_id}]
    run_oci(
        f'network route-table update --rt-id {rt_id} '
        f'--route-rules \'{json.dumps(route_rules)}\' --force'
    )

    # Subnet
    subnets = run_oci(f'network subnet list --compartment-id {compartment_id} --vcn-id {vcn_id}')
    subnet_id = None
    for s in subnets.get("data", []):
        dn = s.get("display-name") or s.get("displayName", "")
        if dn == subnet_name:
            subnet_id = s["id"]
            break
    if not subnet_id:
        subnet = run_oci(
            f'network subnet create --compartment-id {compartment_id} '
            f'--vcn-id {vcn_id} --cidr-block 10.0.1.0/24 '
            f'--display-name {subnet_name} --dns-label astranet '
            f'--prohibit-public-ip-on-vnic false'
        )
        subnet_id = subnet["data"]["id"]
        log(f"Subnet: {subnet_id}", "ok")
    else:
        log(f"Subnet exists: {subnet_id}", "ok")

    return {"vcn_id": vcn_id, "subnet_id": subnet_id, "sec_list_id": sec_list_id}


def get_oracle_linux_image(compartment_id: str) -> str:
    """Pick Oracle Linux 8 image matching Always Free ARM (A1) or x86 fallback."""
    result = run_oci(
        f'compute image list --compartment-id {compartment_id} '
        f'--operating-system "Oracle Linux" --operating-system-version "8" '
        f'--sort-by TIMECREATED --sort-order DESC'
    )
    images = [i for i in result.get("data", []) if i.get("lifecycle-state") == "AVAILABLE"]
    if not images:
        raise RuntimeError("No Oracle Linux 8 image found")

    # Prefer aarch64 for Always Free A1.Flex
    for img in images:
        blob = json.dumps(img).lower()
        name = (img.get("display-name") or img.get("displayName") or "").lower()
        if "aarch64" in blob or "aarch64" in name or "arm" in name:
            DEFAULTS["shape"] = "VM.Standard.A1.Flex"
            DEFAULTS["ocpus"] = 2
            DEFAULTS["memory_gb"] = 12
            log(f"ARM image: {name or img['id'][:24]}", "ok")
            return img["id"]

    # Fallback: x86 Always Free micro
    img = images[0]
    DEFAULTS["shape"] = "VM.Standard.E2.1.Micro"
    DEFAULTS["ocpus"] = 1
    DEFAULTS["memory_gb"] = 1
    log(f"x86 fallback image: {img.get('display-name', img['id'][:24])}", "warn")
    return img["id"]


def ensure_ssh_key() -> Path:
    key_dir = CLOUD_DIR / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    private = key_dir / "astra_deploy"
    public = key_dir / "astra_deploy.pub"
    if private.exists() and public.exists():
        log(f"SSH key exists: {private}", "ok")
        return private

    if shutil.which("ssh-keygen"):
        run(
            f'ssh-keygen -t rsa -b 4096 -f "{private}" -N "" -C astra-deploy',
            check=True,
        )
        log(f"Generated SSH key: {private}", "ok")
        return private

    raise RuntimeError("ssh-keygen not found — install OpenSSH")


def read_public_key(private_key: Path) -> str:
    pub = private_key.with_suffix("")
    pub = Path(str(private_key) + ".pub")
    if not pub.exists():
        pub = private_key.parent / (private_key.name + ".pub")
    return pub.read_text(encoding="utf-8").strip()


def build_cloud_init(env: dict, deploy_mode: str, image_url: str = "") -> str:
    app_port = DEFAULTS["app_port"]
    secret = env.get("ASTRA_SECRET_KEY", secrets.token_hex(32))
    groq = env.get("GROQ_API_KEY", "")

    if deploy_mode == "docker" and image_url:
        return textwrap.dedent(f"""\
            #!/bin/bash
            set -euxo pipefail
            yum install -y docker-engine git
            systemctl enable --now docker
            usermod -aG docker opc
            mkdir -p /data/astra
            docker pull {image_url}
            docker rm -f astra 2>/dev/null || true
            docker run -d --name astra --restart unless-stopped \\
              -p {app_port}:{app_port} \\
              -v /data/astra:/data/astra \\
              -e ASTRA_SECRET_KEY={secret} \\
              -e GROQ_API_KEY={groq} \\
              -e ASTRA_DATA_DIR=/data/astra \\
              {image_url}
            echo "ASTRA docker started" > /var/log/astra-deploy.log
        """)

    return textwrap.dedent(f"""\
        #!/bin/bash
        set -euxo pipefail
        yum install -y python3 python3-pip git tar unzip
        mkdir -p /opt/astra /data/astra
        chown -R opc:opc /opt/astra /data/astra
        cat > /etc/systemd/system/astra.service << 'UNIT'
        [Unit]
        Description=ASTRA Cloud API
        After=network.target

        [Service]
        Type=simple
        User=opc
        WorkingDirectory=/opt/astra
        Environment=ASTRA_SECRET_KEY={secret}
        Environment=GROQ_API_KEY={groq}
        Environment=ASTRA_DATA_DIR=/data/astra
        Environment=PORT={app_port}
        ExecStart=/usr/bin/python3 -m gunicorn --bind 0.0.0.0:{app_port} --workers 2 --timeout 120 cloud.api_server:app
        Restart=always

        [Install]
        WantedBy=multi-user.target
        UNIT
        systemctl daemon-reload
        systemctl enable astra
        echo "Waiting for app bundle at /opt/astra/main.py" >> /var/log/astra-deploy.log
    """)


def launch_instance(
    compartment_id: str,
    subnet_id: str,
    image_id: str,
    ssh_public: str,
    user_data: str,
) -> str:
    import base64

    name = DEFAULTS["instance_name"]
    existing = run_oci(
        f'compute instance list --compartment-id {compartment_id} '
        f'--display-name {name}'
    )
    for inst in existing.get("data", []):
        if inst.get("lifecycle-state") in ("RUNNING", "PROVISIONING", "STARTING"):
            log(f"Instance already exists: {inst['id']}", "warn")
            return inst["id"]

    shape = DEFAULTS["shape"]
    launch_body = {
        "compartmentId": compartment_id,
        "availabilityDomain": get_availability_domain(compartment_id),
        "displayName": name,
        "shape": shape,
        "sourceDetails": {
            "sourceType": "image",
            "imageId": image_id,
            "bootVolumeSizeInGBs": DEFAULTS["boot_volume_gb"],
        },
        "createVnicDetails": {
            "subnetId": subnet_id,
            "assignPublicIp": True,
        },
        "metadata": {
            "ssh_authorized_keys": ssh_public,
            "user_data": base64.b64encode(user_data.encode()).decode(),
        },
    }
    if shape.endswith(".Flex"):
        launch_body["shapeConfig"] = {
            "ocpus": float(DEFAULTS["ocpus"]),
            "memoryInGBs": float(DEFAULTS["memory_gb"]),
        }

    launch_file = CLOUD_DIR / "instance_launch.json"
    launch_file.write_text(json.dumps(launch_body, indent=2), encoding="utf-8")

    launch_path = launch_file.resolve().as_posix()
    result = run_oci(f'compute instance launch --from-json {to_file_uri(launch_file)}')
    if "data" not in result:
        raise RuntimeError(f"Launch failed: {result.get('error', result)}")
    iid = result["data"]["id"]
    log(f"Instance launching: {iid}", "ok")
    return iid


def get_availability_domain(compartment_id: str) -> str:
    ads = run_oci(f'iam availability-domain list --compartment-id {compartment_id}')
    domains = ads.get("data", [])
    if not domains:
        raise RuntimeError("No availability domain found")
    return domains[0]["name"]


def wait_instance_running(compartment_id: str, instance_id: str, timeout: int = 600) -> dict:
    log("Waiting for instance to RUNNING...", "info")
    start = time.time()
    while time.time() - start < timeout:
        detail = run_oci(f'compute instance get --instance-id {instance_id}')
        state = detail.get("data", {}).get("lifecycle-state", "")
        if state == "RUNNING":
            log("Instance is RUNNING", "ok")
            return detail["data"]
        if state == "TERMINATED":
            raise RuntimeError("Instance terminated unexpectedly")
        time.sleep(15)
    raise RuntimeError("Timeout waiting for instance")


def get_public_ip(compartment_id: str, instance_id: str) -> str:
    vnics = run_oci(
        f'compute vnic-attachment list --compartment-id {compartment_id} '
        f'--instance-id {instance_id}'
    )
    for v in vnics.get("data", []):
        vnic = run_oci(f'network vnic get --vnic-id {v["vnic-id"]}')
        ip = vnic.get("data", {}).get("public-ip")
        if ip:
            return ip
    return ""


def package_source() -> Path:
    """Zip project for upload (exclude heavy/local dirs)."""
    out = CLOUD_DIR / "astra_bundle.zip"
    exclude_dirs = {
        ".git", "__pycache__", "venv", ".venv", "data", "dist", "build",
        "node_modules", ".cursor",
    }
    exclude_ext = {".pyc", ".pyo"}

    log("Packaging ASTRA source...", "info")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(ROOT)
            parts = set(rel.parts)
            if parts & exclude_dirs:
                continue
            if path.suffix in exclude_ext:
                continue
            if "keys" in rel.parts and path.suffix == ".pem":
                continue
            zf.write(path, rel.as_posix())
    log(f"Bundle: {out} ({out.stat().st_size // 1024} KB)", "ok")
    return out


def upload_and_install(ip: str, private_key: Path, bundle: Path):
    ssh_base = [
        "ssh", "-i", str(private_key),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        f"opc@{ip}",
    ]
    scp_base = [
        "scp", "-i", str(private_key),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
    ]

    log("Waiting 90s for cloud-init / SSH...", "info")
    time.sleep(90)

    for attempt in range(12):
        test = run(ssh_base + ["echo ok"], check=False)
        if test.returncode == 0:
            log("SSH connected", "ok")
            break
        log(f"SSH not ready (attempt {attempt + 1}/12)...", "warn")
        time.sleep(20)
    else:
        raise RuntimeError("SSH failed — open port 22 in Oracle VCN security list")

    run(scp_base + [str(bundle), f"opc@{ip}:/tmp/astra_bundle.zip"], check=True, capture=False)

    remote_script = textwrap.dedent("""
        set -e
        sudo rm -rf /opt/astra/*
        sudo unzip -o /tmp/astra_bundle.zip -d /opt/astra
        sudo chown -R opc:opc /opt/astra
        cd /opt/astra
        python3 -m pip install --user -r requirements.txt
        python3 -m pip install --user gunicorn flask flask-cors
        sudo systemctl restart astra || sudo systemctl start astra
        sleep 5
        curl -sf http://127.0.0.1:5000/health && echo HEALTH_OK
    """)
    proc = subprocess.run(
        ssh_base + ["bash -s"],
        input=remote_script,
        text=True,
        capture=True,
    )
    if proc.returncode != 0:
        log(proc.stdout or "", "info")
        log(proc.stderr or "", "err")
        raise RuntimeError("Remote install failed")
    if "HEALTH_OK" in (proc.stdout or ""):
        log("ASTRA API health check passed on server", "ok")
    else:
        log("Server installed — verify: curl http://<ip>:5000/health", "warn")


def docker_build_and_push(namespace: str, env: dict) -> str:
    user = get_user_id().split(".")[-1] if get_user_id() else "user"
    # OCIR username format: tenancy-namespace/oracleidentitycloudservice/username
    cfg = read_oci_config()
    tenancy = cfg.get("tenancy", "")
    ocir_user = f"{namespace}/oracleidentitycloudservice/{cfg.get('user', '').split('.')[-1]}"
    image = f"{OCIR_HOST}/{namespace}/{DEFAULTS['image_repo']}:latest"

    log("Building Docker image...", "info")
    run(f'docker build -t {DEFAULTS["image_repo"]}:latest "{ROOT}"', check=True, capture=False)
    run(f"docker tag {DEFAULTS['image_repo']}:latest {image}", check=True)

    log("Login to OCIR — use Auth Token as password (NOT Oracle account password)", "warn")
    log(f"  Username: {namespace}/oracleidentitycloudservice/<your-email-prefix>", "info")
    run(f"docker login {OCIR_HOST}", check=False, capture=False)

    run(f"docker push {image}", check=True, capture=False)
    return image


def update_local_config(api_url: str):
    """Patch config.yaml cloud section for desktop client."""
    cfg_path = ROOT / "config" / "config.yaml"
    if not cfg_path.exists():
        return
    try:
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        cfg.setdefault("cloud", {})
        cfg["cloud"]["provider"] = "oracle"
        cfg["cloud"]["sync_enabled"] = True
        cfg["cloud"]["api_endpoint"] = api_url
        cfg_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False), encoding="utf-8")
        log(f"Updated config.yaml api_endpoint → {api_url}", "ok")
    except Exception as e:
        log(f"Could not update config.yaml: {e}", "warn")


def save_deployment_state(state: dict):
    DEPLOY_CONFIG.write_text(json.dumps(state, indent=2), encoding="utf-8")
    log(f"State saved: {DEPLOY_CONFIG}", "ok")


def print_success(state: dict):
    ip = state.get("public_ip", "")
    port = DEFAULTS["app_port"]
    api = f"http://{ip}:{port}/api" if ip else "(pending)"
    health = f"http://{ip}:{port}/health" if ip else ""

    print("\n" + "=" * 70)
    print(f"{Colors.OK}{Colors.BOLD}  ASTRA DEPLOYED TO ORACLE CLOUD ({OCI_REGION_NAME}){Colors.END}")
    print("=" * 70)
    print(f"  Region:      {OCI_REGION}")
    print(f"  Instance:    {state.get('instance_id', '')}")
    print(f"  Public IP:   {ip}")
    print(f"  Health:      {health}")
    print(f"  API:         {api}")
    print(f"  SSH:         ssh -i cloud/keys/astra_deploy opc@{ip}")
    print()
    print("  Desktop config (config.yaml):")
    print(f"    cloud.api_endpoint: \"{api}\"")
    print()
    print(f"  Console: https://cloud.oracle.com/?region={OCI_REGION}")
    print("=" * 70 + "\n")


def deploy(skip_docker: bool = False, skip_upload: bool = False) -> bool:
    security_warning()

    if not check_prerequisites():
        log("Fix prerequisites above, then run again.", "err")
        return False

    env = prompt_env_if_needed(load_env())
    tenancy_id = get_tenancy_id()
    if not tenancy_id:
        log("Run: oci setup config", "err")
        return False

    log(f"Tenancy: {tenancy_id[:30]}...", "ok")
    log(f"Region:  {OCI_REGION} ({OCI_REGION_NAME})", "ok")

    namespace = get_namespace()
    log(f"Object Storage namespace: {namespace}", "ok")

    compartment_id = find_or_create_compartment(tenancy_id)
    network = ensure_network(compartment_id)
    image_id = get_oracle_linux_image(compartment_id)
    private_key = ensure_ssh_key()
    ssh_pub = read_public_key(private_key)

    deploy_mode = "source"
    image_url = ""
    if not skip_docker and shutil.which("docker"):
        try:
            image_url = docker_build_and_push(namespace, env)
            deploy_mode = "docker"
        except Exception as e:
            log(f"Docker push failed, using source upload: {e}", "warn")
            deploy_mode = "source"

    user_data = build_cloud_init(env, deploy_mode, image_url)
    instance_id = launch_instance(
        compartment_id, network["subnet_id"], image_id, ssh_pub, user_data
    )
    wait_instance_running(compartment_id, instance_id)
    public_ip = get_public_ip(compartment_id, instance_id)

    state = {
        "region": OCI_REGION,
        "tenancy_id": tenancy_id,
        "compartment_id": compartment_id,
        "instance_id": instance_id,
        "public_ip": public_ip,
        "deploy_mode": deploy_mode,
        "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_deployment_state(state)

    if deploy_mode == "source" and not skip_upload and public_ip:
        bundle = package_source()
        upload_and_install(public_ip, private_key, bundle)
        state["bundle_uploaded"] = True
        save_deployment_state(state)

    api_url = f"http://{public_ip}:{DEFAULTS['app_port']}/api"
    update_local_config(api_url)
    print_success(state)
    return True


def cmd_setup_only():
    """Only create OCI network + compartment (no VM)."""
    security_warning()
    tenancy_id = get_tenancy_id()
    if not tenancy_id:
        log("Run: oci setup config first", "err")
        return
    compartment_id = find_or_create_compartment(tenancy_id)
    ensure_network(compartment_id)
    log("Infrastructure ready. Run full deploy next.", "ok")


def cmd_status():
    if not DEPLOY_CONFIG.exists():
        log("No deployment found. Run deploy first.", "warn")
        return
    state = json.loads(DEPLOY_CONFIG.read_text(encoding="utf-8"))
    print(json.dumps(state, indent=2))
    ip = state.get("public_ip")
    if ip:
        run(f"curl -sf http://{ip}:{DEFAULTS['app_port']}/health || echo unreachable", check=False, capture=False)


def main():
    parser = argparse.ArgumentParser(description="ASTRA one-click Oracle Cloud deploy")
    parser.add_argument("--setup-only", action="store_true", help="Create VCN/subnet only")
    parser.add_argument("--status", action="store_true", help="Show deployment status")
    parser.add_argument("--skip-docker", action="store_true", help="Force source upload (no Docker)")
    parser.add_argument("--skip-upload", action="store_true", help="Create VM only, no app upload")
    args = parser.parse_args()

    if args.status:
        cmd_status()
        return
    if args.setup_only:
        cmd_setup_only()
        return

    ok = deploy(skip_docker=args.skip_docker, skip_upload=args.skip_upload)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
