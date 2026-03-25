#!/usr/bin/env python3
"""Azure Dashboard — zero-dependency Python server."""

import json
import mimetypes
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote

PORT = 8765


def run_az(*args):
    cmd = ["az", *args, "-o", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return json.loads(result.stdout), None
    except FileNotFoundError:
        return None, "Azure CLI (az) not found. Install it from https://aka.ms/installazurecli"
    except subprocess.TimeoutExpired:
        return None, "Command timed out after 30 seconds."
    except json.JSONDecodeError:
        return None, "Could not parse Azure CLI output."


def get_subscriptions():
    data, err = run_az("account", "list", "--all")
    return data or [], err

def get_resource_groups(subscription_id=None):
    args = ["group", "list"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err

def get_container_apps(subscription_id=None, resource_group=None):
    args = ["containerapp", "list"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    if resource_group:
        args += ["--resource-group", resource_group]
    data, err = run_az(*args)
    return data or [], err

def get_container_app_detail(name, resource_group, subscription_id=None):
    args = ["containerapp", "show", "--name", name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def get_container_app_replicas(name, resource_group, subscription_id=None):
    args = ["containerapp", "replica", "list", "--name", name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err

def create_revision(name, resource_group, image, cpu=None, memory=None,
                    min_replicas=None, max_replicas=None, revision_suffix=None,
                    env_vars=None, subscription_id=None):
    args = ["containerapp", "update", "--name", name, "--resource-group", resource_group,
            "--image", image]
    if cpu:
        args += ["--cpu", str(cpu)]
    if memory:
        args += ["--memory", str(memory)]
    if min_replicas is not None:
        args += ["--min-replicas", str(min_replicas)]
    if max_replicas is not None:
        args += ["--max-replicas", str(max_replicas)]
    if revision_suffix:
        args += ["--revision-suffix", revision_suffix]
    if env_vars:  # list of "KEY=VALUE" strings
        args += ["--set-env-vars"] + env_vars
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def get_vms(subscription_id=None, resource_group=None):
    args = ["vm", "list", "--show-details"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    if resource_group:
        args += ["--resource-group", resource_group]
    data, err = run_az(*args)
    return data or [], err

def get_vm_detail(name, resource_group, subscription_id=None):
    args = ["vm", "show", "-d", "--name", name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def start_vm(name, resource_group, subscription_id=None):
    args = ["vm", "start", "--name", name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def get_nic(nic_name, resource_group, subscription_id=None):
    args = ["network", "nic", "show", "--name", nic_name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def get_nsg_rules(nsg_name, resource_group, subscription_id=None):
    args = ["network", "nsg", "rule", "list", "--nsg-name", nsg_name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err

def add_nsg_rule(nsg_name, resource_group, rule_name, priority, source_ip,
                 dest_port, protocol, subscription_id=None):
    args = [
        "network", "nsg", "rule", "create",
        "--nsg-name", nsg_name,
        "--resource-group", resource_group,
        "--name", rule_name,
        "--priority", str(priority),
        "--source-address-prefixes", source_ip,
        "--destination-port-ranges", str(dest_port),
        "--protocol", protocol,
        "--access", "Allow",
        "--direction", "Inbound",
    ]
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def update_nsg_rule(nsg_name, resource_group, rule_name, priority, source_ip,
                    dest_port, protocol, subscription_id=None):
    args = [
        "network", "nsg", "rule", "update",
        "--nsg-name", nsg_name,
        "--resource-group", resource_group,
        "--name", rule_name,
        "--priority", str(priority),
        "--source-address-prefixes", source_ip,
        "--destination-port-ranges", str(dest_port),
        "--protocol", protocol,
    ]
    if subscription_id:
        args += ["--subscription", subscription_id]
    return run_az(*args)

def delete_nsg_rule(nsg_name, resource_group, rule_name, subscription_id=None):
    args = [
        "az", "network", "nsg", "rule", "delete",
        "--nsg-name", nsg_name,
        "--resource-group", resource_group,
        "--name", rule_name,
    ]
    if subscription_id:
        args += ["--subscription", subscription_id]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return {}, None
    except FileNotFoundError:
        return None, "Azure CLI (az) not found."
    except subprocess.TimeoutExpired:
        return None, "Command timed out after 30 seconds."


# ── Storage Account helpers ──

def get_storage_accounts(subscription_id=None, resource_group=None):
    args = ["storage", "account", "list"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    if resource_group:
        args += ["--resource-group", resource_group]
    data, err = run_az(*args)
    return data or [], err

def get_storage_containers(account_name, subscription_id=None):
    args = ["storage", "container", "list", "--account-name", account_name, "--auth-mode", "key"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err

def list_blobs(account_name, container_name, subscription_id=None):
    args = ["storage", "blob", "list", "--account-name", account_name,
            "--container-name", container_name, "--auth-mode", "key"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err

def delete_blob(account_name, container_name, blob_name, subscription_id=None):
    args = ["az", "storage", "blob", "delete",
            "--account-name", account_name,
            "--container-name", container_name,
            "--name", blob_name,
            "--auth-mode", "key"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return {}, None
    except FileNotFoundError:
        return None, "Azure CLI (az) not found."
    except subprocess.TimeoutExpired:
        return None, "Command timed out after 60 seconds."

def download_blob(account_name, container_name, blob_name, subscription_id=None):
    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)
    args = ["az", "storage", "blob", "download",
            "--account-name", account_name,
            "--container-name", container_name,
            "--name", blob_name,
            "--file", tmp_path,
            "--auth-mode", "key",
            "--overwrite"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            try: os.unlink(tmp_path)
            except OSError: pass
            return None, result.stderr.strip()
        with open(tmp_path, "rb") as f:
            data = f.read()
        try: os.unlink(tmp_path)
        except OSError: pass
        return data, None
    except FileNotFoundError:
        try: os.unlink(tmp_path)
        except OSError: pass
        return None, "Azure CLI (az) not found."
    except subprocess.TimeoutExpired:
        try: os.unlink(tmp_path)
        except OSError: pass
        return None, "Download timed out after 5 minutes."

def upload_blob(account_name, container_name, blob_name, file_data, subscription_id=None):
    fd, tmp_path = tempfile.mkstemp()
    try:
        os.write(fd, file_data)
        os.close(fd)
    except Exception as e:
        try: os.close(fd)
        except OSError: pass
        try: os.unlink(tmp_path)
        except OSError: pass
        return None, f"Failed to write temp file: {e}"
    args = ["az", "storage", "blob", "upload",
            "--account-name", account_name,
            "--container-name", container_name,
            "--name", blob_name,
            "--file", tmp_path,
            "--auth-mode", "key",
            "--overwrite"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        try: os.unlink(tmp_path)
        except OSError: pass
        if result.returncode != 0:
            return None, result.stderr.strip()
        return {}, None
    except FileNotFoundError:
        try: os.unlink(tmp_path)
        except OSError: pass
        return None, "Azure CLI (az) not found."
    except subprocess.TimeoutExpired:
        try: os.unlink(tmp_path)
        except OSError: pass
        return None, "Upload timed out after 5 minutes."


def get_apim_services(subscription_id=None, resource_group=None):
    args = ["apim", "list"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    if resource_group:
        args += ["--resource-group", resource_group]
    data, err = run_az(*args)
    return data or [], err

def get_apim_apis(service_name, resource_group, subscription_id=None):
    args = ["apim", "api", "list", "--service-name", service_name, "--resource-group", resource_group]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err

def get_apim_api_policy(service_name, resource_group, api_id, subscription_id=None):
    args = ["apim", "api", "policy", "show",
            "--service-name", service_name,
            "--resource-group", resource_group,
            "--api-id", api_id]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data, err

def get_apim_api_operations(service_name, resource_group, api_id, subscription_id=None):
    args = ["apim", "api", "operation", "list",
            "--service-name", service_name,
            "--resource-group", resource_group,
            "--api-id", api_id]
    if subscription_id:
        args += ["--subscription", subscription_id]
    data, err = run_az(*args)
    return data or [], err


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Azure Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242736;
    --border: #2d3148;
    --blue: #0078d4;
    --blue-light: #2ea8ff;
    --green: #50e6a0;
    --yellow: #ffd76e;
    --red: #f87171;
    --text: #e2e8f0;
    --muted: #8892a4;
    --radius: 8px;
    --sidebar-w: 210px;
  }

  body {
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 14px; min-height: 100vh;
    display: flex; flex-direction: column;
  }

  /* ── Header ── */
  header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 0 20px; height: 52px;
    display: flex; align-items: center; gap: 10px;
    flex-shrink: 0; z-index: 10;
  }
  header h1 { font-size: 16px; font-weight: 600; letter-spacing: -0.3px; }
  header .last-refresh { font-size: 11px; color: var(--muted); margin-left: auto; }

  /* ── Layout ── */
  .layout { display: flex; flex: 1; overflow: hidden; }

  /* ── Sidebar ── */
  nav {
    width: var(--sidebar-w); background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    flex-shrink: 0; overflow-y: auto;
  }
  .nav-section-label {
    font-size: 10px; text-transform: uppercase; letter-spacing: .7px;
    color: var(--muted); padding: 18px 16px 6px;
  }
  .nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 16px; cursor: pointer; border-radius: 0;
    color: var(--muted); font-size: 13px; font-weight: 500;
    transition: background .12s, color .12s;
    border-left: 3px solid transparent;
    user-select: none;
  }
  .nav-item:hover { background: var(--surface2); color: var(--text); }
  .nav-item.active { color: var(--blue-light); border-left-color: var(--blue-light); background: rgba(46,168,255,.07); }
  .nav-item svg { flex-shrink: 0; opacity: .7; }
  .nav-item.active svg { opacity: 1; }
  .nav-powered {
    margin-top: auto; padding: 14px 16px 18px;
    border-top: 1px solid var(--border);
    display: flex; flex-direction: column; align-items: flex-start; gap: 6px;
  }
  .nav-powered-label {
    font-size: 9px; text-transform: uppercase; letter-spacing: .7px; color: var(--muted);
  }
  .nav-powered-badge {
    display: flex; align-items: center; gap: 7px;
    text-decoration: none; color: var(--text); opacity: .75;
    transition: opacity .15s;
  }
  .nav-powered-badge:hover { opacity: 1; }
  .nav-powered-badge span { font-size: 12px; font-weight: 600; letter-spacing: -.1px; }

  /* ── New Revision form ── */
  .revision-form { background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; margin-top: 4px; }
  .revision-form h4 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: var(--text); }
  .rev-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
  .rev-field { display: flex; flex-direction: column; gap: 4px; }
  .rev-field.full { grid-column: 1 / -1; }
  .rev-field label { font-size: 11px; font-weight: 500; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
  .rev-field input { background: var(--surface); border: 1px solid var(--border); color: var(--text); border-radius: var(--radius); padding: 6px 10px; font-size: 13px; font-family: inherit; }
  .rev-field input:focus { outline: none; border-color: var(--blue-light); }
  .rev-actions { display: flex; gap: 8px; }
  .rev-feedback { margin-top: 10px; font-size: 13px; }
  .rev-feedback.ok  { color: var(--green); }
  .rev-feedback.err { color: var(--red); }

  /* ── Content area ── */
  .content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  .toolbar {
    display: flex; gap: 10px; align-items: center;
    padding: 10px 20px; border-bottom: 1px solid var(--border);
    background: var(--surface); flex-wrap: wrap; flex-shrink: 0;
  }

  select, button {
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
    border-radius: var(--radius); padding: 6px 12px; font-size: 13px; cursor: pointer;
    transition: border-color .15s, background .15s;
  }
  select:hover, button:hover { border-color: var(--blue); }
  select:focus, button:focus { outline: none; border-color: var(--blue-light); }
  button.primary { background: var(--blue); border-color: var(--blue); font-weight: 500; }
  button.primary:hover { background: #0066ba; border-color: #0066ba; }

  .spin { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  main { flex: 1; overflow-y: auto; padding: 20px; }

  .error-box {
    background: #3b1b1b; border: 1px solid #7f3434;
    border-radius: var(--radius); padding: 14px 16px;
    color: var(--red); margin-bottom: 18px; font-size: 13px; white-space: pre-wrap;
  }

  /* Stats */
  .stats { display: flex; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }
  .stat {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 12px 18px; flex: 1; min-width: 120px;
  }
  .stat .val { font-size: 24px; font-weight: 700; color: var(--blue-light); }
  .stat .lbl { font-size: 11px; color: var(--muted); margin-top: 2px; text-transform: uppercase; letter-spacing: .5px; }

  /* Cards */
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 14px; cursor: pointer;
    transition: border-color .15s, transform .1s;
  }
  .card:hover { border-color: var(--blue); transform: translateY(-1px); }
  .card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
  .card-name { font-weight: 600; font-size: 14px; word-break: break-all; }
  .card-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .card-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 5px 10px; }
  .meta-item .k { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .4px; }
  .meta-item .v { font-size: 12px; margin-top: 1px; word-break: break-all; }

  /* Badges */
  .badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px; white-space: nowrap; flex-shrink: 0; }
  .badge.running  { background: #0d3b26; color: var(--green);  border: 1px solid #1a6b42; }
  .badge.stopped  { background: #3b1b1b; color: var(--red);    border: 1px solid #7f3434; }
  .badge.degraded { background: #3b2e00; color: var(--yellow); border: 1px solid #7f6400; }
  .badge.unknown  { background: var(--surface2); color: var(--muted); border: 1px solid var(--border); }
  .badge.deallocated { background: #2a1a3b; color: #c084fc; border: 1px solid #6d28d9; }

  /* Empty */
  .empty { text-align: center; color: var(--muted); padding: 60px 20px; }
  .empty svg { display: block; margin: 0 auto 12px; opacity: .3; }

  /* Modal */
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.65); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 24px; }
  .overlay.hidden { display: none; }
  .modal { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; width: 100%; max-width: 680px; max-height: 85vh; display: flex; flex-direction: column; }
  .modal-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  .modal-header h2 { font-size: 16px; }
  .modal-close { background: none; border: none; color: var(--muted); font-size: 22px; cursor: pointer; line-height: 1; padding: 0 4px; }
  .modal-close:hover { color: var(--text); }
  .modal-body { padding: 18px 20px; overflow-y: auto; flex: 1; }

  .detail-section { margin-bottom: 18px; }
  .detail-section h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; color: var(--muted); margin-bottom: 8px; }
  .detail-grid { display: grid; grid-template-columns: 150px 1fr; gap: 5px 12px; }
  .detail-grid .k { color: var(--muted); font-size: 12px; }
  .detail-grid .v { font-size: 13px; word-break: break-all; }

  .replicas-list { display: flex; flex-direction: column; gap: 6px; }
  .replica { background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; padding: 7px 12px; font-size: 12px; display: flex; justify-content: space-between; align-items: center; }
  .replica .rname { font-family: monospace; font-size: 11px; color: var(--muted); }

  /* NSG table */
  .nsg-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 4px; }
  .nsg-table th { text-align: left; color: var(--muted); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; padding: 4px 8px; border-bottom: 1px solid var(--border); }
  .nsg-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  .nsg-table tr:last-child td { border-bottom: none; }
  .nsg-table tr:hover td { background: var(--surface2); }
  .mono { font-family: monospace; font-size: 11px; }
  .nsg-table .actions { display: flex; gap: 4px; opacity: 0; transition: opacity .15s; }
  .nsg-table tr:hover .actions { opacity: 1; }
  .btn-icon {
    background: var(--surface2); border: 1px solid var(--border); color: var(--muted);
    border-radius: 5px; padding: 2px 7px; font-size: 11px; cursor: pointer; line-height: 1.6;
    transition: background .12s, color .12s, border-color .12s;
  }
  .btn-icon:hover { color: var(--text); border-color: var(--blue); background: var(--surface); }
  .btn-icon.danger:hover { color: var(--red); border-color: var(--red); }

  /* Add rule form */
  .nsg-form { background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
  .nsg-form-row { display: grid; grid-template-columns: 130px 1fr; align-items: start; gap: 8px; }
  .nsg-form-row label { font-size: 12px; color: var(--muted); padding-top: 7px; }
  .nsg-form input, .nsg-form select {
    width: 100%; background: var(--surface); border: 1px solid var(--border); color: var(--text);
    border-radius: 6px; padding: 6px 10px; font-size: 13px;
  }
  .nsg-form input:focus, .nsg-form select:focus { outline: none; border-color: var(--blue-light); }

  /* Search bar */
  .search-wrap { position: relative; margin-left: auto; }
  .search-wrap input {
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
    border-radius: var(--radius); padding: 6px 28px 6px 30px; font-size: 13px; width: 200px;
    transition: border-color .15s, width .2s;
  }
  .search-wrap input:focus { outline: none; border-color: var(--blue-light); width: 260px; }
  .search-wrap input::placeholder { color: var(--muted); }
  .search-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: var(--muted); pointer-events: none; line-height: 0; }
  .search-clear { position: absolute; right: 7px; top: 50%; transform: translateY(-50%);
    background: none; border: none; color: var(--muted); cursor: pointer; font-size: 13px;
    padding: 0; line-height: 1; display: none; }
  .search-clear.visible { display: block; }
  .search-clear:hover { color: var(--text); border: none; background: none; }

  /* View pages */
  .view { display: none; }
  .view.active { display: contents; }

  /* Storage breadcrumb */
  .breadcrumb { display: flex; align-items: center; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
  .breadcrumb .bc-btn {
    background: none; border: none; color: var(--blue-light); font-size: 13px; cursor: pointer;
    padding: 2px 4px; border-radius: 4px;
  }
  .breadcrumb .bc-btn:hover { background: rgba(46,168,255,.1); }
  .breadcrumb .bc-sep { color: var(--muted); font-size: 13px; }
  .breadcrumb .bc-cur { font-size: 13px; color: var(--text); font-weight: 500; }

  /* Generic data table (shared by storage containers & blobs) */
  .data-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 4px; }
  .data-table th { text-align: left; color: var(--muted); font-weight: 500; font-size: 11px;
    text-transform: uppercase; letter-spacing: .4px; padding: 6px 10px; border-bottom: 1px solid var(--border); }
  .data-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tr:hover td { background: var(--surface2); }
  .data-table .row-actions { display: flex; gap: 4px; opacity: 0; transition: opacity .15s; }
  .data-table tr:hover .row-actions { opacity: 1; }
  .data-table .clickable { cursor: pointer; color: var(--blue-light); }
  .data-table .clickable:hover { text-decoration: underline; }

  /* Upload area */
  .upload-bar { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
  .upload-bar label.file-pick {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--blue); border: 1px solid var(--blue); color: #fff;
    border-radius: var(--radius); padding: 6px 14px; font-size: 13px; cursor: pointer; font-weight: 500;
    transition: background .15s;
  }
  .upload-bar label.file-pick:hover { background: #0066ba; }
  #upload-status { font-size: 12px; color: var(--muted); }
</style>
</head>
<body>

<header>
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="5" fill="#0078d4"/>
    <path d="M6 17l3-10 4 7 2-3.5 3 6.5" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
  <h1>Azure Dashboard</h1>
  <span class="last-refresh" id="last-refresh"></span>
</header>

<div class="layout">

  <!-- Sidebar -->
  <nav>
    <div class="nav-section-label">Compute</div>

    <div class="nav-item active" id="nav-ca" onclick="switchView('container-apps')">
      <!-- Container Apps icon -->
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
        <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
        <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
        <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
      </svg>
      Container Apps
    </div>

    <div class="nav-item" id="nav-vm" onclick="switchView('vms')">
      <!-- VM icon -->
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="1" y="3" width="14" height="9" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
        <path d="M5 12v1.5M11 12v1.5M3.5 13.5h9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        <path d="M5 7.5h2M9 7.5h2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
      </svg>
      Virtual Machines
    </div>

    <div class="nav-section-label">Integration</div>

    <div class="nav-item" id="nav-apim" onclick="switchView('apim')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6.3" stroke="currentColor" stroke-width="1.4"/>
        <path d="M5 8h6M8 5v6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        <path d="M5.5 5.5C6.5 6.5 6.5 9.5 5.5 10.5M10.5 5.5C9.5 6.5 9.5 9.5 10.5 10.5" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
      </svg>
      API Management
    </div>

    <div class="nav-section-label">Storage</div>

    <div class="nav-item" id="nav-storage" onclick="switchView('storage')">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="1" y="3" width="14" height="4" rx="1.2" stroke="currentColor" stroke-width="1.4"/>
        <rect x="1" y="9" width="14" height="4" rx="1.2" stroke="currentColor" stroke-width="1.4"/>
        <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
        <circle cx="12.5" cy="11" r="1" fill="currentColor"/>
      </svg>
      Storage Accounts
    </div>

    <!-- Powered by Claude -->
    <div class="nav-powered">
      <div class="nav-powered-label">Powered by</div>
      <a class="nav-powered-badge" href="https://claude.ai" target="_blank" title="Anthropic Claude">
        <!-- Anthropic / Claude logomark -->
        <svg width="20" height="20" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M32.2 6H27.1L23 14.9L18.9 6H13.8L21.1 20.7H24.9L32.2 6Z" fill="#D4956A"/>
          <path d="M13.8 40H18.9L23 31.1L27.1 40H32.2L24.9 25.3H21.1L13.8 40Z" fill="#D4956A"/>
        </svg>
        <span>Anthropic Claude</span>
      </a>
    </div>
  </nav>

  <!-- Content -->
  <div class="content">

    <!-- Toolbar (shared) -->
    <div class="toolbar">
      <select id="sub-select"><option value="">All subscriptions</option></select>
      <select id="rg-select"><option value="">All resource groups</option></select>
      <button class="primary" id="refresh-btn" onclick="refresh()">&#8635; Refresh</button>
      <span id="status-text" style="font-size:12px;color:var(--muted)"></span>
      <div class="search-wrap">
        <span class="search-icon">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" stroke-width="1.4"/>
            <path d="M9 9l2.5 2.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          </svg>
        </span>
        <input type="text" id="search-input" placeholder="Search…" oninput="onSearchInput(this)" onkeydown="if(event.key==='Escape')clearSearch()"/>
        <button class="search-clear" id="search-clear" onclick="clearSearch()" title="Clear search">&#10005;</button>
      </div>
    </div>

    <main>
      <div id="error-area"></div>

      <!-- Container Apps view -->
      <div class="view active" id="view-container-apps">
        <div class="stats" id="ca-stats" style="display:none">
          <div class="stat"><div class="val" id="ca-total">0</div><div class="lbl">Total</div></div>
          <div class="stat"><div class="val" id="ca-running" style="color:var(--green)">0</div><div class="lbl">Running</div></div>
          <div class="stat"><div class="val" id="ca-stopped" style="color:var(--red)">0</div><div class="lbl">Stopped</div></div>
          <div class="stat"><div class="val" id="ca-rgs">0</div><div class="lbl">Resource Groups</div></div>
        </div>
        <div class="grid" id="ca-grid"></div>
        <div class="empty" id="ca-empty" style="display:none">
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none"><rect x="6" y="6" width="32" height="32" rx="4" stroke="#8892a4" stroke-width="1.8"/><path d="M14 22h16M22 14v16" stroke="#8892a4" stroke-width="1.8" stroke-linecap="round"/></svg>
          No container apps found.
        </div>
      </div>

      <!-- VMs view -->
      <div class="view" id="view-vms">
        <div class="stats" id="vm-stats" style="display:none">
          <div class="stat"><div class="val" id="vm-total">0</div><div class="lbl">Total</div></div>
          <div class="stat"><div class="val" id="vm-running" style="color:var(--green)">0</div><div class="lbl">Running</div></div>
          <div class="stat"><div class="val" id="vm-stopped" style="color:var(--red)">0</div><div class="lbl">Stopped/Dealloc</div></div>
          <div class="stat"><div class="val" id="vm-rgs">0</div><div class="lbl">Resource Groups</div></div>
        </div>
        <div class="grid" id="vm-grid"></div>
        <div class="empty" id="vm-empty" style="display:none">
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none"><rect x="4" y="10" width="36" height="24" rx="3" stroke="#8892a4" stroke-width="1.8"/><path d="M14 34v3M30 34v3M10 37h24" stroke="#8892a4" stroke-width="1.8" stroke-linecap="round"/></svg>
          No virtual machines found.
        </div>
      </div>

      <!-- Storage view -->
      <div class="view" id="view-storage">
        <div class="stats" id="sa-stats" style="display:none">
          <div class="stat"><div class="val" id="sa-total">0</div><div class="lbl">Accounts</div></div>
          <div class="stat"><div class="val" id="sa-rgs">0</div><div class="lbl">Resource Groups</div></div>
          <div class="stat"><div class="val" id="sa-regions">0</div><div class="lbl">Regions</div></div>
        </div>
        <div id="storage-breadcrumb" class="breadcrumb" style="display:none"></div>
        <div id="storage-content"></div>
        <div class="empty" id="sa-empty" style="display:none">
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none"><rect x="4" y="10" width="36" height="10" rx="2.5" stroke="#8892a4" stroke-width="1.8"/><rect x="4" y="24" width="36" height="10" rx="2.5" stroke="#8892a4" stroke-width="1.8"/><circle cx="36" cy="15" r="2.5" fill="#8892a4"/><circle cx="36" cy="29" r="2.5" fill="#8892a4"/></svg>
          No storage accounts found.
        </div>
      </div>

      <!-- APIM view -->
      <div class="view" id="view-apim">
        <div class="stats" id="apim-stats" style="display:none">
          <div class="stat"><div class="val" id="apim-total">0</div><div class="lbl">Services</div></div>
          <div class="stat"><div class="val" id="apim-rgs">0</div><div class="lbl">Resource Groups</div></div>
          <div class="stat"><div class="val" id="apim-regions">0</div><div class="lbl">Regions</div></div>
        </div>
        <div id="apim-breadcrumb" class="breadcrumb" style="display:none"></div>
        <div id="apim-content"></div>
        <div class="empty" id="apim-empty" style="display:none">
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none"><circle cx="22" cy="22" r="17" stroke="#8892a4" stroke-width="1.8"/><path d="M14 22h16M22 14v16" stroke="#8892a4" stroke-width="1.8" stroke-linecap="round"/></svg>
          No API Management services found.
        </div>
      </div>

    </main>
  </div>
</div>

<!-- Modal -->
<div class="overlay hidden" id="overlay" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-header">
      <h2 id="modal-title">Details</h2>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body" id="modal-body">Loading…</div>
  </div>
</div>

<script>
let currentView = 'container-apps';
let allApps = [];
let allVMs = [];
let allAPIM = [];
let apimDrilldown = 'services'; // 'services' | 'apis' | 'operations'
let currentAPIMService = null;
let currentAPIMApi = null;
let lastAPIMApis = [];
let lastAPIMOperations = [];
let subscriptions = [];
let allStorageAccounts      = [];
let storageDrilldown        = 'accounts'; // 'accounts' | 'containers' | 'blobs'
let currentSAAccount        = null;   // full account object
let currentSAContainer      = null;   // container name string
let lastContainersData      = [];     // cache for search re-filter
let lastBlobsData           = [];     // cache for search re-filter
let currentSAContainerSub   = '';     // eSub when containers were loaded
let currentSAContainerECont = '';     // eContainer when blobs were loaded

async function apiFetch(path, options) {
  try {
    const res = await fetch(path, options);
    return res.json();
  } catch (e) {
    return { error: e.message };
  }
}

// ── View switching ──
function switchView(view) {
  currentView = view;
  clearSearch();
  document.getElementById('view-container-apps').classList.toggle('active', view === 'container-apps');
  document.getElementById('view-vms').classList.toggle('active', view === 'vms');
  document.getElementById('view-storage').classList.toggle('active', view === 'storage');
  document.getElementById('view-apim').classList.toggle('active', view === 'apim');
  document.getElementById('nav-ca').classList.toggle('active', view === 'container-apps');
  document.getElementById('nav-vm').classList.toggle('active', view === 'vms');
  document.getElementById('nav-storage').classList.toggle('active', view === 'storage');
  document.getElementById('nav-apim').classList.toggle('active', view === 'apim');
  refresh();
}

// ── Badges ──
function caBadge(app) {
  const s = (app.properties?.runningStatus || app.properties?.provisioningState || '').toLowerCase();
  if (s === 'running')  return '<span class="badge running">Running</span>';
  if (s === 'stopped')  return '<span class="badge stopped">Stopped</span>';
  if (s === 'degraded') return '<span class="badge degraded">Degraded</span>';
  return `<span class="badge unknown">${s || 'Unknown'}</span>`;
}

function vmBadge(vm) {
  const s = (vm.powerState || '').toLowerCase();
  if (s.includes('running'))     return '<span class="badge running">Running</span>';
  if (s.includes('deallocated')) return '<span class="badge deallocated">Deallocated</span>';
  if (s.includes('stopped'))     return '<span class="badge stopped">Stopped</span>';
  return `<span class="badge unknown">${vm.powerState || 'Unknown'}</span>`;
}

// ── Container Apps render ──
function renderContainerApps(apps) {
  const grid  = document.getElementById('ca-grid');
  const empty = document.getElementById('ca-empty');
  const stats = document.getElementById('ca-stats');

  if (!apps.length) {
    grid.innerHTML = '';
    empty.style.display = '';
    stats.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  stats.style.display = '';

  const running = apps.filter(a => (a.properties?.runningStatus || '').toLowerCase() === 'running').length;
  const stopped = apps.filter(a => (a.properties?.runningStatus || '').toLowerCase() === 'stopped').length;
  document.getElementById('ca-total').textContent   = apps.length;
  document.getElementById('ca-running').textContent = running;
  document.getElementById('ca-stopped').textContent = stopped;
  document.getElementById('ca-rgs').textContent     = new Set(apps.map(a => a.resourceGroup)).size;

  grid.innerHTML = apps.map(app => {
    const rg    = app.resourceGroup || '—';
    const image = app.properties?.template?.containers?.[0]?.image || '—';
    const minR  = app.properties?.template?.scale?.minReplicas ?? '?';
    const maxR  = app.properties?.template?.scale?.maxReplicas ?? '?';
    const sub   = app.subscriptionId || '';
    return `
      <div class="card" onclick="showCADetail('${enc(app.name)}','${enc(rg)}','${enc(sub)}')">
        <div class="card-header">
          <div><div class="card-name">${app.name}</div><div class="card-sub">${rg}</div></div>
          ${caBadge(app)}
        </div>
        <div class="card-meta">
          <div class="meta-item"><div class="k">Location</div><div class="v">${app.location || '—'}</div></div>
          <div class="meta-item"><div class="k">Replicas</div><div class="v">${minR}–${maxR}</div></div>
          <div class="meta-item" style="grid-column:1/-1"><div class="k">Image</div><div class="v">${image}</div></div>
        </div>
      </div>`;
  }).join('');
}

// ── VM render ──
function renderVMs(vms) {
  const grid  = document.getElementById('vm-grid');
  const empty = document.getElementById('vm-empty');
  const stats = document.getElementById('vm-stats');

  if (!vms.length) {
    grid.innerHTML = '';
    empty.style.display = '';
    stats.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  stats.style.display = '';

  const running = vms.filter(v => (v.powerState || '').toLowerCase().includes('running')).length;
  const stopped = vms.filter(v => {
    const s = (v.powerState || '').toLowerCase();
    return s.includes('stopped') || s.includes('deallocated');
  }).length;
  document.getElementById('vm-total').textContent   = vms.length;
  document.getElementById('vm-running').textContent = running;
  document.getElementById('vm-stopped').textContent = stopped;
  document.getElementById('vm-rgs').textContent     = new Set(vms.map(v => v.resourceGroup)).size;

  grid.innerHTML = vms.map(vm => {
    const rg   = vm.resourceGroup || '—';
    const size = vm.hardwareProfile?.vmSize || '—';
    const os   = vm.storageProfile?.osDisk?.osType || '—';
    const loc  = vm.location || '—';
    const sub  = vm.id?.split('/')[2] || '';
    const pip  = vm.publicIps || '—';
    const ps   = (vm.powerState || '').toLowerCase();
    const canStart = ps.includes('deallocated') || ps.includes('stopped');
    const startBtn = canStart
      ? `<button class="primary" style="font-size:12px;padding:4px 10px;margin-top:8px"
           onclick="event.stopPropagation();startVM('${enc(vm.name)}','${enc(rg)}','${enc(sub)}',this)">
           &#9654; Start
         </button>`
      : '';
    return `
      <div class="card" onclick="showVMDetail('${enc(vm.name)}','${enc(rg)}','${enc(sub)}')">
        <div class="card-header">
          <div><div class="card-name">${vm.name}</div><div class="card-sub">${rg}</div></div>
          ${vmBadge(vm)}
        </div>
        <div class="card-meta">
          <div class="meta-item"><div class="k">Location</div><div class="v">${loc}</div></div>
          <div class="meta-item"><div class="k">OS</div><div class="v">${os}</div></div>
          <div class="meta-item"><div class="k">Size</div><div class="v">${size}</div></div>
          <div class="meta-item"><div class="k">Public IP</div><div class="v">${pip}</div></div>
        </div>
        ${startBtn}
      </div>`;
  }).join('');
}

async function startVM(name, rg, sub, btn) {
  btn.disabled = true;
  btn.textContent = '⏳ Starting…';
  const qs = `?resource_group=${enc(decodeURIComponent(rg))}&subscription=${enc(sub)}`;
  try {
    const res = await apiFetch(`/api/vms/${name}/start${qs}`, { method: 'POST' });
    if (res.error) { btn.textContent = '✖ ' + res.error; btn.disabled = false; return; }
    btn.textContent = '✔ Started';
    btn.style.background = '#1a6e3c';
    // refresh VM list after a short delay so the new state is visible
    setTimeout(() => loadVMs(), 3000);
  } catch(e) {
    btn.textContent = '✖ Failed';
    btn.disabled = false;
  }
}

// ── APIM render ──
function apimTierBadge(sku) {
  const t = (sku?.name || '').toLowerCase();
  if (t === 'consumption') return '<span class="badge running">Consumption</span>';
  if (t === 'developer')   return '<span class="badge unknown">Developer</span>';
  if (t === 'basic')       return '<span class="badge unknown">Basic</span>';
  if (t === 'standard')    return '<span class="badge deallocated">Standard</span>';
  if (t === 'premium')     return '<span class="badge stopped">Premium</span>';
  return `<span class="badge unknown">${sku?.name || '?'}</span>`;
}

function methodBadge(method) {
  const m = (method || 'GET').toUpperCase();
  const colors = { GET:'#1d6fa4', POST:'#276749', PUT:'#744210', DELETE:'#7f1d1d', PATCH:'#4c1d6b' };
  const bg = colors[m] || '#2d3148';
  return `<span style="background:${bg};color:#fff;border-radius:4px;padding:1px 7px;font-size:11px;font-weight:700;letter-spacing:.3px">${m}</span>`;
}

function renderAPIMServices(services) {
  const content = document.getElementById('apim-content');
  const empty   = document.getElementById('apim-empty');
  const stats   = document.getElementById('apim-stats');
  const bc      = document.getElementById('apim-breadcrumb');
  bc.style.display = 'none';
  if (!services.length) {
    content.innerHTML = ''; empty.style.display = ''; stats.style.display = 'none'; return;
  }
  empty.style.display = 'none'; stats.style.display = '';
  document.getElementById('apim-total').textContent   = allAPIM.length;
  document.getElementById('apim-rgs').textContent     = new Set(allAPIM.map(s => s.resourceGroup)).size;
  document.getElementById('apim-regions').textContent = new Set(allAPIM.map(s => s.location)).size;
  content.innerHTML = `<table class="tbl">
    <thead><tr><th>Name</th><th>Resource Group</th><th>Location</th><th>Tier</th><th>Gateway URL</th></tr></thead>
    <tbody>${services.map(s => {
      const sub = (s.id || '').split('/')[2] || '';
      return `<tr style="cursor:pointer" onclick="loadAPIMApis('${enc(s.name)}','${enc(s.resourceGroup)}','${enc(sub)}')">
        <td><strong>${s.name}</strong></td>
        <td>${s.resourceGroup}</td>
        <td>${s.location || '—'}</td>
        <td>${apimTierBadge(s.sku)}</td>
        <td style="font-size:12px;color:var(--muted)">${s.gatewayUrl || '—'}</td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

function renderAPIMApis(apis) {
  const content = document.getElementById('apim-content');
  if (!apis.length) { content.innerHTML = '<div class="empty">No APIs found in this service.</div>'; return; }
  const svc = currentAPIMService;
  const eSvc = enc(svc?.name || '');
  const eRg  = enc(svc?.resourceGroup || '');
  const eSub = enc((svc?.id || '').split('/')[2] || '');
  content.innerHTML = `<table class="tbl">
    <thead><tr><th>API Name</th><th>Path</th><th>Protocol(s)</th><th>Version</th><th>Description</th><th></th></tr></thead>
    <tbody>${apis.map(a => `<tr>
      <td style="cursor:pointer" onclick="loadAPIMOperations('${enc(a.name)}','${enc(a.displayName || a.name)}')"><strong>${a.displayName || a.name}</strong></td>
      <td style="font-family:monospace;font-size:12px;cursor:pointer" onclick="loadAPIMOperations('${enc(a.name)}','${enc(a.displayName || a.name)}')">${a.path || '—'}</td>
      <td>${(a.protocols || []).join(', ') || '—'}</td>
      <td>${a.apiVersion || '—'}</td>
      <td style="font-size:12px;color:var(--muted)">${a.description || ''}</td>
      <td><button onclick="event.stopPropagation();showAPIMPolicy('${eSvc}','${eRg}','${enc(a.name)}','${enc(a.displayName||a.name)}','${eSub}')"
            style="font-size:11px;padding:3px 9px">&#128196; Policy</button></td>
    </tr>`).join('')}</tbody>
  </table>`;
}

async function showAPIMPolicy(eSvc, eRg, eApiId, eApiName, eSub) {
  openModal(`Policy — ${decodeURIComponent(eApiName)}`);
  const url = `/api/apim/${eSvc}/apis/${eApiId}/policy?resource_group=${eRg}&subscription=${eSub}`;
  const data = await apiFetch(url);
  const body = document.getElementById('modal-body');
  if (data.error) {
    body.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; return;
  }
  // Azure returns the XML in the "value" field
  const xml = data.data?.value || data.data?.properties?.value || '';
  if (!xml) { body.innerHTML = '<div style="color:var(--muted);padding:10px">No policy defined for this API.</div>'; return; }
  // Pretty-print and escape XML for display
  const pretty = formatXml(xml);
  body.innerHTML = `
    <div style="display:flex;justify-content:flex-end;margin-bottom:8px">
      <button onclick="copyToClipboard(this,'${encodeURIComponent(xml)}')" style="font-size:12px;padding:4px 10px">&#128203; Copy</button>
    </div>
    <pre style="background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);
                padding:14px;overflow:auto;font-size:12px;line-height:1.6;color:var(--text);
                white-space:pre-wrap;word-break:break-all">${highlightXml(pretty)}</pre>`;
}

function formatXml(xml) {
  // Basic XML pretty-printer
  let indent = 0;
  return xml
    .replace(/>\s*</g, '>\n<')
    .split('\n')
    .map(line => {
      line = line.trim();
      if (!line) return '';
      if (line.match(/^<\//) || line.match(/^<[^?!][^>]*\/>$/)) indent = Math.max(0, indent - 1);
      const out = '  '.repeat(indent) + line;
      if (line.match(/^<[^\/!?][^>]*[^\/]>$/) && !line.match(/^<[^>]+\/>/)) indent++;
      return out;
    })
    .filter(Boolean)
    .join('\n');
}

function highlightXml(xml) {
  return xml
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    // re-colour: tags, attributes, values, comments
    .replace(/(&lt;\/?[\w:.-]+)/g, '<span style="color:#2ea8ff">$1</span>')
    .replace(/([\w:.-]+=)(&quot;[^&]*&quot;)/g, '<span style="color:#8892a4">$1</span><span style="color:#ffd76e">$2</span>')
    .replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span style="color:#556b7d;font-style:italic">$1</span>')
    .replace(/(&gt;)/g, '<span style="color:#2ea8ff">$1</span>');
}

function copyToClipboard(btn, encoded) {
  navigator.clipboard.writeText(decodeURIComponent(encoded)).then(() => {
    btn.textContent = '✔ Copied!';
    setTimeout(() => btn.innerHTML = '&#128203; Copy', 2000);
  });
}

function renderAPIMOperations(ops) {
  const content = document.getElementById('apim-content');
  if (!ops.length) { content.innerHTML = '<div class="empty">No operations found for this API.</div>'; return; }
  content.innerHTML = `<table class="tbl">
    <thead><tr><th>Method</th><th>Display Name</th><th>URL Template</th><th>Description</th></tr></thead>
    <tbody>${ops.map(o => `<tr>
      <td>${methodBadge(o.method)}</td>
      <td>${o.displayName || o.name || '—'}</td>
      <td style="font-family:monospace;font-size:12px">${o.urlTemplate || '—'}</td>
      <td style="font-size:12px;color:var(--muted)">${o.description || ''}</td>
    </tr>`).join('')}</tbody>
  </table>`;
}

async function loadAPIMApis(eName, eRg, eSub) {
  clearSearch();
  apimDrilldown = 'apis';
  currentAPIMService = { name: decodeURIComponent(eName), resourceGroup: decodeURIComponent(eRg), id: `/subscriptions/${eSub}` };
  const bc = document.getElementById('apim-breadcrumb');
  bc.style.display = '';
  bc.innerHTML = `<span class="bc-link" onclick="resetAPIM()">Services</span>
    <span class="bc-sep">›</span>
    <span>${decodeURIComponent(eName)}</span>`;
  document.getElementById('apim-stats').style.display = 'none';
  document.getElementById('apim-empty').style.display = 'none';
  document.getElementById('apim-content').innerHTML = '<div style="padding:20px;color:var(--muted)">Loading APIs…</div>';
  const url = `/api/apim/${eName}/apis?resource_group=${eRg}&subscription=${eSub}`;
  const data = await apiFetch(url);
  lastAPIMApis = data.data || [];
  renderAPIMApis(lastAPIMApis);
  document.getElementById('status-text').textContent = `${lastAPIMApis.length} API(s)`;
}

async function loadAPIMOperations(eApiId, eApiName) {
  clearSearch();
  apimDrilldown = 'operations';
  currentAPIMApi = { id: decodeURIComponent(eApiId), name: decodeURIComponent(eApiName) };
  const svc = currentAPIMService;
  const eSvc = enc(svc.name); const eRg = enc(svc.resourceGroup);
  const eSub = enc((svc.id || '').split('/')[2] || '');
  const bc = document.getElementById('apim-breadcrumb');
  bc.innerHTML = `<span class="bc-link" onclick="resetAPIM()">Services</span>
    <span class="bc-sep">›</span>
    <span class="bc-link" onclick="loadAPIMApis('${eSvc}','${eRg}','${eSub}')">${svc.name}</span>
    <span class="bc-sep">›</span>
    <span>${decodeURIComponent(eApiName)}</span>`;
  document.getElementById('apim-content').innerHTML = '<div style="padding:20px;color:var(--muted)">Loading operations…</div>';
  const url = `/api/apim/${eSvc}/apis/${eApiId}/operations?resource_group=${eRg}&subscription=${eSub}`;
  const data = await apiFetch(url);
  lastAPIMOperations = data.data || [];
  renderAPIMOperations(lastAPIMOperations);
  document.getElementById('status-text').textContent = `${lastAPIMOperations.length} operation(s)`;
}

function resetAPIM() {
  clearSearch();
  apimDrilldown = 'services';
  currentAPIMService = null;
  currentAPIMApi = null;
  lastAPIMApis = [];
  lastAPIMOperations = [];
  document.getElementById('apim-breadcrumb').style.display = 'none';
  filterAndRender();
}

// ── Filters ──
function appSubId(a) {
  // subscriptionId may be a top-level field or embedded in the resource id
  return (a.subscriptionId || (a.id || '').split('/')[2] || '').toLowerCase();
}

function filterAndRender() {
  const sub = document.getElementById('sub-select').value.toLowerCase();
  const rg  = document.getElementById('rg-select').value;
  const q   = document.getElementById('search-input').value.trim().toLowerCase();

  function hit(...terms) {
    return !q || terms.some(t => (t || '').toLowerCase().includes(q));
  }

  if (currentView === 'container-apps') {
    let apps = allApps;
    if (sub) apps = apps.filter(a => appSubId(a) === sub);
    if (rg)  apps = apps.filter(a => (a.resourceGroup || '').toLowerCase() === rg.toLowerCase());
    if (q)   apps = apps.filter(a => hit(a.name, a.resourceGroup, a.location,
                                         a.properties?.template?.containers?.[0]?.image));
    renderContainerApps(apps);
    document.getElementById('status-text').textContent =
      allApps.length ? `${apps.length} of ${allApps.length} app(s)` : '';

  } else if (currentView === 'vms') {
    let vms = allVMs;
    if (sub) vms = vms.filter(v => (v.id || '').split('/')[2].toLowerCase() === sub);
    if (rg)  vms = vms.filter(v => (v.resourceGroup || '').toLowerCase() === rg.toLowerCase());
    if (q)   vms = vms.filter(v => hit(v.name, v.resourceGroup, v.location,
                                        v.hardwareProfile?.vmSize, v.powerState, v.publicIps));
    renderVMs(vms);
    document.getElementById('status-text').textContent =
      allVMs.length ? `${vms.length} of ${allVMs.length} VM(s)` : '';

  } else if (currentView === 'storage') {
    // Inside a container or blob listing: search in-place without resetting drilldown
    if (storageDrilldown === 'containers') {
      const filtered = q ? lastContainersData.filter(c => (c.name || '').toLowerCase().includes(q))
                         : lastContainersData;
      renderContainerTable(filtered, currentSAContainerSub);
      document.getElementById('status-text').textContent =
        `${filtered.length} of ${lastContainersData.length} container(s)`;
      return;
    }
    if (storageDrilldown === 'blobs') {
      const filtered = q ? lastBlobsData.filter(b => (b.name || '').toLowerCase().includes(q))
                         : lastBlobsData;
      renderBlobTable(filtered, currentSAContainerECont, currentSAContainerSub);
      document.getElementById('status-text').textContent =
        `${filtered.length} of ${lastBlobsData.length} blob(s)`;
      return;
    }
    // Accounts level
    storageDrilldown = 'accounts';
    currentSAAccount = null;
    currentSAContainer = null;
    let accounts = allStorageAccounts;
    if (sub) accounts = accounts.filter(a => (a.id || '').split('/')[2].toLowerCase() === sub);
    if (rg)  accounts = accounts.filter(a => (a.resourceGroup || '').toLowerCase() === rg.toLowerCase());
    if (q)   accounts = accounts.filter(a => hit(a.name, a.resourceGroup, a.location, a.kind));
    renderStorageAccounts(accounts);
    document.getElementById('status-text').textContent =
      allStorageAccounts.length ? `${accounts.length} of ${allStorageAccounts.length} account(s)` : '';

  } else if (currentView === 'apim') {
    if (apimDrilldown === 'apis') {
      const filtered = q ? lastAPIMApis.filter(a =>
        [(a.displayName||''), (a.path||''), (a.description||'')].some(t => t.toLowerCase().includes(q)))
        : lastAPIMApis;
      renderAPIMApis(filtered);
      document.getElementById('status-text').textContent = `${filtered.length} of ${lastAPIMApis.length} API(s)`;
      return;
    }
    if (apimDrilldown === 'operations') {
      const filtered = q ? lastAPIMOperations.filter(o =>
        [(o.displayName||''), (o.urlTemplate||''), (o.method||'')].some(t => t.toLowerCase().includes(q)))
        : lastAPIMOperations;
      renderAPIMOperations(filtered);
      document.getElementById('status-text').textContent = `${filtered.length} of ${lastAPIMOperations.length} operation(s)`;
      return;
    }
    apimDrilldown = 'services';
    let services = allAPIM;
    if (sub) services = services.filter(s => (s.id || '').split('/')[2].toLowerCase() === sub);
    if (rg)  services = services.filter(s => (s.resourceGroup || '').toLowerCase() === rg.toLowerCase());
    if (q)   services = services.filter(s => hit(s.name, s.resourceGroup, s.location, s.sku?.name, s.gatewayUrl));
    renderAPIMServices(services);
    document.getElementById('status-text').textContent =
      allAPIM.length ? `${services.length} of ${allAPIM.length} service(s)` : '';
  }
}

// ── Search ──
function onSearchInput(el) {
  document.getElementById('search-clear').classList.toggle('visible', el.value.length > 0);
  filterAndRender();
}
function clearSearch() {
  const el = document.getElementById('search-input');
  if (!el) return;
  el.value = '';
  const clr = document.getElementById('search-clear');
  if (clr) clr.classList.remove('visible');
  // Don't call filterAndRender here — callers do it when needed (switchView → refresh)
}

// ── Subscriptions & RGs ──
async function loadSubscriptions() {
  const data = await apiFetch('/api/subscriptions');
  subscriptions = data.data || [];
  const sel = document.getElementById('sub-select');
  sel.innerHTML = '<option value="">All subscriptions</option>' +
    subscriptions.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  sel.onchange = () => { loadResourceGroups(); filterAndRender(); };
}

async function loadResourceGroups() {
  const sub = document.getElementById('sub-select').value;
  const url = sub ? `/api/resource-groups?subscription=${sub}` : '/api/resource-groups';
  const data = await apiFetch(url);
  const sel  = document.getElementById('rg-select');
  sel.innerHTML = '<option value="">All resource groups</option>' +
    (data.data || []).map(r => `<option value="${r.name}">${r.name}</option>`).join('');
  sel.onchange = filterAndRender;
}

// ── Refresh ──
async function refresh() {
  const btn    = document.getElementById('refresh-btn');
  const status = document.getElementById('status-text');
  const errEl  = document.getElementById('error-area');

  btn.disabled = true;
  btn.innerHTML = '<span class="spin">&#8635;</span> Loading…';
  status.textContent = '';
  errEl.innerHTML = '';

  try {
    const sub = document.getElementById('sub-select').value;
    const rg  = document.getElementById('rg-select').value;
    const params = [];
    if (sub) params.push(`subscription=${sub}`);
    if (rg)  params.push(`resource_group=${rg}`);
    const qs = params.length ? '?' + params.join('&') : '';

    if (currentView === 'container-apps') {
      status.textContent = 'Fetching container apps…';
      const data = await apiFetch('/api/container-apps' + qs);
      if (data.error) { errEl.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; allApps = []; }
      else { allApps = data.data || []; }
      filterAndRender();
    } else if (currentView === 'vms') {
      status.textContent = 'Fetching virtual machines…';
      const data = await apiFetch('/api/vms' + qs);
      if (data.error) { errEl.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; allVMs = []; }
      else { allVMs = data.data || []; }
      filterAndRender();
    } else if (currentView === 'apim') {
      status.textContent = 'Fetching API Management services…';
      apimDrilldown = 'services';
      currentAPIMService = null; currentAPIMApi = null;
      lastAPIMApis = []; lastAPIMOperations = [];
      const data = await apiFetch('/api/apim' + qs);
      if (data.error) { errEl.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; allAPIM = []; }
      else { allAPIM = data.data || []; }
      filterAndRender();

    } else if (currentView === 'storage') {
      status.textContent = 'Fetching storage accounts…';
      storageDrilldown = 'accounts';
      currentSAAccount = null;
      currentSAContainer = null;
      const data = await apiFetch('/api/storage' + qs);
      if (data.error) { errEl.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; allStorageAccounts = []; }
      else { allStorageAccounts = data.data || []; }
      filterAndRender();
    }

    document.getElementById('last-refresh').textContent = 'Refreshed ' + new Date().toLocaleTimeString();
  } catch (e) {
    errEl.innerHTML = `<div class="error-box">&#9888; ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '&#8635; Refresh';
  }
}

// ── Container App detail ──
async function showCADetail(eName, eRg, eSub) {
  openModal(decodeURIComponent(eName));
  let url = `/api/container-apps/${eName}?resource_group=${eRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  const data = await apiFetch(url);
  if (data.error) { document.getElementById('modal-body').innerHTML = `<div class="error-box">${data.error}</div>`; return; }

  const app = data.data;
  const p = app.properties || {};
  const sub = decodeURIComponent(eSub);
  const containers = p.template?.containers || [];
  const ingress = p.configuration?.ingress;
  const replicas = data.replicas || [];

  let html = section('Overview', kv([
    ['Status', caBadge(app)],
    ['Location', app.location || '—'],
    ['Resource Group', app.resourceGroup || '—'],
    ['Subscription', sub || '—'],
    ['Environment', p.managedEnvironmentId?.split('/').pop() || '—'],
  ]));

  if (containers.length) {
    html += `<div class="detail-section"><h3>Containers</h3>`;
    containers.forEach(c => {
      html += kv([
        ['Name', c.name], ['Image', c.image],
        ['CPU', (c.resources?.cpu ?? '—') + ' cores'], ['Memory', c.resources?.memory ?? '—'],
      ]);
    });
    html += `</div>`;
  }

  if (ingress) {
    const fqdn = ingress.fqdn;
    html += section('Ingress', kv([
      ['External', ingress.external ? 'Yes' : 'No'],
      ['FQDN', fqdn ? `<a href="https://${fqdn}" target="_blank" style="color:var(--blue-light)">${fqdn}</a>` : '—'],
      ['Target Port', ingress.targetPort || '—'],
      ['Transport', ingress.transport || '—'],
    ]));
  }

  const scale = p.template?.scale;
  if (scale) {
    html += section('Scaling', kv([
      ['Min Replicas', scale.minReplicas ?? '—'],
      ['Max Replicas', scale.maxReplicas ?? '—'],
    ]));
  }

  if (replicas.length) {
    html += `<div class="detail-section"><h3>Active Replicas (${replicas.length})</h3><div class="replicas-list">` +
      replicas.map(r => `<div class="replica"><span class="rname">${r.name}</span>
        <span class="badge ${(r.runningState||'').toLowerCase() === 'running' ? 'running' : 'unknown'}">${r.runningState || 'Unknown'}</span></div>`).join('') +
      `</div></div>`;
  }

  // Pre-fill values from current template for the revision form
  const curImage  = containers[0]?.image  || '';
  const curCpu    = containers[0]?.resources?.cpu    ?? '';
  const curMem    = containers[0]?.resources?.memory ?? '';
  const curMin    = scale?.minReplicas ?? '';
  const curMax    = scale?.maxReplicas ?? '';

  html += `<div class="detail-section">
    <h3>New Revision</h3>
    <div id="rev-form-wrap">
      <button class="primary" onclick="showRevisionForm()">+ Deploy New Revision</button>
    </div>
    <div class="revision-form" id="rev-form" style="display:none">
      <h4>Deploy a new revision</h4>
      <div class="rev-fields">
        <div class="rev-field full">
          <label>Image</label>
          <input id="rev-image" type="text" value="${htmlEsc(curImage)}" placeholder="e.g. myrepo/myimage:tag"/>
        </div>
        <div class="rev-field full">
          <label>Revision suffix <span style="font-weight:400;text-transform:none;letter-spacing:0">(optional — result: ${decodeURIComponent(eName)}--&lt;suffix&gt;)</span></label>
          <input id="rev-suffix" type="text" placeholder="e.g. v2 or 20240325" pattern="[a-z0-9-]+" title="Lowercase letters, numbers, and hyphens only"/>
        </div>
        <div class="rev-field">
          <label>CPU (cores)</label>
          <input id="rev-cpu" type="text" value="${curCpu}" placeholder="e.g. 0.5"/>
        </div>
        <div class="rev-field">
          <label>Memory</label>
          <input id="rev-mem" type="text" value="${curMem}" placeholder="e.g. 1Gi"/>
        </div>
        <div class="rev-field">
          <label>Min Replicas</label>
          <input id="rev-min" type="number" min="0" value="${curMin}" placeholder="0"/>
        </div>
        <div class="rev-field">
          <label>Max Replicas</label>
          <input id="rev-max" type="number" min="1" value="${curMax}" placeholder="1"/>
        </div>
      </div>
      <div class="rev-actions">
        <button class="primary" onclick="submitRevision('${eName}','${enc(decodeURIComponent(eRg))}','${enc(decodeURIComponent(eSub))}')">Deploy</button>
        <button onclick="hideRevisionForm()">Cancel</button>
      </div>
    </div>
    <div class="rev-feedback" id="rev-feedback"></div>
  </div>`;

  document.getElementById('modal-body').innerHTML = html;
}

function showRevisionForm() {
  document.getElementById('rev-form').style.display = '';
  document.getElementById('rev-form-wrap').querySelector('button').style.display = 'none';
}
function hideRevisionForm() {
  document.getElementById('rev-form').style.display = 'none';
  document.getElementById('rev-form-wrap').querySelector('button').style.display = '';
  setRevFeedback('', null);
}

async function submitRevision(eName, eRg, eSub) {
  const image = document.getElementById('rev-image').value.trim();
  if (!image) { setRevFeedback('Image is required.', false); return; }

  const payload = { image };
  const suffix = document.getElementById('rev-suffix').value.trim();
  const cpu = document.getElementById('rev-cpu').value.trim();
  const mem = document.getElementById('rev-mem').value.trim();
  const min = document.getElementById('rev-min').value.trim();
  const max = document.getElementById('rev-max').value.trim();
  if (suffix) payload.revision_suffix = suffix;
  if (cpu) payload.cpu = cpu;
  if (mem) payload.memory = mem;
  if (min !== '') payload.min_replicas = parseInt(min);
  if (max !== '') payload.max_replicas = parseInt(max);

  setRevFeedback('Deploying…', null);
  document.querySelectorAll('.rev-actions button').forEach(b => b.disabled = true);

  let url = `/api/container-apps/${eName}/revisions?resource_group=${eRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  const res = await apiFetch(url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });

  document.querySelectorAll('.rev-actions button').forEach(b => b.disabled = false);
  if (res.error) {
    setRevFeedback('Error: ' + res.error, false);
  } else {
    // Collapse form, show success message (feedback is outside the form, stays visible)
    document.getElementById('rev-form').style.display = 'none';
    document.getElementById('rev-form-wrap').querySelector('button').style.display = '';
    setRevFeedback('Revision deployed successfully!', true);
  }
}
function setRevFeedback(msg, ok) {
  const el = document.getElementById('rev-feedback');
  if (!el) return;
  el.textContent = msg;
  el.className = 'rev-feedback' + (ok === true ? ' ok' : ok === false ? ' err' : '');
}

// ── VM detail ──
async function showVMDetail(eName, eRg, eSub) {
  openModal(decodeURIComponent(eName));
  let url = `/api/vms/${eName}?resource_group=${eRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  const data = await apiFetch(url);
  if (data.error) { document.getElementById('modal-body').innerHTML = `<div class="error-box">${data.error}</div>`; return; }

  const vm = data.data;
  const hw   = vm.hardwareProfile || {};
  const stor = vm.storageProfile || {};
  const net  = vm.networkProfile || {};
  const sub  = decodeURIComponent(eSub);
  const rg   = decodeURIComponent(eRg);

  let html = section('Overview', kv([
    ['Status', vmBadge(vm)],
    ['Location', vm.location || '—'],
    ['Resource Group', rg || '—'],
    ['Subscription', sub || '—'],
    ['Size', hw.vmSize || '—'],
    ['OS Type', stor.osDisk?.osType || '—'],
    ['OS Disk', stor.osDisk?.name || '—'],
    ['Public IPs', vm.publicIps || '—'],
    ['Private IPs', vm.privateIps || '—'],
    ['FQDN', vm.fqdns || '—'],
  ])) +
  section('Hardware', kv([
    ['VM Size', hw.vmSize || '—'],
    ['Image', [stor.imageReference?.publisher, stor.imageReference?.offer, stor.imageReference?.sku].filter(Boolean).join(' / ') || '—'],
  ]));

  // NSG section placeholder — will be populated async
  html += `<div id="nsg-section"><div style="color:var(--muted);font-size:13px">Loading network security groups…</div></div>`;

  document.getElementById('modal-body').innerHTML = html;

  // Fetch NSG info async
  let nsgUrl = `/api/vms/${eName}/nsg?resource_group=${eRg}`;
  if (eSub) nsgUrl += `&subscription=${eSub}`;
  const nsgData = await apiFetch(nsgUrl);
  renderNsgSection(nsgData, eRg, eSub);
}

// Cache of rules per NSG name, so edit/delete can look up current values without re-encoding
const nsgRulesCache = {};

function renderNsgSection(nsgData, eRg, eSub) {
  const el = document.getElementById('nsg-section');
  if (!el) return;

  if (nsgData.error) {
    el.innerHTML = `<div class="error-box">NSG: ${nsgData.error}</div>`;
    return;
  }

  const nsgs = nsgData.data || [];
  if (!nsgs.length) {
    el.innerHTML = section('Network Security Groups', '<p style="color:var(--muted);font-size:13px">No NSG attached to this VM\'s NICs.</p>');
    return;
  }

  let html = '';
  nsgs.forEach(nsg => {
    const rules = (nsg.rules || [])
      .filter(r => r.direction === 'Inbound')
      .sort((a, b) => a.priority - b.priority);

    nsgRulesCache[nsg.name] = rules;

    const eNsg   = enc(nsg.name);
    const eNsgRg = enc(nsg.resourceGroup);

    const rulesHtml = rules.length
      ? `<table class="nsg-table">
          <thead><tr><th>Priority</th><th>Name</th><th>Source</th><th>Port</th><th>Protocol</th><th>Access</th><th></th></tr></thead>
          <tbody>${rules.map(r => `
            <tr id="rule-row-${eNsg}-${enc(r.name)}">
              <td>${r.priority}</td>
              <td>${r.name}</td>
              <td class="mono">${r.sourceAddressPrefix || r.sourceAddressPrefixes?.join(', ') || '*'}</td>
              <td>${r.destinationPortRange || r.destinationPortRanges?.join(', ') || '*'}</td>
              <td>${r.protocol}</td>
              <td><span class="badge ${r.access === 'Allow' ? 'running' : 'stopped'}">${r.access}</span></td>
              <td>
                <div class="actions">
                  <button class="btn-icon" title="Edit" onclick="showEditRuleForm('${eNsg}','${eNsgRg}','${eSub}','${enc(r.name)}')">&#9998;</button>
                  <button class="btn-icon danger" title="Delete" onclick="deleteNsgRule('${eNsg}','${eNsgRg}','${eSub}','${enc(r.name)}')">&#10005;</button>
                </div>
              </td>
            </tr>
            <tr id="edit-row-${eNsg}-${enc(r.name)}" style="display:none">
              <td colspan="7" style="padding:0"></td>
            </tr>`).join('')}
          </tbody>
        </table>`
      : '<p style="color:var(--muted);font-size:13px">No inbound rules.</p>';

    html += `<div class="detail-section">
      <h3>NSG: ${nsg.name} <span style="font-weight:400;color:var(--muted)">(${nsg.resourceGroup})</span></h3>
      <div id="nsg-table-${eNsg}">${rulesHtml}</div>
      <button class="primary" style="margin-top:10px;font-size:12px" onclick="showAddRuleForm('${eNsg}','${eNsgRg}','${eSub}')">
        + Add Inbound Rule
      </button>
      <div id="add-rule-form-${eNsg}" style="display:none"></div>
    </div>`;
  });

  el.innerHTML = `<div class="detail-section" style="margin-top:0"><h3 style="margin-bottom:12px">Network Security Groups</h3>${html}</div>`;
}

// ── Refresh helper: re-fetch rules and re-render the table for one NSG ──
async function refreshNsgTable(eNsg, eNsgRg, eSub) {
  let url = `/api/nsg/${eNsg}/rules?resource_group=${eNsgRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  const data = await apiFetch(url);
  if (data.error || !data.data) return;

  const nsgName = decodeURIComponent(eNsg);
  const nsgRg   = decodeURIComponent(eNsgRg);
  const rules   = (data.data || []).filter(r => r.direction === 'Inbound').sort((a,b) => a.priority - b.priority);
  nsgRulesCache[nsgName] = rules;

  // Re-render by rebuilding nsgData shape and calling renderNsgSection with updated rules
  const fakeNsgData = { data: [{ name: nsgName, resourceGroup: nsgRg, rules: data.data }] };
  renderNsgSection(fakeNsgData, eNsgRg, eSub);
}

// ── Add rule form ──
function showAddRuleForm(eNsg, eNsgRg, eSub) {
  const container = document.getElementById(`add-rule-form-${eNsg}`);
  if (!container) return;
  container.style.display = '';
  container.innerHTML = ruleFormHtml(eNsg, eNsgRg, eSub, null);
}

// ── Edit rule form ──
function showEditRuleForm(eNsg, eNsgRg, eSub, eRuleName) {
  const nsgName  = decodeURIComponent(eNsg);
  const ruleName = decodeURIComponent(eRuleName);
  const rule     = (nsgRulesCache[nsgName] || []).find(r => r.name === ruleName);

  // Hide any other open edit rows first
  document.querySelectorAll('[id^="edit-row-"]').forEach(r => { r.style.display = 'none'; r.firstElementChild.innerHTML = ''; });

  const editRow = document.getElementById(`edit-row-${eNsg}-${eRuleName}`);
  if (!editRow) return;

  editRow.style.display = '';
  editRow.firstElementChild.innerHTML = ruleFormHtml(eNsg, eNsgRg, eSub, rule);
}

// ── Shared form builder (null rule = add mode, rule object = edit mode) ──
function ruleFormHtml(eNsg, eNsgRg, eSub, rule) {
  const isEdit  = rule !== null;
  const srcIp   = rule ? (rule.sourceAddressPrefix || rule.sourceAddressPrefixes?.[0] || '') : '';
  const port    = rule ? (rule.destinationPortRange || rule.destinationPortRanges?.[0] || '') : '22';
  const proto   = rule ? rule.protocol : 'Tcp';
  const prio    = rule ? rule.priority : 1000;
  const name    = rule ? rule.name : 'allow-my-ip';
  const eRN     = rule ? enc(rule.name) : '';

  const protoOpts = ['Tcp','Udp','*'].map(p =>
    `<option value="${p}" ${proto === p ? 'selected' : ''}>${p === '*' ? 'Any' : p}</option>`).join('');

  const cancelAction = isEdit
    ? `document.getElementById('edit-row-${eNsg}-${eRN}').style.display='none'`
    : `document.getElementById('add-rule-form-${eNsg}').style.display='none'`;
  const saveAction = isEdit
    ? `submitEditRule('${eNsg}','${eNsgRg}','${eSub}','${eRN}')`
    : `submitAddRule('${eNsg}','${eNsgRg}','${eSub}')`;
  const prefix = isEdit ? `edit-${eRN}` : 'add';

  return `<div class="nsg-form" style="margin:6px 0">
    <div class="nsg-form-row">
      <label>Rule Name</label>
      <input id="rf-${prefix}-name-${eNsg}" type="text" value="${name}" ${isEdit ? 'disabled style="opacity:.5"' : 'placeholder="allow-my-ip-ssh"'}/>
    </div>
    <div class="nsg-form-row">
      <label>Source IP / CIDR</label>
      <div style="display:flex;gap:6px">
        <input id="rf-${prefix}-ip-${eNsg}" type="text" placeholder="1.2.3.4/32" value="${srcIp}" style="flex:1"/>
        <button onclick="detectMyIp('rf-${prefix}-ip-${eNsg}')" style="white-space:nowrap;font-size:12px">&#8857; My IP</button>
      </div>
    </div>
    <div class="nsg-form-row">
      <label>Destination Port</label>
      <input id="rf-${prefix}-port-${eNsg}" type="text" value="${port}" placeholder="22"/>
    </div>
    <div class="nsg-form-row">
      <label>Protocol</label>
      <select id="rf-${prefix}-proto-${eNsg}">${protoOpts}</select>
    </div>
    <div class="nsg-form-row">
      <label>Priority</label>
      <input id="rf-${prefix}-prio-${eNsg}" type="number" value="${prio}" min="100" max="4096"/>
    </div>
    <div class="nsg-form-row" style="align-items:center">
      <label></label>
      <div style="display:flex;gap:8px">
        <button class="primary" onclick="${saveAction}">${isEdit ? 'Update Rule' : 'Save Rule'}</button>
        <button onclick="${cancelAction}">Cancel</button>
      </div>
    </div>
    <div id="rf-${prefix}-status-${eNsg}" style="font-size:12px;margin-top:4px"></div>
  </div>`;
}

async function detectMyIp(inputId) {
  const ipInput = document.getElementById(inputId);
  if (!ipInput) return;
  ipInput.value = 'Detecting…';
  try {
    const res  = await fetch('https://api.ipify.org?format=json');
    const json = await res.json();
    ipInput.value = json.ip + '/32';
  } catch {
    ipInput.value = '';
    alert('Could not detect public IP. Please enter it manually.');
  }
}

// ── Submit add rule ──
async function submitAddRule(eNsg, eNsgRg, eSub) {
  const prefix   = 'add';
  const statusEl = document.getElementById(`rf-${prefix}-status-${eNsg}`);
  const name  = document.getElementById(`rf-${prefix}-name-${eNsg}`).value.trim();
  const ip    = document.getElementById(`rf-${prefix}-ip-${eNsg}`).value.trim();
  const port  = document.getElementById(`rf-${prefix}-port-${eNsg}`).value.trim();
  const proto = document.getElementById(`rf-${prefix}-proto-${eNsg}`).value;
  const prio  = document.getElementById(`rf-${prefix}-prio-${eNsg}`).value.trim();

  if (!name || !ip || !port || !prio) {
    statusEl.innerHTML = '<span style="color:var(--red)">All fields are required.</span>'; return;
  }
  statusEl.innerHTML = '<span class="spin">&#8635;</span> Creating…';

  let url = `/api/nsg/${eNsg}/rules?resource_group=${eNsgRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  try {
    const res  = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name, source_ip: ip, port, protocol: proto, priority: prio }) });
    const data = await res.json();
    if (data.error) { statusEl.innerHTML = `<span style="color:var(--red)">${data.error}</span>`; return; }
    document.getElementById(`add-rule-form-${eNsg}`).style.display = 'none';
    await refreshNsgTable(eNsg, eNsgRg, eSub);
  } catch (e) {
    statusEl.innerHTML = `<span style="color:var(--red)">${e.message}</span>`;
  }
}

// ── Submit edit rule ──
async function submitEditRule(eNsg, eNsgRg, eSub, eRuleName) {
  const prefix   = `edit-${eRuleName}`;
  const statusEl = document.getElementById(`rf-${prefix}-status-${eNsg}`);
  const ip    = document.getElementById(`rf-${prefix}-ip-${eNsg}`).value.trim();
  const port  = document.getElementById(`rf-${prefix}-port-${eNsg}`).value.trim();
  const proto = document.getElementById(`rf-${prefix}-proto-${eNsg}`).value;
  const prio  = document.getElementById(`rf-${prefix}-prio-${eNsg}`).value.trim();

  if (!ip || !port || !prio) {
    statusEl.innerHTML = '<span style="color:var(--red)">All fields are required.</span>'; return;
  }
  statusEl.innerHTML = '<span class="spin">&#8635;</span> Updating…';

  let url = `/api/nsg/${eNsg}/rules/${eRuleName}?resource_group=${eNsgRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  try {
    const res  = await fetch(url, { method:'PUT', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ source_ip: ip, port, protocol: proto, priority: prio }) });
    const data = await res.json();
    if (data.error) { statusEl.innerHTML = `<span style="color:var(--red)">${data.error}</span>`; return; }
    await refreshNsgTable(eNsg, eNsgRg, eSub);
  } catch (e) {
    statusEl.innerHTML = `<span style="color:var(--red)">${e.message}</span>`;
  }
}

// ── Delete rule — show inline confirm instead of browser confirm() ──
function deleteNsgRule(eNsg, eNsgRg, eSub, eRuleName) {
  const ruleName = decodeURIComponent(eRuleName);
  const row = document.getElementById(`rule-row-${eNsg}-${eRuleName}`);
  if (!row) return;

  // Replace action buttons with inline confirm prompt
  const actionsCell = row.querySelector('.actions');
  if (!actionsCell) return;
  actionsCell.style.opacity = '1';
  actionsCell.innerHTML = `
    <span style="font-size:11px;color:var(--red);white-space:nowrap">Delete?</span>
    <button class="btn-icon danger" onclick="confirmDeleteRule('${eNsg}','${eNsgRg}','${eSub}','${eRuleName}')">Yes</button>
    <button class="btn-icon" onclick="refreshNsgTable('${eNsg}','${eNsgRg}','${eSub}')">No</button>`;
}

async function confirmDeleteRule(eNsg, eNsgRg, eSub, eRuleName) {
  const row = document.getElementById(`rule-row-${eNsg}-${eRuleName}`);
  if (row) row.style.opacity = '.4';

  let url = `/api/nsg/${eNsg}/rules/${eRuleName}?resource_group=${eNsgRg}`;
  if (eSub) url += `&subscription=${eSub}`;
  try {
    const res  = await fetch(url, { method: 'DELETE' });
    const data = await res.json();
    if (data.error) {
      if (row) row.style.opacity = '';
      // show error inline in the row
      const actionsCell = row?.querySelector('.actions');
      if (actionsCell) actionsCell.innerHTML = `<span style="color:var(--red);font-size:11px">${data.error}</span>`;
      return;
    }
    await refreshNsgTable(eNsg, eNsgRg, eSub);
  } catch (e) {
    if (row) row.style.opacity = '';
    const actionsCell = row?.querySelector('.actions');
    if (actionsCell) actionsCell.innerHTML = `<span style="color:var(--red);font-size:11px">${e.message}</span>`;
  }
}

// ── Storage: breadcrumb ──
function updateStorageBreadcrumb() {
  const bc = document.getElementById('storage-breadcrumb');
  if (storageDrilldown === 'accounts') {
    bc.style.display = 'none'; bc.innerHTML = ''; return;
  }
  bc.style.display = '';
  const acName = currentSAAccount?.name || '';
  if (storageDrilldown === 'containers') {
    bc.innerHTML = `
      <button class="bc-btn" onclick="storageBack('accounts')">Storage Accounts</button>
      <span class="bc-sep">›</span>
      <span class="bc-cur">${acName}</span>`;
  } else {
    bc.innerHTML = `
      <button class="bc-btn" onclick="storageBack('accounts')">Storage Accounts</button>
      <span class="bc-sep">›</span>
      <button class="bc-btn" onclick="storageBack('containers')">${acName}</button>
      <span class="bc-sep">›</span>
      <span class="bc-cur">${currentSAContainer || ''}</span>`;
  }
}

async function storageBack(level) {
  if (level === 'accounts') {
    storageDrilldown = 'accounts';
    currentSAAccount = null;
    currentSAContainer = null;
    filterAndRender();
  } else if (level === 'containers') {
    storageDrilldown = 'containers';
    currentSAContainer = null;
    await loadContainers(currentSAAccount);
  }
}

// ── Storage: render accounts grid ──
function renderStorageAccounts(accounts) {
  const content = document.getElementById('storage-content');
  const empty   = document.getElementById('sa-empty');
  const stats   = document.getElementById('sa-stats');

  updateStorageBreadcrumb();

  if (!accounts.length) {
    content.innerHTML = '';
    empty.style.display = '';
    stats.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  stats.style.display = '';
  document.getElementById('sa-total').textContent   = accounts.length;
  document.getElementById('sa-rgs').textContent     = new Set(accounts.map(a => a.resourceGroup)).size;
  document.getElementById('sa-regions').textContent = new Set(accounts.map(a => a.location)).size;

  content.innerHTML = `<div class="grid">${accounts.map(a => {
    const sku  = a.sku?.name || '—';
    const kind = a.kind || '—';
    const tier = a.accessTier || '—';
    const rg   = a.resourceGroup || '—';
    const sub  = (a.id || '').split('/')[2] || '';
    return `<div class="card" onclick="loadContainersForAccount('${enc(JSON.stringify({name:a.name, resourceGroup:rg, id:a.id}))}','${enc(sub)}')">
      <div class="card-header">
        <div><div class="card-name">${a.name}</div><div class="card-sub">${rg}</div></div>
        <span class="badge unknown">${kind}</span>
      </div>
      <div class="card-meta">
        <div class="meta-item"><div class="k">Location</div><div class="v">${a.location || '—'}</div></div>
        <div class="meta-item"><div class="k">SKU</div><div class="v">${sku}</div></div>
        <div class="meta-item"><div class="k">Access Tier</div><div class="v">${tier}</div></div>
      </div>
    </div>`;
  }).join('')}</div>`;
}

async function loadContainersForAccount(eAccountJson, eSub) {
  const account = JSON.parse(decodeURIComponent(eAccountJson));
  const sub     = decodeURIComponent(eSub);
  currentSAAccount = account;
  await loadContainers(account, sub);
}

async function loadContainers(account, sub) {
  clearSearch();
  storageDrilldown = 'containers';
  currentSAContainer = null;
  updateStorageBreadcrumb();

  const content = document.getElementById('storage-content');
  content.innerHTML = '<div style="color:var(--muted);padding:20px 0">Loading containers…</div>';
  document.getElementById('sa-stats').style.display = 'none';
  document.getElementById('sa-empty').style.display = 'none';

  const eSub = enc(sub || (currentSAAccount?.id || '').split('/')[2] || '');
  const data = await apiFetch(`/api/storage/${enc(account.name)}/containers?subscription=${eSub}`);

  if (data.error) {
    content.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; return;
  }
  lastContainersData    = data.data || [];
  currentSAContainerSub = eSub;

  const q = document.getElementById('search-input').value.trim().toLowerCase();
  const visible = q ? lastContainersData.filter(c => (c.name || '').toLowerCase().includes(q))
                    : lastContainersData;
  renderContainerTable(visible, eSub);
  document.getElementById('status-text').textContent =
    `${visible.length} of ${lastContainersData.length} container(s)`;
}

function renderContainerTable(containers, eSub) {
  const content = document.getElementById('storage-content');
  if (!containers.length) {
    content.innerHTML = lastContainersData.length
      ? '<div class="empty" style="padding:40px 0">No containers match your search.</div>'
      : '<div class="empty" style="padding:40px 0">No containers in this storage account.</div>';
    return;
  }
  content.innerHTML = `
    <table class="data-table">
      <thead><tr><th>Container</th><th>Last Modified</th><th>Lease State</th><th>Public Access</th><th></th></tr></thead>
      <tbody>${containers.map(c => `
        <tr>
          <td class="clickable" onclick="loadBlobs('${enc(c.name)}','${eSub}')">${c.name}</td>
          <td>${fmtDate(c.properties?.lastModified)}</td>
          <td>${c.properties?.leaseState || '—'}</td>
          <td>${c.properties?.publicAccess || 'Private'}</td>
          <td><div class="row-actions">
            <button class="btn-icon" onclick="loadBlobs('${enc(c.name)}','${eSub}')">Browse ›</button>
          </div></td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

async function loadBlobs(eContainer, eSub) {
  clearSearch();
  currentSAContainer      = decodeURIComponent(eContainer);
  currentSAContainerECont = eContainer;
  currentSAContainerSub   = eSub;
  storageDrilldown        = 'blobs';
  updateStorageBreadcrumb();

  const content = document.getElementById('storage-content');
  content.innerHTML = '<div style="color:var(--muted);padding:20px 0">Loading blobs…</div>';

  const url = `/api/storage/${enc(currentSAAccount.name)}/blobs?container=${eContainer}&subscription=${eSub}`;
  const data = await apiFetch(url);

  if (data.error) {
    content.innerHTML = `<div class="error-box">&#9888; ${data.error}</div>`; return;
  }
  lastBlobsData = data.data || [];

  const q = document.getElementById('search-input').value.trim().toLowerCase();
  const visible = q ? lastBlobsData.filter(b => (b.name || '').toLowerCase().includes(q))
                    : lastBlobsData;
  renderBlobTable(visible, eContainer, eSub);
  document.getElementById('status-text').textContent =
    `${visible.length} of ${lastBlobsData.length} blob(s)`;
}

function renderBlobTable(blobs, eContainer, eSub) {
  const content = document.getElementById('storage-content');
  document.getElementById('status-text').textContent = `${blobs.length} blob(s)`;

  const uploadBar = `
    <div class="upload-bar">
      <label class="file-pick">
        &#8593; Upload File
        <input type="file" style="display:none" onchange="handleBlobUpload(event,'${eContainer}','${eSub}')"/>
      </label>
      <span id="upload-status"></span>
    </div>`;

  if (!blobs.length) {
    content.innerHTML = uploadBar + '<div class="empty" style="padding:30px 0">No blobs in this container.</div>';
    return;
  }

  content.innerHTML = uploadBar + `
    <table class="data-table">
      <thead><tr><th>Name</th><th>Size</th><th>Last Modified</th><th>Content Type</th><th></th></tr></thead>
      <tbody>${blobs.map(b => {
        const name = b.name || '—';
        const size = fmtBytes(b.properties?.contentLength);
        const mod  = fmtDate(b.properties?.lastModified);
        const ct   = b.properties?.contentType || '—';
        const eName = enc(name);
        return `<tr id="blob-row-${eName}">
          <td class="mono">${name}</td>
          <td>${size}</td>
          <td>${mod}</td>
          <td>${ct}</td>
          <td><div class="row-actions">
            <button class="btn-icon" onclick="downloadBlob('${eName}','${eContainer}','${eSub}')">&#8595; Download</button>
            <button class="btn-icon danger" onclick="confirmBlobDelete('${eName}','${eContainer}','${eSub}')">&#10005;</button>
          </div></td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>`;
}

function downloadBlob(eName, eContainer, eSub) {
  const url = `/api/storage/${enc(currentSAAccount.name)}/blob/download?container=${eContainer}&name=${eName}&subscription=${eSub}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = decodeURIComponent(eName);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function confirmBlobDelete(eName, eContainer, eSub) {
  const row = document.getElementById(`blob-row-${eName}`);
  if (!row) return;
  const actionsCell = row.querySelector('.row-actions');
  if (!actionsCell) return;
  actionsCell.style.opacity = '1';
  actionsCell.innerHTML = `
    <span style="font-size:11px;color:var(--red);white-space:nowrap">Delete?</span>
    <button class="btn-icon danger" onclick="executeBlobDelete('${eName}','${eContainer}','${eSub}')">Yes</button>
    <button class="btn-icon" onclick="loadBlobs('${eContainer}','${eSub}')">No</button>`;
}

async function executeBlobDelete(eName, eContainer, eSub) {
  const row = document.getElementById(`blob-row-${eName}`);
  if (row) row.style.opacity = '.4';
  const url = `/api/storage/${enc(currentSAAccount.name)}/blob?container=${eContainer}&name=${eName}&subscription=${eSub}`;
  try {
    const res  = await fetch(url, { method: 'DELETE' });
    const data = await res.json();
    if (data.error) {
      if (row) { row.style.opacity = ''; row.querySelector('.row-actions').innerHTML = `<span style="color:var(--red);font-size:11px">${data.error}</span>`; }
      return;
    }
    await loadBlobs(eContainer, eSub);
  } catch (e) {
    if (row) { row.style.opacity = ''; row.querySelector('.row-actions').innerHTML = `<span style="color:var(--red);font-size:11px">${e.message}</span>`; }
  }
}

async function handleBlobUpload(event, eContainer, eSub) {
  const file = event.target.files[0];
  if (!file) return;
  const statusEl = document.getElementById('upload-status');
  statusEl.innerHTML = `<span class="spin">&#8635;</span> Uploading ${file.name}…`;
  const url = `/api/storage/${enc(currentSAAccount.name)}/blobs?container=${eContainer}&name=${enc(file.name)}&subscription=${eSub}`;
  try {
    const res  = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file });
    const data = await res.json();
    if (data.error) { statusEl.innerHTML = `<span style="color:var(--red)">${data.error}</span>`; return; }
    statusEl.innerHTML = `<span style="color:var(--green)">&#10003; Uploaded ${file.name}</span>`;
    setTimeout(() => { statusEl.innerHTML = ''; }, 3000);
    await loadBlobs(eContainer, eSub);
  } catch (e) {
    statusEl.innerHTML = `<span style="color:var(--red)">${e.message}</span>`;
  }
  event.target.value = '';
}

// ── Storage: format helpers ──
function fmtBytes(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes === 0) return '0 B';
  const k = 1024, sizes = ['B','KB','MB','GB','TB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
function fmtDate(d) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString(undefined, {dateStyle:'short',timeStyle:'short'}); }
  catch { return d; }
}

// ── Modal helpers ──
function openModal(title) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = '<div style="color:var(--muted);padding:20px 0">Loading details…</div>';
  document.getElementById('overlay').classList.remove('hidden');
}
function closeModal(e) {
  if (!e || e.target === document.getElementById('overlay'))
    document.getElementById('overlay').classList.add('hidden');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── HTML helpers ──
function enc(s) { return encodeURIComponent(s || ''); }
function htmlEsc(s) { return (s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function kv(pairs) {
  return '<div class="detail-grid">' +
    pairs.map(([k, v]) => `<span class="k">${k}</span><span class="v">${v}</span>`).join('') +
    '</div>';
}
function section(title, content) {
  return `<div class="detail-section"><h3>${title}</h3>${content}</div>`;
}

// ── Boot ──
(async () => {
  await Promise.all([loadSubscriptions(), loadResourceGroups()]);
  refresh();
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def q(key):
            return qs.get(key, [None])[0]

        if path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/subscriptions":
            data, err = get_subscriptions()
            self.send_json({"error": err} if err else {"data": data})

        elif path == "/api/resource-groups":
            data, err = get_resource_groups(q("subscription"))
            self.send_json({"error": err} if err else {"data": data})

        elif path == "/api/container-apps":
            data, err = get_container_apps(q("subscription"), q("resource_group"))
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/container-apps/"):
            name = unquote(path[len("/api/container-apps/"):])
            rg   = unquote(q("resource_group") or "")
            sub  = q("subscription")
            detail, err = get_container_app_detail(name, rg, sub)
            if err:
                self.send_json({"error": err}); return
            replicas, _ = get_container_app_replicas(name, rg, sub)
            self.send_json({"data": detail, "replicas": replicas})

        elif path == "/api/vms":
            data, err = get_vms(q("subscription"), q("resource_group"))
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/vms/") and path.endswith("/nsg"):
            # GET /api/vms/{name}/nsg — return NSG(s) attached to this VM's NICs
            name = unquote(path[len("/api/vms/"):-len("/nsg")])
            rg   = unquote(q("resource_group") or "")
            sub  = q("subscription")
            vm, err = get_vm_detail(name, rg, sub)
            if err:
                self.send_json({"error": err}); return
            nic_ids = [n["id"] for n in (vm.get("networkProfile") or {}).get("networkInterfaces", [])]
            nsgs = []
            for nic_id in nic_ids:
                nic_name = nic_id.split("/")[-1]
                # resource group for NIC may differ; extract from id
                parts = nic_id.split("/")
                try:
                    nic_rg = parts[parts.index("resourceGroups") + 1]
                except (ValueError, IndexError):
                    nic_rg = rg
                nic, nerr = get_nic(nic_name, nic_rg, sub)
                if nerr or not nic:
                    continue
                nsg_ref = (nic.get("networkSecurityGroup") or {})
                if not nsg_ref.get("id"):
                    continue
                nsg_id = nsg_ref["id"]
                nsg_parts = nsg_id.split("/")
                try:
                    nsg_name = nsg_parts[-1]
                    nsg_rg   = nsg_parts[nsg_parts.index("resourceGroups") + 1]
                except (ValueError, IndexError):
                    continue
                rules, _ = get_nsg_rules(nsg_name, nsg_rg, sub)
                nsgs.append({"name": nsg_name, "resourceGroup": nsg_rg, "id": nsg_id, "rules": rules})
            self.send_json({"data": nsgs})

        elif path.startswith("/api/vms/"):
            name = unquote(path[len("/api/vms/"):])
            rg   = unquote(q("resource_group") or "")
            sub  = q("subscription")
            detail, err = get_vm_detail(name, rg, sub)
            self.send_json({"error": err} if err else {"data": detail})

        elif path.startswith("/api/nsg/") and path.endswith("/rules"):
            nsg_name = unquote(path[len("/api/nsg/"):-len("/rules")])
            rg  = unquote(q("resource_group") or "")
            sub = q("subscription")
            data, err = get_nsg_rules(nsg_name, rg, sub)
            self.send_json({"error": err} if err else {"data": data})

        elif path == "/api/apim":
            data, err = get_apim_services(q("subscription"), q("resource_group"))
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/apim/") and "/apis/" in path and path.endswith("/policy"):
            # /api/apim/{service}/apis/{api_id}/policy
            rest     = path[len("/api/apim/"):-len("/policy")]
            svc, api_id = rest.split("/apis/", 1)
            svc    = unquote(svc); api_id = unquote(api_id)
            rg     = unquote(q("resource_group") or "")
            sub    = q("subscription")
            data, err = get_apim_api_policy(svc, rg, api_id, sub)
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/apim/") and "/apis/" in path and path.endswith("/operations"):
            # /api/apim/{service}/apis/{api_id}/operations
            rest     = path[len("/api/apim/"):-len("/operations")]
            svc, api_id = rest.split("/apis/", 1)
            svc    = unquote(svc); api_id = unquote(api_id)
            rg     = unquote(q("resource_group") or "")
            sub    = q("subscription")
            data, err = get_apim_api_operations(svc, rg, api_id, sub)
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/apim/") and path.endswith("/apis"):
            svc = unquote(path[len("/api/apim/"):-len("/apis")])
            rg  = unquote(q("resource_group") or "")
            sub = q("subscription")
            data, err = get_apim_apis(svc, rg, sub)
            self.send_json({"error": err} if err else {"data": data})

        elif path == "/api/storage":
            data, err = get_storage_accounts(q("subscription"), q("resource_group"))
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/storage/") and path.endswith("/containers"):
            account = unquote(path[len("/api/storage/"):-len("/containers")])
            data, err = get_storage_containers(account, q("subscription"))
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/storage/") and path.endswith("/blobs"):
            account   = unquote(path[len("/api/storage/"):-len("/blobs")])
            container = unquote(q("container") or "")
            data, err = list_blobs(account, container, q("subscription"))
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/storage/") and path.endswith("/blob/download"):
            account   = unquote(path[len("/api/storage/"):-len("/blob/download")])
            container = unquote(q("container") or "")
            blob_name = unquote(q("name") or "")
            if not container or not blob_name:
                self.send_json({"error": "container and name are required"}, 400); return
            file_data, err = download_blob(account, container, blob_name, q("subscription"))
            if err:
                self.send_json({"error": err})
            else:
                ct, _ = mimetypes.guess_type(blob_name)
                ct = ct or "application/octet-stream"
                safe = blob_name.split("/")[-1]
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
                self.send_header("Content-Length", str(len(file_data)))
                self.end_headers()
                self.wfile.write(file_data)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def q(key):
            return qs.get(key, [None])[0]

        if path.startswith("/api/container-apps/") and path.endswith("/revisions"):
            name = unquote(path[len("/api/container-apps/"):-len("/revisions")])
            rg   = unquote(q("resource_group") or "")
            sub  = q("subscription")
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON body"}, 400); return
            image = (payload.get("image") or "").strip()
            if not image:
                self.send_json({"error": "image is required"}, 400); return
            data, err = create_revision(
                name, rg, image,
                cpu=payload.get("cpu"),
                memory=payload.get("memory"),
                min_replicas=payload.get("min_replicas"),
                max_replicas=payload.get("max_replicas"),
                revision_suffix=payload.get("revision_suffix"),
                subscription_id=sub,
            )
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/vms/") and path.endswith("/start"):
            name = unquote(path[len("/api/vms/"):-len("/start")])
            rg   = unquote(q("resource_group") or "")
            sub  = q("subscription")
            _, err = start_vm(name, rg, sub)
            self.send_json({"error": err} if err else {"ok": True})

        elif path.startswith("/api/nsg/") and path.endswith("/rules"):
            nsg_name = unquote(path[len("/api/nsg/"):-len("/rules")])
            rg  = unquote(q("resource_group") or "")
            sub = q("subscription")

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON body"}, 400)
                return

            rule_name = payload.get("name", "").strip()
            source_ip = payload.get("source_ip", "").strip()
            port      = payload.get("port", "").strip()
            protocol  = payload.get("protocol", "Tcp").strip()
            priority  = payload.get("priority", "1000")

            if not all([rule_name, source_ip, port]):
                self.send_json({"error": "name, source_ip, and port are required"}, 400)
                return

            data, err = add_nsg_rule(nsg_name, rg, rule_name, priority, source_ip, port, protocol, sub)
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/storage/") and path.endswith("/blobs"):
            account   = unquote(path[len("/api/storage/"):-len("/blobs")])
            container = unquote(q("container") or "")
            blob_name = unquote(q("name") or "")
            if not container or not blob_name:
                self.send_json({"error": "container and name are required"}, 400); return
            length = int(self.headers.get("Content-Length", 0))
            file_data = self.rfile.read(length)
            data, err = upload_blob(account, container, blob_name, file_data, q("subscription"))
            self.send_json({"error": err} if err else {"data": data})

        else:
            self.send_response(404)
            self.end_headers()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            return json.loads(body), None
        except json.JSONDecodeError:
            return None, "Invalid JSON body"

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def q(key):
            return qs.get(key, [None])[0]

        # PUT /api/nsg/{nsg}/rules/{rule_name}
        if path.startswith("/api/nsg/") and "/rules/" in path:
            parts    = path[len("/api/nsg/"):].split("/rules/", 1)
            nsg_name = unquote(parts[0])
            rule_name = unquote(parts[1])
            rg  = unquote(q("resource_group") or "")
            sub = q("subscription")

            payload, err = self._read_json_body()
            if err:
                self.send_json({"error": err}, 400); return

            source_ip = payload.get("source_ip", "").strip()
            port      = payload.get("port", "").strip()
            protocol  = payload.get("protocol", "Tcp").strip()
            priority  = payload.get("priority", "1000")

            if not all([source_ip, port]):
                self.send_json({"error": "source_ip and port are required"}, 400); return

            data, err = update_nsg_rule(nsg_name, rg, rule_name, priority, source_ip, port, protocol, sub)
            self.send_json({"error": err} if err else {"data": data})
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def q(key):
            return qs.get(key, [None])[0]

        # DELETE /api/nsg/{nsg}/rules/{rule_name}
        if path.startswith("/api/nsg/") and "/rules/" in path:
            parts     = path[len("/api/nsg/"):].split("/rules/", 1)
            nsg_name  = unquote(parts[0])
            rule_name = unquote(parts[1])
            rg  = unquote(q("resource_group") or "")
            sub = q("subscription")

            data, err = delete_nsg_rule(nsg_name, rg, rule_name, sub)
            self.send_json({"error": err} if err else {"data": data})

        elif path.startswith("/api/storage/") and path.endswith("/blob"):
            account   = unquote(path[len("/api/storage/"):-len("/blob")])
            container = unquote(q("container") or "")
            blob_name = unquote(q("name") or "")
            if not container or not blob_name:
                self.send_json({"error": "container and name are required"}, 400); return
            data, err = delete_blob(account, container, blob_name, q("subscription"))
            self.send_json({"error": err} if err else {"data": data})

        else:
            self.send_response(404)
            self.end_headers()


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"\n  Azure Dashboard  —  http://localhost:{PORT}\n")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
