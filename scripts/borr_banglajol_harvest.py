#!/usr/bin/env python3
"""Resumable BanglaJOL OAI-PMH metadata harvester.

Stores metadata as JSONL and uses SQLite state for deduplication and token tracking.
"""
import os
import json
import gzip
import sqlite3
import time
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import requests

OAI_URL = "https://www.banglajol.info/index.php/index/oai"
STATE_DB = "state/borr_banglajol_state.sqlite"
OUTPUT_FILE = "data/borr_banglajol_harvested.jsonl.gz"

NS = {
    'oai': 'http://www.openarchives.org/OAI/2.0/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/'
}

def init_db():
    os.makedirs(os.path.dirname(STATE_DB), exist_ok=True)
    conn = sqlite3.connect(STATE_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS harvested_records (
                    identifier TEXT PRIMARY KEY,
                    harvested_at TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                 )''')
    conn.commit()
    return conn

def sanitize_xml(xml_bytes):
    text = xml_bytes.decode('utf-8', errors='replace')
    # Remove invalid XML control characters
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    return text

def harvest_records():
    conn = init_db()
    c = conn.cursor()
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    c.execute("SELECT value FROM state WHERE key='resumption_token'")
    row = c.fetchone()
    resumption_token = row[0] if row else None
    
    total_harvested = 0
    
    with gzip.open(OUTPUT_FILE, 'at', encoding='utf-8') as f:
        while True:
            params = {'verb': 'ListRecords'}
            if resumption_token:
                params['resumptionToken'] = resumption_token
            else:
                params['metadataPrefix'] = 'oai_dc'
                
            print(f"Fetching OAI-PMH: {params}")
            resp = requests.get(OAI_URL, params=params)
            resp.raise_for_status()
            
            clean_xml = sanitize_xml(resp.content)
            try:
                root = ET.fromstring(clean_xml)
            except ET.ParseError as e:
                print(f"Parse error skipping page: {e}")
                break
            
            error = root.find('oai:error', NS)
            if error is not None:
                print(f"OAI Error: {error.text}")
                break
                
            records = root.findall('.//oai:record', NS)
            if not records:
                break
                
            for record in records:
                header = record.find('oai:header', NS)
                if header is None:
                    continue
                    
                identifier_elem = header.find('oai:identifier', NS)
                if identifier_elem is None:
                    continue
                identifier = identifier_elem.text
                
                c.execute('SELECT 1 FROM harvested_records WHERE identifier = ?', (identifier,))
                if c.fetchone():
                    continue
                    
                metadata = record.find('oai:metadata', NS)
                if metadata is None:
                    continue
                    
                dc = metadata.find('oai_dc:dc', NS)
                if dc is None:
                    continue
                
                title = dc.find('dc:title', NS)
                title = title.text if title is not None else ""
                
                authors = [creator.text for creator in dc.findall('dc:creator', NS) if creator.text]
                date_elem = dc.find('dc:date', NS)
                pub_date = date_elem.text if date_elem is not None else ""
                
                desc = dc.find('dc:description', NS)
                abstract = desc.text if desc is not None else ""
                
                source = dc.find('dc:source', NS)
                journal = source.text if source is not None else ""
                
                identifiers = [ident.text for ident in dc.findall('dc:identifier', NS) if ident.text]
                doi = next((i for i in identifiers if i and i.startswith('10.')), None)
                url = next((i for i in identifiers if i and i.startswith('http')), None)
                
                borr_record = {
                    "id": f"banglajol:{identifier}",
                    "doi": f"https://doi.org/{doi}" if doi else None,
                    "title": title,
                    "publication_year": int(pub_date[:4]) if pub_date and len(pub_date) >= 4 and pub_date[:4].isdigit() else None,
                    "publication_date": pub_date,
                    "type": "Journal Article",
                    "authorships": [{"author": {"display_name": a}} for a in authors],
                    "primary_location": {"source": {"display_name": journal}, "landing_page_url": url},
                    "abstract": abstract,
                    "harvested_at": datetime.now(timezone.utc).isoformat()
                }
                
                f.write(json.dumps(borr_record) + "\n")
                
                c.execute('INSERT INTO harvested_records (identifier, harvested_at) VALUES (?, ?)', 
                          (identifier, borr_record['harvested_at']))
                total_harvested += 1
                
            token_elem = root.find('.//oai:resumptionToken', NS)
            if token_elem is not None and token_elem.text:
                resumption_token = token_elem.text
                c.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('resumption_token', ?)", (resumption_token,))
                conn.commit()
                print(f"Harvested {total_harvested} total new records... Saved token.")
                time.sleep(1)
            else:
                c.execute("DELETE FROM state WHERE key='resumption_token'")
                conn.commit()
                print(f"Harvested {total_harvested} total new records... Reached end.")
                break
                
    print(f"Done. Harvested {total_harvested} new records from BanglaJOL.")
    conn.close()

if __name__ == "__main__":
    harvest_records()
