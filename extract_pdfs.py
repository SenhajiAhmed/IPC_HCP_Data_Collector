import csv
import requests
from bs4 import BeautifulSoup
import os
from concurrent.futures import ThreadPoolExecutor

input_csv = 'hcp_ipc_reports_2010_2025.csv'
output_csv = 'hcp_ipc_pdfs.csv'

def fetch_url(row):
    url = row.get('URL', '')
    annee = row.get('Année', '')
    mois = row.get('Mois', '')
    
    if not url or url.lower() == 'nan':
        return []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    extracted = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Recherche des liens avec la classe "pj" ou à l'intérieur d'un div avec la classe "pj"
        links = soup.find_all('a', class_='pj')
        
        if not links:
            div_pj = soup.find('div', class_='pj')
            if div_pj:
                links = div_pj.find_all('a')
        
        for link in links:
            href = link.get('href')
            text = link.get_text(strip=True)
            if href:
                if href.startswith('/'):
                    href = 'https://www.hcp.ma' + href
                
                extracted.append({
                    'Année': annee,
                    'Mois': mois,
                    'Source_URL': url,
                    'PDF_Title': text,
                    'PDF_URL': href
                })
        print(f"Processed: {annee} {mois} - Found {len(extracted)} links")
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        
    return extracted

def extract_pdf_links():
    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found.")
        return

    rows = []
    with open(input_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    results = []
    print(f"Starting extraction for {len(rows)} reports using 10 threads...")
    
    # Utilisation de ThreadPoolExecutor pour accélérer les requêtes
    with ThreadPoolExecutor(max_workers=10) as executor:
        # map préserve l'ordre initial des lignes
        all_data = executor.map(fetch_url, rows)
        for data in all_data:
            if data:
                results.extend(data)
                
    if results:
        with open(output_csv, mode='w', encoding='utf-8', newline='') as out_f:
            fieldnames = ['Année', 'Mois', 'Source_URL', 'PDF_Title', 'PDF_URL']
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSuccessfully extracted {len(results)} PDF links to {output_csv}")
    else:
        print("\nNo PDF links found.")

if __name__ == '__main__':
    extract_pdf_links()
