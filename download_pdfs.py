import os
import csv
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

csv_file = 'hcp_ipc_pdfs.csv'
download_dir = 'downloads'

def is_fr(title):
    # Cherche "_fr", " fr ", "français" ou "francais" (insensible à la casse)
    return bool(re.search(r'(?i)(_fr\b|\bfr\b|français|francais)', title))

def is_ar(title):
    # Cherche "_ar", " ar " ou "arabe" (insensible à la casse)
    return bool(re.search(r'(?i)(_ar\b|\bar\b|arabe)', title))

def download_file(item):
    annee = item['Année']
    mois = item['Mois']
    title = item['PDF_Title']
    url = item['PDF_URL']
    
    # Création d'un nom de fichier sûr
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    safe_title = safe_title.strip()
    
    # Enlever toute extension du titre (on la détectera via le contenu)
    safe_title = re.sub(r'(?i)\.(pdf|docx?|zip)$', '', safe_title)
    base_filename = f"{annee}_{mois}_{safe_title}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=20)
        response.raise_for_status()
        
        iterator = response.iter_content(chunk_size=8192)
        try:
            first_chunk = next(iterator)
        except StopIteration:
            return
            
        # Détection de la vraie extension selon le "magic number"
        ext = ".pdf"
        if first_chunk.startswith(b'%PDF'):
            ext = ".pdf"
        elif first_chunk.startswith(b'PK\x03\x04'):
            ext = ".docx"
        elif first_chunk.startswith(b'\xd0\xcf\x11\xe0'):
            ext = ".doc"
        elif first_chunk.startswith(b'{\\rtf'):
            ext = ".rtf"
        elif b'<html' in first_chunk.lower() or b'<!doct' in first_chunk.lower() or b'<htm' in first_chunk.lower():
            print(f"Ignoré : {url} pointe vers une page HTML (probablement une erreur).")
            return
            
        filename = base_filename + ext
        filepath = os.path.join(download_dir, filename)
        
        if os.path.exists(filepath):
            print(f"Déjà téléchargé : {filename}")
            return
        
        # On sauvegarde le fichier
        with open(filepath, 'wb') as f:
            f.write(first_chunk)
            for chunk in iterator:
                f.write(chunk)
                
        print(f"Téléchargé : {filename}")
    except Exception as e:
        print(f"Échec du téléchargement {url} : {e}")

def main():
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    if not os.path.exists(csv_file):
        print(f"Erreur : le fichier {csv_file} est introuvable.")
        return
        
    # Grouper les entrées par (Année, Mois)
    groups = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['Année'], row['Mois'])
            if key not in groups:
                groups[key] = []
            groups[key].append(row)
            
    items_to_download = []
    
    # Pour chaque mois, on choisit la version FR, sinon AR, sinon ce qu'il y a
    for key, items in groups.items():
        fr_item = None
        ar_item = None
        other_item = None
        
        for item in items:
            title = item['PDF_Title']
            if is_fr(title):
                fr_item = item
            elif is_ar(title):
                ar_item = item
            else:
                other_item = item
                
        # Ordre de préférence : Français > Arabe > Autre
        if fr_item:
            items_to_download.append(fr_item)
        elif ar_item:
            items_to_download.append(ar_item)
        elif other_item:
            items_to_download.append(other_item)
            
    print(f"Sélection de {len(items_to_download)} fichiers à télécharger sur {len(groups)} mois uniques.")
    
    # Téléchargement en parallèle (5 workers pour ne pas surcharger le serveur)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(download_file, item) for item in items_to_download]
        for future in as_completed(futures):
            future.result()
            
    print("\nTéléchargement terminé !")

if __name__ == '__main__':
    main()
