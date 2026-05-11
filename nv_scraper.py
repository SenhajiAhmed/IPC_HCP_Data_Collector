import os
import json
import time
import re
from seleniumwire import webdriver
from seleniumwire.utils import decode

def collect_responses(url: str):
    """
    Exemple minimal utilisant selenium-wire pour collecter les requêtes 
    et extraire leurs réponses sous forme de JSON dans un nouveau dossier.
    """
    # Configuration de Chrome en mode headless
    options = webdriver.ChromeOptions()
    options.add_argument('--window-size=1920,1080')
    
    print("🚀 Démarrage du navigateur Chrome avec Selenium-Wire...")
    driver = webdriver.Chrome(options=options)
    
    # Création du nouveau dossier
    output_dir = "extracted_responses"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        print(f"\n[*] Navigation vers : {url}")
        driver.get(url)
        
        # Pause pour laisser le temps aux requêtes asynchrones de s'effectuer
        time.sleep(5)
        
        print("\n" + "="*50)
        print(f"🔍 EXTRACTION DES RÉPONSES VERS LE DOSSIER '{output_dir}'")
        print("="*50)
        
        # Parcours de toutes les requêtes interceptées
        for i, request in enumerate(driver.requests):
            if request.response:
                content_type = request.response.headers.get('Content-Type', '')
                
                req_data = {
                    "url": request.url,
                    "method": request.method,
                    "status_code": request.response.status_code,
                    "content_type": content_type,
                    "headers": dict(request.response.headers),
                    "body": None
                }
                
                try:
                    # Décodage du corps de la réponse
                    body = decode(request.response.body, request.response.headers.get('Content-Encoding', 'identity'))
                    body_text = body.decode('utf-8', errors='ignore')
                    
                    # Traitement spécifique pour JSON et JSONP (comme Google Custom Search)
                    if 'application/json' in content_type or 'javascript' in content_type:
                        # On essaie d'extraire la structure JSON pure s'il s'agit de JSONP
                        match = re.search(r'(\{.*\})', body_text, re.DOTALL)
                        if match:
                            try:
                                req_data['body'] = json.loads(match.group(1))
                            except json.JSONDecodeError:
                                req_data['body'] = body_text
                        else:
                            req_data['body'] = body_text
                    else:
                        # Pour le HTML/CSS/Images, on stocke juste un extrait ou un message
                        req_data['body'] = body_text[:500] + " ... [TRONQUÉ]" if len(body_text) > 500 else body_text
                
                except Exception as e:
                    req_data['body'] = f"Erreur de décodage : {str(e)}"
                
                # Sauvegarde au format JSON dans le nouveau dossier
                file_path = os.path.join(output_dir, f"response_{i:03d}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(req_data, f, indent=4, ensure_ascii=False)
                    
                print(f"[+] Sauvegardé : {file_path} (Type: {content_type.split(';')[0]})")
                
    finally:
        driver.quit()
        print(f"\n🛑 Extraction terminée. Les fichiers sont dans le dossier '{output_dir}'.")

if __name__ == "__main__":
    # 1 seul lien HCP pour exemple (Janvier 2013)
    query = "L'Indice des prix à la consommation (IPC) du mois de Janvier 2013"
    target_url = f"https://www.hcp.ma/plugin/?q={query}#gsc.tab=0&gsc.q={query}&gsc.page=1"
    
    collect_responses(target_url)
