# Pipeline IPC/HCP — Données 2010-2025

Pipeline automatisé pour collecter, télécharger et extraire les données de l'Indice des Prix à la Consommation (IPC) depuis le site du Haut Commissariat au Plan (HCP) du Maroc.

---

## Lancement en une seule commande

```bash
python3 pipeline.py                  # Lance toutes les étapes (saute celles déjà faites)
python3 pipeline.py --step 2 3 4     # Lance uniquement les étapes 2, 3 et 4
python3 pipeline.py --force          # Reforce toutes les étapes
```

---

## Architecture

```
data-ext/
├── pipeline.py          # 🚀 Point d'entrée unique
├── src/
│   ├── scraper.py       # Étape 1 : Scraping des URLs (Google Custom Search)
│   ├── extractor.py     # Étape 2 : Extraction des liens PDF/DOCX
│   ├── downloader.py    # Étape 3 : Téléchargement des fichiers
│   └── parser.py        # Étape 4 : Extraction des tableaux
├── downloads/           # Fichiers téléchargés (ignoré par git)
├── extracted_tables/    # Tableaux CSV extraits par année (ignoré par git)
├── hcp_ipc_reports_2010_2025.csv   # URLs des 186 rapports mensuels
└── hcp_ipc_pdfs.csv                # Liens directs vers les documents
```

---

## Les 4 Étapes du Pipeline

### Étape 1 — `HCPScraper`
Navigue sur le site du HCP via l'API Google Custom Search et récupère les URLs des articles mensuels de l'IPC pour 2010-2025. **Idempotence** : ne re-scrape que les mois dont l'URL est `nan`.

### Étape 2 — `PDFLinkExtractor`
Ouvre chaque page d'article et extrait les liens directs vers les documents joints (`<div class="pj">`). **Idempotence** : ne traite que les pages pas encore dans `hcp_ipc_pdfs.csv`.

### Étape 3 — `Downloader`
Télécharge les documents en priorité en version française (sinon arabe). Détecte automatiquement le vrai format (PDF, DOCX, DOC, RTF) via les magic bytes pour corriger les extensions. **Idempotence** : ne télécharge que les fichiers absents dans `downloads/`.

### Étape 4 — `TableParser`
Extrait les tableaux de données depuis tous les formats de fichiers (PDF, DOCX, DOC, RTF). Convertit les anciens formats via LibreOffice. Organise les résultats par année dans `extracted_tables/`. **Idempotence** : ne traite que les fichiers sans CSV de sortie existant.

---

## Comportement en cas d'erreur

- Si une étape échoue partiellement, **seule la partie manquante est rejouée** au prochain lancement.
- Si une étape critique échoue complètement, le pipeline s'arrête et affiche un rapport.
- Chaque lancement se termine par un **résumé visuel** de l'état de chaque étape.


Ce dépôt contient l'ensemble des scripts permettant de récupérer, télécharger et extraire les données de l'Indice des Prix à la Consommation (IPC) depuis le site du Haut Commissariat au Plan (HCP) du Maroc, pour la période 2010-2025.

Le processus est divisé en plusieurs étapes séquentielles.

---

## Scripts Principaux (Le Pipeline)

Ces scripts forment le flux de travail actif pour obtenir vos données finales. Ils doivent être exécutés dans cet ordre :

### 1. `scraper.py`
**Rôle :** Récupérer la liste des articles mensuels.
**Fonctionnement :** Ce script navigue sur le site du HCP et contourne les restrictions du moteur de recherche (Google Custom Search) en utilisant `selenium-wire`. Il récupère les URL de tous les articles mensuels concernant l'IPC (ex: "L'indice des prix à la consommation du mois de Janvier 2010") et les exporte dans le fichier `hcp_ipc_reports_2010_2025.csv`.

### 2. `extract_pdfs.py`
**Rôle :** Extraire les liens directs vers les documents (Pièces jointes).
**Fonctionnement :** Ce script lit le fichier `hcp_ipc_reports_2010_2025.csv`. Pour chaque URL d'article, il télécharge le code HTML, recherche la section des pièces jointes (`<div class="pj">`), et extrait les liens directs vers les documents (versions française et arabe). Le résultat est sauvegardé dans `hcp_ipc_pdfs.csv`.

### 3. `download_pdfs.py`
**Rôle :** Télécharger intelligemment les documents sur votre machine.
**Fonctionnement :** Ce script parcourt `hcp_ipc_pdfs.csv` et télécharge les documents dans le dossier `downloads/`.
- **Filtre de langue :** Il télécharge en priorité la version française. Si absente, il prend la version arabe.
- **Correction magique des formats :** Le site du HCP possède de nombreux anciens fichiers Word (`.doc`, `.docx` ou `.rtf`) masqués sous une fausse extension `.pdf`. Ce script analyse les premiers octets (le *magic number*) de chaque fichier téléchargé à la volée et lui attribue **la vraie extension correcte** (`.pdf`, `.docx`, `.doc` ou `.rtf`) pour éviter tout fichier corrompu.

### 4. `extract.py`
**Rôle :** Extraire les tableaux de données depuis tous les types de fichiers téléchargés.
**Fonctionnement :** Ce script traite les fichiers **PDF, DOC, DOCX et RTF**. Il utilise `pdfplumber` pour les PDF et `python-docx` pour les documents Word (après conversion automatique via LibreOffice si nécessaire). Il identifie les tableaux, les nettoie, et les sauvegarde sous forme de fichiers CSV organisés par année dans le dossier `extracted_tables/`.

---

## Scripts Obsolètes / Outils de Diagnostic

Ces scripts ont été utilisés ponctuellement pour le débogage et la mise en place du pipeline. Ils n'ont plus besoin d'être exécutés.

### `check_pdfs.py`
**Rôle :** Outil de diagnostic binaire.
**Historique :** Avant la correction de `download_pdfs.py`, de nombreux fichiers PDF ne s'ouvraient pas. Ce script a été écrit pour inspecter la signature binaire (magic bytes) des fichiers téléchargés. Il a permis de découvrir que la majorité des "faux PDF" étaient en réalité des archives `ZIP/DOCX` ou de vieux `.doc`.

### `extract_html.py`
**Rôle :** Script de test initial.
**Historique :** Un simple script de brouillon utilisé au tout début du projet pour télécharger le code HTML brut d'un seul lien au hasard (`sample_report.html`) afin d'étudier la structure des balises HTML du site.
