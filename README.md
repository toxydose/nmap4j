# nmap4j

nmap4j is a lightweight vibe-coded ingestor that parses Nmap XML scan output and loads host, port, service, and script results into Neo4j as a graph database.

## 🚀 What it does

- Reads Nmap XML output (from `nmap -oX ...`)
- Parses targets, host addresses, ports, services.
- Stores each entity (hosts, ports, services, scripts) as nodes
- Connects nodes with relationships (e.g., `(:Host)-[:HAS_PORT]->(:Port)`)
- Supports bulk ingestion for large scan files

## ✅ Why use nmap4j

- Makes Nmap results queryable with Cypher
- Enables attack surface analysis, network mapping, and alerting in Neo4j
- Keeps topology and service relationships in a graph model

## To-Do features
- Implement parsing of nmap NSE results
- Own client module with web dashboard
- Ai-powered query building (local LLM)

## 🧭 Quick Start

### 1) Prepare Nmap XML

Run Nmap with XML output:

```bash
nmap -sV -oX scan.xml 10.0.0.0/24
```

### 2) Configure Neo4j

Start Neo4j and note the connection details in config file (URI, username, password). Example:

- URI: `bolt://localhost:7687`
- Username: `neo4j`
- Password: `password`

### 3) Ingest with nmap4j

Use the nmap4j command or script (adjust to your project’s entrypoint):

```bash
python ingest.py scan.xml
```
When ingesting data the tool assumes you were scanning /24 networks. 
If you were scanning networks with different masks you can specify the target networks file as a second argument in a script

```bash
python ingest.py scan.xml target_networks.txt
```
