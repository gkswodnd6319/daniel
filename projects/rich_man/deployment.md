# Deploying Rich Man to Oracle Cloud (Always Free)

## What You Get (Free Forever)

- ARM VM: 4 CPU, 24GB RAM (Ampere A1) — or 2x AMD VMs (1 CPU, 1GB each)
- 200GB block storage
- 10TB/month network
- No surprise bills, no credit card charges

## Step 1: Create Oracle Cloud Account

1. Go to https://cloud.oracle.com/
2. Click "Start for Free"
3. Enter email, name, credit card (verification only, never charged)
4. Select home region: **ap-chuncheon-1 (South Korea)** or **ap-seoul-1** for lowest latency
5. Wait for account activation (~5 minutes)

## Step 2: Create a VM

1. Go to Oracle Cloud Console → **Compute → Instances → Create Instance**
2. Settings:
   - **Name:** `richman`
   - **Image:** Ubuntu 22.04 (or 24.04)
   - **Shape:** Click "Change Shape" → **Ampere** → **VM.Standard.A1.Flex**
     - OCPUs: **4** (max free)
     - Memory: **24 GB** (max free)
   - **Networking:** Accept defaults (creates VCN automatically)
   - **SSH Key:** Click "Generate a key pair" → **Save Private Key** (download the .key file)
3. Click **Create**
4. Wait ~2 minutes for the instance to provision
5. Copy the **Public IP Address** from the instance details

## Step 3: Connect to Your VM

```bash
# Make the key file secure
chmod 400 ~/Downloads/ssh-key-*.key

# Connect
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<YOUR_PUBLIC_IP>
```

## Step 4: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and pip
sudo apt install -y python3 python3-pip python3-venv git

# Clone your project (or upload via scp)
git clone <your-repo-url> ~/daniel
# OR upload directly:
# scp -i ~/Downloads/ssh-key-*.key -r /Users/eader/daniel ubuntu@<IP>:~/daniel

cd ~/daniel

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 5: Open Port 8080

By default Oracle blocks all ports. Open 8080 for the web UI:

### In Oracle Console:
1. Go to **Networking → Virtual Cloud Networks** → click your VCN
2. Click **Security Lists** → **Default Security List**
3. Click **Add Ingress Rules**:
   - Source CIDR: `0.0.0.0/0`
   - Destination Port: `8080`
   - Protocol: TCP
4. Click **Add Ingress Rules**

### On the VM (firewall):
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

## Step 6: Run the App

### Quick test:
```bash
cd ~/daniel
source venv/bin/activate
python3 main.py
```
Visit `http://<YOUR_PUBLIC_IP>:8080` — you should see the dashboard.

### Run permanently (survives SSH disconnect):
```bash
# Option A: Using screen
screen -S richman
cd ~/daniel && source venv/bin/activate
python3 main.py
# Press Ctrl+A then D to detach
# Reconnect later: screen -r richman

# Option B: Using systemd (recommended)
sudo tee /etc/systemd/system/richman.service << 'EOF'
[Unit]
Description=Rich Man Trading Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/daniel
ExecStart=/home/ubuntu/daniel/venv/bin/python3 main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable richman
sudo systemctl start richman

# Check status
sudo systemctl status richman

# View logs
sudo journalctl -u richman -f
```

## Step 7: Start Paper Trading

1. Open `http://<YOUR_PUBLIC_IP>:8080` in your browser
2. Go to Projects → Rich Man → Paper Trade
3. Hit **Start**
4. Close your laptop — the VM keeps running 24/7

## Managing the App

```bash
# SSH into VM
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<YOUR_PUBLIC_IP>

# Restart app
sudo systemctl restart richman

# Stop app
sudo systemctl stop richman

# View live logs
sudo journalctl -u richman -f

# Update code
cd ~/daniel
git pull  # if using git
sudo systemctl restart richman

# Run optimizer (monthly)
cd ~/daniel
source venv/bin/activate
python3 projects/rich_man/optimizer.py
```

## Updating Parameters After Optimization

1. SSH into VM
2. Run optimizer: `python3 projects/rich_man/optimizer.py`
3. It saves `optimal_params.json` automatically
4. Restart app: `sudo systemctl restart richman`
5. New params are loaded on startup

## Security (Optional but Recommended)

### Add basic auth to the web UI:
In `main.py`, add before `ui.run()`:
```python
app.add_middleware(
    AuthenticationMiddleware,
    backend=BasicAuth(username='your_user', password='your_pass'),
)
```

### Use HTTPS (free with Let's Encrypt):
```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# Configure nginx as reverse proxy
sudo tee /etc/nginx/sites-available/richman << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/richman /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Get SSL certificate (need a domain pointed to your IP)
sudo certbot --nginx -d your-domain.com
```

## Cost Summary

| Resource | Amount | Cost |
|---|---|---|
| VM (A1.Flex, 4 CPU, 24GB) | 1 | **Free** |
| Block Storage | 200GB | **Free** |
| Network | 10TB/month | **Free** |
| **Total** | | **$0/month** |
