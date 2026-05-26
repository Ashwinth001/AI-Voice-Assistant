"""
Oracle Cloud Infrastructure Setup for ASTRA
Creates all required cloud resources for deployment.
Run: python cloud/oracle_setup.py
"""
import os
import sys
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Oracle Cloud Configuration
OCI_CONFIG = {
    "region": "ap-hyderabad-1",
    "compartment_name": "astra-compartment",
    "vcn_name": "astra-vcn",
    "subnet_name": "astra-subnet",
    "compute_shape": "VM.Standard.E4.Flex",
    "compute_ocpus": 2,
    "compute_memory_gb": 16,
    "bucket_name": "astra-models",
    "registry_name": "astra-registry",
    "api_gateway_name": "astra-api",
}


def run_oci(cmd: str) -> dict:
    """Run OCI CLI command and return JSON result."""
    full_cmd = f"oci {cmd} --output json"
    print(f"[OCI] Running: {full_cmd}")
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[OCI] Error: {result.stderr}")
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}


def check_oci_cli():
    """Check if OCI CLI is installed and configured."""
    try:
        result = subprocess.run("oci --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OCI] CLI version: {result.stdout.strip()}")
            return True
    except Exception as e:
        print(f"[OCI] CLI not found: {e}")
    print("[OCI] Please install OCI CLI: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm")
    return False


def get_tenancy():
    """Get tenancy OCID from OCI config."""
    config_path = Path.home() / ".oci" / "config"
    if not config_path.exists():
        print("[OCI] Config not found. Run: oci setup config")
        return None
    
    tenancy = None
    with open(config_path) as f:
        for line in f:
            if line.strip().startswith("tenancy"):
                tenancy = line.split("=")[1].strip()
                break
    return tenancy


def create_compartment(tenancy_id: str) -> str:
    """Create compartment for ASTRA resources."""
    print("[OCI] Creating compartment...")
    result = run_oci(
        f'iam compartment create '
        f'--compartment-id {tenancy_id} '
        f'--name {OCI_CONFIG["compartment_name"]} '
        f'--description "ASTRA AI Assistant Resources"'
    )
    if "data" in result:
        compartment_id = result["data"]["id"]
        print(f"[OCI] Compartment created: {compartment_id}")
        return compartment_id
    
    # Check if already exists
    result = run_oci(f'iam compartment list --compartment-id {tenancy_id}')
    for comp in result.get("data", []):
        if comp["name"] == OCI_CONFIG["compartment_name"]:
            print(f"[OCI] Compartment exists: {comp['id']}")
            return comp["id"]
    return ""


def create_vcn(compartment_id: str) -> str:
    """Create Virtual Cloud Network."""
    print("[OCI] Creating VCN...")
    result = run_oci(
        f'network vcn create '
        f'--compartment-id {compartment_id} '
        f'--cidr-blocks \'["10.0.0.0/16"]\' '
        f'--display-name {OCI_CONFIG["vcn_name"]}'
    )
    if "data" in result:
        vcn_id = result["data"]["id"]
        print(f"[OCI] VCN created: {vcn_id}")
        return vcn_id
    return ""


def create_subnet(compartment_id: str, vcn_id: str) -> str:
    """Create subnet in VCN."""
    print("[OCI] Creating subnet...")
    result = run_oci(
        f'network subnet create '
        f'--compartment-id {compartment_id} '
        f'--vcn-id {vcn_id} '
        f'--cidr-block "10.0.1.0/24" '
        f'--display-name {OCI_CONFIG["subnet_name"]}'
    )
    if "data" in result:
        subnet_id = result["data"]["id"]
        print(f"[OCI] Subnet created: {subnet_id}")
        return subnet_id
    return ""


def create_bucket(compartment_id: str, namespace: str) -> str:
    """Create Object Storage bucket for models."""
    print("[OCI] Creating bucket...")
    result = run_oci(
        f'os bucket create '
        f'--compartment-id {compartment_id} '
        f'--namespace {namespace} '
        f'--name {OCI_CONFIG["bucket_name"]}'
    )
    if "data" in result:
        print(f"[OCI] Bucket created: {OCI_CONFIG['bucket_name']}")
        return OCI_CONFIG["bucket_name"]
    return ""


def create_compute(compartment_id: str, subnet_id: str, image_id: str) -> str:
    """Create compute instance for ASTRA server."""
    print("[OCI] Creating compute instance...")
    
    # Create instance configuration
    instance_config = {
        "compartmentId": compartment_id,
        "displayName": "astra-server",
        "shape": OCI_CONFIG["compute_shape"],
        "shapeConfig": {
            "ocpus": OCI_CONFIG["compute_ocpus"],
            "memoryInGBs": OCI_CONFIG["compute_memory_gb"]
        },
        "sourceDetails": {
            "sourceType": "image",
            "imageId": image_id
        },
        "createVnicDetails": {
            "subnetId": subnet_id
        }
    }
    
    config_file = ROOT / "cloud" / "instance_config.json"
    config_file.write_text(json.dumps(instance_config, indent=2))
    
    result = run_oci(
        f'compute instance launch '
        f'--from-json file://{config_file}'
    )
    if "data" in result:
        instance_id = result["data"]["id"]
        print(f"[OCI] Instance created: {instance_id}")
        return instance_id
    return ""


def get_namespace() -> str:
    """Get Object Storage namespace."""
    result = run_oci("os ns get")
    return result.get("data", "")


def save_config(config: dict):
    """Save deployment configuration."""
    config_file = ROOT / "cloud" / "deployment_config.json"
    config_file.write_text(json.dumps(config, indent=2))
    print(f"[OCI] Configuration saved to {config_file}")


def setup():
    """Main setup function."""
    print("=" * 60)
    print("  ASTRA - Oracle Cloud Setup")
    print("=" * 60)
    
    if not check_oci_cli():
        return False
    
    tenancy_id = get_tenancy()
    if not tenancy_id:
        return False
    print(f"[OCI] Tenancy: {tenancy_id}")
    
    namespace = get_namespace()
    print(f"[OCI] Namespace: {namespace}")
    
    # Create resources
    compartment_id = create_compartment(tenancy_id)
    if not compartment_id:
        print("[OCI] Failed to create compartment")
        return False
    
    # Wait for compartment to be active
    import time
    print("[OCI] Waiting for compartment to become active...")
    time.sleep(10)
    
    vcn_id = create_vcn(compartment_id)
    subnet_id = create_subnet(compartment_id, vcn_id) if vcn_id else ""
    bucket = create_bucket(compartment_id, namespace)
    
    # Save configuration
    config = {
        "tenancy_id": tenancy_id,
        "compartment_id": compartment_id,
        "vcn_id": vcn_id,
        "subnet_id": subnet_id,
        "bucket": bucket,
        "namespace": namespace,
        "region": OCI_CONFIG["region"],
    }
    save_config(config)
    
    print("\n" + "=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print(f"  Compartment: {compartment_id}")
    print(f"  VCN:         {vcn_id}")
    print(f"  Subnet:      {subnet_id}")
    print(f"  Bucket:      {bucket}")
    print("\n  Next steps:")
    print("  1. Build Docker image: docker build -t astra-server .")
    print("  2. Push to registry: python cloud/deploy.py --push")
    print("  3. Deploy: python cloud/deploy.py --deploy")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    setup()
