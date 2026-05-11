import json
import re
import urllib.parse
import requests
import csv
import time
import unicodedata
from typing import Dict, Optional

class HCPRequestsScraper:
    def __init__(self):
        """
        Initialise le scraper de l'API Google Custom Search pour le HCP.
        """
        self.session = requests.Session()
        self.cx = "04ef8a898c9384bec"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        print("🚀 Démarrage du scraper HCP automatisé (Recherche + Nettoyage)...")
        
    def _remove_accents(self, input_str: str) -> str:
        """Supprime les accents pour faciliter la comparaison des URL (ex: Août -> aout)"""
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

    def _is_valid_report_url(self, url: str) -> bool:
        """
        Vérifie que l'URL n'est pas un faux lien (page de téléchargement générique, 
        ou rubrique d'actualité).
        """
        if "downloads/" in url:
            return False
        if "Actualite-" in url:
            return False
        # Les vrais articles finissent par _a[chiffres].html, les rubriques par _r[chiffres].html
        if url.endswith(".html") and "_r" in url.split("/")[-1]:
            return False
        return True

    def find_report_url(self, month: str, year: int) -> Optional[str]:
        """
        Recherche le rapport pour un mois et une année donnés et retourne l'URL correspondante.
        Filtre automatiquement les faux positifs.
        """
        # Nettoyage du mois (ex: "d'Octobre" -> "Octobre")
        mois_propre = month.replace("d'", "d ").split()[-1]
        mois_sans_accent = self._remove_accents(mois_propre).lower()
        
        # Requête courte et robuste
        search_query = f"Indice des prix à la consommation {mois_propre} {year}"
        print(f"[*] Recherche : \"{search_query}\"")
        encoded_query = urllib.parse.quote_plus(search_query)
        
        self.headers["Referer"] = f"https://www.hcp.ma/plugin/?q={encoded_query}"
        init_url = f"https://cse.google.com/cse.js?cx={self.cx}"
        
        try:
            init_response = self.session.get(init_url, headers=self.headers, timeout=10)
            token_match = re.search(r'"cse_token":\s*"([^"]+)"', init_response.text)
            version_match = re.search(r'"cselibVersion":\s*"([^"]+)"', init_response.text)
            
            if not token_match or not version_match:
                print("  [!] Impossible de récupérer le token CSE.")
                return None
                
            cse_tok = token_match.group(1)
            cselib_version = version_match.group(1)
            
            rurl = f"https://www.hcp.ma/plugin/?q={encoded_query}#gsc.tab=0&gsc.q={encoded_query}&gsc.page=1"
            api_url = (
                f"https://cse.google.com/cse/element/v1?rsz=filtered_cse&num=10&hl=fr&source=gcsc"
                f"&cselibv={cselib_version}&cx={self.cx}&q={encoded_query}&safe=off"
                f"&cse_tok={urllib.parse.quote_plus(cse_tok)}&callback=google.search.cse.api"
                f"&rurl={urllib.parse.quote_plus(rurl)}"
            )
            
            api_response = self.session.get(api_url, headers=self.headers, timeout=10)
            
            if api_response.status_code == 200:
                json_match = re.search(r'google\.search\.cse\.api\((.*)\);?', api_response.text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    results = data.get('results', [])
                    
                    for res in results:
                        title = res.get('titleNoFormatting', '').strip().lower()
                        url = res.get('unescapedUrl', '')
                        snippet = res.get('contentNoFormatting', '').lower()
                        
                        # Google tronque parfois les titres, on fouille l'URL et le snippet aussi
                        text_to_check = title + " " + url.lower() + " " + snippet
                        
                        # Conditions de validation : mots clés du rapport d'inflation HCP présents
                        if ("prix" in text_to_check and 
                            "consommation" in text_to_check and 
                            str(year) in text_to_check and 
                            (mois_propre.lower() in text_to_check or mois_sans_accent in text_to_check)):
                            
                            if self._is_valid_report_url(url):
                                print(f"  [+] Match valide trouvé : {url}")
                                return url
                            else:
                                print(f"  [-] Lien ignoré (Faux positif/rubrique) : {url}")
                            
                    print("  [-] Aucun résultat valide trouvé.")
                else:
                    print("  [!] Erreur de parsing de la réponse JSONP de l'API.")
            else:
                print(f"  [!] Erreur API Google (Code {api_response.status_code}).")
                
        except Exception as e:
            print(f"  [!] Exception rencontrée : {e}")
            
        return None

    def close(self):
        self.session.close()
        print("\n🛑 Session requests fermée.")

if __name__ == "__main__":
    months_grammar = [
        "de Janvier", "de Février", "de Mars", "d'Avril", 
        "de Mai", "de Juin", "de Juillet", "d'Août", 
        "de Septembre", "d'Octobre", "de Novembre", "de Décembre"
    ]
    
    scraper = HCPRequestsScraper()
    csv_filename = "hcp_ipc_reports_2010_2025.csv"
    
    total_queries = 0
    total_success = 0
    
    try:
        print("\n" + "="*60)
        print("🔍 DÉBUT DU SCRAPING DES RAPPORTS HCP (2010 - 2025)")
        print("="*60)
        
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Année", "Mois", "URL"])
            
            for year in range(2010, 2026):
                print(f"\n--- Année {year} ---")
                for month in months_grammar:
                    total_queries += 1
                    url_extracted = scraper.find_report_url(month, year)
                    
                    # Si aucune URL trouvée, on met "nan" selon votre préférence
                    final_value = url_extracted if url_extracted else "nan"
                    
                    writer.writerow([year, month, final_value])
                    if url_extracted:
                        total_success += 1
                    
                    # Pause pour préserver l'API
                    time.sleep(1)
                    
    finally:
        scraper.close()
        
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DE L'EXTRACTION")
    print("="*60)
    print(f"✅ Fichier sauvegardé sous : {csv_filename}")
    print(f"Total des requêtes : {total_queries}")
    print(f"URL extraites avec succès : {total_success}")
    print(f"Absents (inscrits 'nan') : {total_queries - total_success}")
    print("="*60 + "\n")
