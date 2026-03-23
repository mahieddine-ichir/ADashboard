# ADashboard — Azure Resource Dashboard

A lightweight, single-file web dashboard for managing Azure resources directly from your browser. It runs a local Python HTTP server and delegates all Azure operations to the **Azure CLI** (`az`) in the background — no SDK, no extra dependencies beyond a working `az` login.

---

## Features

### 🗂 Container Apps
- List all Azure Container Apps across subscriptions and resource groups
- Filter by subscription, resource group, or free-text search (name, location, image)
- View app details: location, resource group, provisioning state, container image, replicas

### 🖥 Virtual Machines
- List all VMs with status badges (Running, Stopped, Deallocated, …)
- Filter by subscription, resource group, or free-text search (name, size, IP, power state)
- View VM details: size, OS, public IP, location
- **Network Security Group management**
  - Inspect NSG rules attached to the VM's NIC
  - Add inbound rules (source IP, port, protocol, priority)
  - Edit existing rules inline
  - Delete rules with inline confirmation (no browser `confirm()` dialogs)

### 🗄 Storage Accounts — Blob Explorer
- List all storage accounts across subscriptions
- Drill into a storage account → browse containers → browse blobs
- **Blob operations**
  - ⬇ Download any blob directly from the browser
  - ⬆ Upload a local file to any container
  - 🗑 Delete a blob with inline confirmation
- Breadcrumb navigation to move back through account → container → blob levels
- Search filters at every level (account name, container name, blob name)

### 🔍 Global Search Bar
- Top-right search bar filters the current view in real time
- Searches across all relevant fields per view (name, resource group, location, image, IP, etc.)
- Clears automatically when switching views or drilling into a resource

### Shared Controls
- **Subscription selector** — switch between all subscriptions accessible to your `az` account
- **Resource Group selector** — scoped to the selected subscription
- **Refresh button** — re-fetches live data from Azure
- Status bar shows filtered vs total count (e.g. `12 of 47 blob(s)`)

---

## Requirements

| Requirement | Notes |
|---|---|
| Python 3.8+ | Standard library only — no `pip install` needed |
| [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) | Must be installed and on `PATH` |
| Active Azure login | Run `az login` before starting the server |

---

## Getting Started

```bash
# 1. Log in to Azure
az login

# 2. Start the dashboard
python3 server.py

# 3. Open in your browser
open http://localhost:8765
```

The server listens on `http://localhost:8765` by default.

---

## Authentication Notes

- All Azure operations use your active `az` CLI session (service principal, managed identity, or interactive login — whatever `az account show` returns).
- **Storage blob operations** use `--auth-mode key`: the CLI fetches the storage account key via the ARM management API (requires Contributor or Owner on the storage account) and uses it for data-plane calls. This avoids the need for the *Storage Blob Data Contributor/Reader* data-plane RBAC roles.
- **NSG rule management** uses the standard ARM API and requires at least *Network Contributor* on the relevant resource group or subscription.

---

## Architecture

```
Browser  ──HTTP──▶  server.py (Python BaseHTTPServer, port 8765)
                        │
                        └──subprocess──▶  az CLI  ──▶  Azure REST APIs
```

Everything is a single file (`server.py`):
- The Python HTTP server handles routing and shells out to `az` for every data operation
- The frontend is an inline single-page app (vanilla JS, no frameworks, no build step)
- No state is persisted to disk — all data is fetched live from Azure on demand

---

## Project Structure

```
ADashboard/
└── server.py   # Server + embedded frontend (single file)
```
