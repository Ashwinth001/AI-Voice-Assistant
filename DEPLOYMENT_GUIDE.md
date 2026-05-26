# ASTRA Deployment Guide

## Complete Step-by-Step Deployment to Oracle Cloud

This guide covers deploying ASTRA as a cloud service with:
- User registration portal
- Cloud sync across devices  
- Nightly model training on Kaggle GPU/TPU
- Low-latency responses via Groq API

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLOUD ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐         │
│   │   User PC   │────▶│ Oracle Cloud│────▶│   Kaggle    │         │
│   │  (Desktop)  │◀────│   Server    │◀────│   GPU/TPU   │         │
│   └─────────────┘     └─────────────┘     └─────────────┘         │
│         │                    │                    │                │
│   Desktop App          Web Portal          Model Training          │
│   - Wake word         - Register           - Nightly runs          │
│   - Voice control     - Login              - LoRA fine-tune        │
│   - PC actions        - Config sync        - Model updates         │
│   - Local LLM         - User data                                  │
│         │                    │                                     │
│         └────────────────────┴─────────────────────────────────────│
│                              │                                      │
│                         Groq API                                    │
│                     (Fast LLM responses)                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

1. **Oracle Cloud Account** (Free tier available)
   - https://www.oracle.com/cloud/free/

2. **OCI CLI** installed and configured
   - https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm

3. **Docker** installed locally
   - https://www.docker.com/get-started

4. **Groq API Key** (Free, 500 requests/day)
   - https://console.groq.com

5. **Kaggle Account** (Optional, for cloud training)
   - https://www.kaggle.com

---

## One-Click Deploy (Hyderabad — ap-hyderabad-1)

Fastest path from your PC to Oracle Cloud:

### Step 0: Security (required)

1. **Change your Oracle password** if you ever shared it in chat or email.
2. Create **API keys** (console password is NOT used by the deploy script):
   - Open [Oracle Cloud Hyderabad](https://cloud.oracle.com/?region=ap-hyderabad-1)
   - Profile → **My profile** → **API Keys** → **Add API Key**
   - Save the private key file
3. Run once: `oci setup config` (paste Tenancy OCID, User OCID, region `ap-hyderabad-1`)

### Step 1: One click

**Windows:** double-click `deploy_oracle.bat`

**Or terminal:**
```bash
cd ASTRA_v1
python cloud/deploy_oracle_oneclick.py
```

Optional secrets file:
```bash
copy cloud\.env.deploy.example cloud\.env.deploy
# Edit GROQ_API_KEY and ASTRA_SECRET_KEY
```

### What the script does

1. Creates compartment `astra-compartment`
2. Creates VCN, subnet, opens ports **22** and **5000**
3. Launches **Always Free** VM (`VM.Standard.A1.Flex` in Hyderabad when available)
4. Uploads ASTRA and starts `cloud/api_server.py` via systemd
5. Prints public IP + API URL
6. Updates local `config/config.yaml` → `cloud.api_endpoint`

### Commands

| Command | Purpose |
|---------|---------|
| `python cloud/deploy_oracle_oneclick.py` | Full deploy |
| `python cloud/deploy_oracle_oneclick.py --setup-only` | Network only |
| `python cloud/deploy_oracle_oneclick.py --status` | Show IP / health |
| `python cloud/deploy_oracle_oneclick.py --skip-docker` | Force ZIP upload |

### After deploy

- Health: `http://<PUBLIC_IP>:5000/health`
- API: `http://<PUBLIC_IP>:5000/api`
- SSH: `ssh -i cloud/keys/astra_deploy opc@<PUBLIC_IP>`

---

## Step 1: Set Up Oracle Cloud Infrastructure

### 1.1 Run the Setup Script

```bash
cd ASTRA
python cloud/oracle_setup.py
```

This creates:
- Compartment for ASTRA resources
- VCN (Virtual Cloud Network)
- Subnet for the server
- Object Storage bucket for models

### 1.2 Manual Setup (if script fails)

1. Log into Oracle Cloud Console
2. Create a Compartment: Identity → Compartments → Create
3. Create VCN: Networking → Virtual Cloud Networks → Create
4. Create Subnet: Inside VCN → Create Subnet (public)
5. Create Bucket: Storage → Buckets → Create

---

## Step 2: Build and Push Docker Image

### 2.1 Build the Image

```bash
cd ASTRA
docker build -t astra-server .
```

### 2.2 Tag for Oracle Registry

```bash
# Get your namespace
oci os ns get

# Tag the image
docker tag astra-server <region>.ocir.io/<namespace>/astra-server:latest

# Example:
docker tag astra-server ap-mumbai-1.ocir.io/mytenancy/astra-server:latest
```

### 2.3 Push to Oracle Container Registry

```bash
# Login to registry (use Auth Token as password)
docker login <region>.ocir.io

# Push
docker push <region>.ocir.io/<namespace>/astra-server:latest
```

---

## Step 3: Deploy to Oracle Compute

### 3.1 Create Compute Instance

1. Go to: Compute → Instances → Create Instance
2. Settings:
   - Shape: VM.Standard.E4.Flex (2 OCPU, 16GB RAM)
   - Image: Oracle Linux 8
   - Network: Your VCN/Subnet
   - Public IP: Yes

### 3.2 Install Docker on Instance

```bash
# SSH into instance
ssh opc@<public-ip>

# Install Docker
sudo yum install -y docker-engine
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker opc
```

### 3.3 Run the Container

```bash
# Login to registry
docker login <region>.ocir.io

# Pull and run
docker pull <region>.ocir.io/<namespace>/astra-server:latest

docker run -d \
  --name astra \
  -p 5000:5000 \
  -v /data/astra:/data/astra \
  -e ASTRA_SECRET_KEY=your-secret-key-here \
  -e GROQ_API_KEY=your-groq-api-key \
  --restart unless-stopped \
  <region>.ocir.io/<namespace>/astra-server:latest
```

### 3.4 Configure Firewall

```bash
# Allow port 5000
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

---

## Step 4: Set Up API Gateway (Optional but Recommended)

For HTTPS and custom domain:

1. Go to: Developer Services → API Gateway
2. Create Gateway in your VCN
3. Create Deployment:
   - Path: /astra
   - Backend: http://<instance-private-ip>:5000
4. Add Route rules for all API endpoints

---

## Step 5: Configure DNS (Optional)

1. Get your API Gateway URL or Instance Public IP
2. Add DNS record:
   - Type: A or CNAME
   - Name: astra.yourdomain.com
   - Value: <gateway-url or public-ip>

---

## Step 6: Configure Desktop Client

### 6.1 Update config.yaml

```yaml
cloud:
  provider: "oracle"
  sync_enabled: true
  api_endpoint: "https://astra.yourdomain.com/api"
  # OR: "http://<public-ip>:5000/api"
```

### 6.2 First Run Flow

1. User installs ASTRA
2. On first run, opens web browser to register
3. After registration, downloads personalized config.yaml
4. ASTRA starts with their AI name, theme, features

---

## Step 7: Set Up Kaggle Training (Optional)

For users without local GPU:

### 7.1 Configure Kaggle

```bash
# Install Kaggle CLI
pip install kaggle

# Get API token from kaggle.com/account
# Save to ~/.kaggle/kaggle.json
```

### 7.2 Upload Training Data

```bash
python training/kaggle_train.py --upload
```

### 7.3 Check Training Status

```bash
python training/kaggle_train.py --status
```

### 7.4 Download Trained Model

```bash
python training/kaggle_train.py --download
```

---

## Latency Optimization

### Why Local LLM is Slow

| Provider | Model | Response Time | Quality |
|----------|-------|---------------|---------|
| Ollama (CPU) | phi3.5 | 10-30 seconds | Medium |
| Ollama (GPU) | phi3.5 | 2-5 seconds | Medium |
| Groq Cloud | llama-3.3-70b | 200ms | Excellent |

### Recommended Setup for Fast Responses

1. **Primary**: Groq API (fast cloud)
2. **Fallback**: Ollama local (offline mode)

```yaml
# config.yaml
llm:
  provider: "groq"  # Primary - fast cloud
  model: "llama-3.3-70b-versatile"
  fallback_model: "phi3.5"  # Ollama fallback
```

### Get Groq API Key (Free)

1. Go to https://console.groq.com
2. Sign up (takes 2 minutes)
3. Create API key
4. Set environment variable:
   ```bash
   # Windows
   setx GROQ_API_KEY "your-key-here"
   
   # Linux/Mac
   export GROQ_API_KEY="your-key-here"
   ```

---

## Creating Windows Installer

### Option 1: PyInstaller (Simple EXE)

```bash
pip install pyinstaller
python setup.py  # Creates build scripts
pyinstaller astra.spec
# Output: dist/ASTRA.exe
```

### Option 2: NSIS Installer (Full Installer)

1. Install NSIS: https://nsis.sourceforge.io/
2. Run:
   ```bash
   makensis installer.nsi
   # Output: ASTRA-Setup.exe
   ```

The installer will:
- Install ASTRA to Program Files
- Create desktop shortcut
- Add to Windows startup (optional)
- Register uninstaller

---

## Monitoring and Maintenance

### Health Check

```bash
curl http://<server>:5000/health
# Returns: {"status": "healthy", "version": "2.0.0"}
```

### View Logs

```bash
docker logs -f astra
```

### Update Server

```bash
docker pull <region>.ocir.io/<namespace>/astra-server:latest
docker stop astra
docker rm astra
# Run docker run command again
```

### Backup User Data

```bash
# On server
tar -czvf astra-backup.tar.gz /data/astra

# Download
scp opc@<server>:astra-backup.tar.gz .
```

---

## Security Checklist

- [ ] Use HTTPS (API Gateway or nginx)
- [ ] Set strong ASTRA_SECRET_KEY
- [ ] Don't expose Groq API key in client
- [ ] Enable OCI firewall rules
- [ ] Regular backups of /data/astra
- [ ] Update container regularly

---

## Troubleshooting

### "Connection refused"
- Check firewall: `sudo firewall-cmd --list-all`
- Check container: `docker ps`
- Check logs: `docker logs astra`

### "Slow responses"
- Use Groq API instead of local Ollama
- Check network latency to server
- Reduce `num_predict` in config.yaml

### "Registration not working"
- Check API endpoint in browser
- Verify CORS settings
- Check server logs for errors

### "Training fails on Kaggle"
- Check Kaggle notebook logs
- Ensure dataset uploaded correctly
- Verify GPU quota available

---

## Cost Estimation (Oracle Cloud)

| Resource | Free Tier | After Free |
|----------|-----------|------------|
| Compute (E4.Flex 2 OCPU) | Always Free | ~$30/month |
| Object Storage (10GB) | Always Free | $0.0255/GB |
| Egress (10TB/month) | Free | $0.0085/GB |

**Total with Free Tier: $0/month**

---

## Support

- GitHub Issues: Report bugs and feature requests
- Documentation: This guide + README.md
- Community: Join the ASTRA Discord

---

*Last updated: 2024*
