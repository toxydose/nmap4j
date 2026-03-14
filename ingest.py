from neo4j import GraphDatabase
from lxml import etree
import sys
import ipaddress
import os
from datetime import datetime
from config import *

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def derive_network(ip_str, networks_list=None):
    ip_obj = ipaddress.ip_address(ip_str)

    if networks_list:
        for net in networks_list:
            if ip_obj in net:
                return str(net)

    return str(ipaddress.ip_network(f"{ip_str}/24", strict=False))


def load_networks_file(path):
    networks = []

    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    networks.append(ipaddress.ip_network(line, strict=False))

    return networks


def ingest(xml_file, networks_file=None):

    scan_date = datetime.utcnow().isoformat()
    networks_list = load_networks_file(networks_file)

    context = etree.iterparse(xml_file, events=("end",), tag="host")

    with driver.session() as session:

        # Create Scan node
        session.run(
            """
            MERGE (scan:Scan {date:$scan_date})
            """,
            scan_date=scan_date,
        )

        for event, host_elem in context:

            ip_elem = host_elem.find("address[@addrtype='ipv4']")
            if ip_elem is None:
                host_elem.clear()
                continue

            ip = ip_elem.get("addr")

            hostname_elem = host_elem.find("hostnames/hostname")
            hostname = hostname_elem.get("name") if hostname_elem is not None else None

            ports_elem = host_elem.find("ports")
            if ports_elem is None:
                host_elem.clear()
                continue

            # collect only open ports
            open_ports = []
            for p in ports_elem.findall("port"):
                state_elem = p.find("state")
                if state_elem is not None and state_elem.get("state") == "open":
                    open_ports.append(p)

            # skip hosts without open ports
            if not open_ports:
                host_elem.clear()
                continue

            net_cidr = derive_network(ip, networks_list)
            # create network + IP
            session.run(
                """
                MERGE (scan:Scan {date:$scan_date})

                MERGE (n:Network {cidr:$cidr})
                ON CREATE SET n.name=$cidr

                MERGE (ipnode:IPAddress {address:$ip})
                ON CREATE SET ipnode.first_seen=$scan_date

                SET ipnode.last_seen=$scan_date,
                    ipnode.hostname=$hostname

                MERGE (n)-[:CONTAINS]->(ipnode)

                MERGE (ipnode)-[:FOUND_IN_SCAN]->(scan)
                """,
                scan_date=scan_date,
                cidr=net_cidr,
                ip=ip,
                hostname=hostname,
            )

            seen_ports = set()

            for port_elem in open_ports:

                state_elem = port_elem.find("state")
                port_state = state_elem.get("state")

                port_num = int(port_elem.get("portid"))
                proto = port_elem.get("protocol")

                port_id = f"{ip}_{port_num}_{proto}"
                port_name = f"{port_num}/{proto}"

                seen_ports.add(port_id)

                # merge port
                session.run(
                    """
                    MERGE (scan:Scan {date:$scan_date})

                    MERGE (p:Port {internal_id:$pid})
                    ON CREATE SET p.first_seen=$scan_date

                    SET p.last_seen=$scan_date,
                        p.state=$state,
                        p.port=$port,
                        p.protocol=$proto,
                        p.name=$name

                    MERGE (ipnode:IPAddress {address:$ip})

                    MERGE (ipnode)-[:HAS_PORT]->(p)

                    MERGE (p)-[:FOUND_IN_SCAN]->(scan)
                    """,
                    scan_date=scan_date,
                    pid=port_id,
                    state=port_state,
                    port=port_num,
                    proto=proto,
                    name=port_name,
                    ip=ip,
                )

                svc_elem = port_elem.find("service")

                if svc_elem is not None and svc_elem.get("name"):

                    svc_name = svc_elem.get("name")
                    service_id = port_id

                    session.run(
                        """
                        MERGE (scan:Scan {date:$scan_date})

                        MERGE (s:Service {internal_id:$sid})
                        ON CREATE SET s.first_seen=$scan_date

                        SET s.last_seen=$scan_date,
                            s.name=$name,
                            s.product=$product,
                            s.version=$version

                        MERGE (p:Port {internal_id:$pid})

                        MERGE (p)-[:RUNS_SERVICE]->(s)

                        MERGE (s)-[:FOUND_IN_SCAN]->(scan)
                        """,
                        scan_date=scan_date,
                        sid=service_id,
                        pid=port_id,
                        name=svc_name,
                        product=svc_elem.get("product"),
                        version=svc_elem.get("version"),
                    )

            # mark previously seen ports closed if missing
            if seen_ports:
                session.run(
                    """
                    MATCH (ipnode:IPAddress {address:$ip})-[:HAS_PORT]->(p:Port)
                    WHERE NOT p.internal_id IN $seen_ports
                    SET p.state='closed'
                    """,
                    ip=ip,
                    seen_ports=list(seen_ports),
                )

            host_elem.clear()


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python ingest.py scan.xml [networks.txt]")
        sys.exit(1)

    xml_file = sys.argv[1]
    networks_file = sys.argv[2] if len(sys.argv) > 2 else None

    ingest(xml_file, networks_file)

    print("✔ Ingestion complete")
