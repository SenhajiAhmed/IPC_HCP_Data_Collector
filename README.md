# Pipeline d'Extraction des Données IPC (HCP Maroc)

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
**Rôle :** Extraire les tableaux de données depuis les fichiers téléchargés.
**Fonctionnement :** Utilise les librairies `pdfplumber` et `pandas` pour parcourir les documents téléchargés dans `downloads/`. Le script identifie visuellement et extrait les tableaux contenant les chiffres de l'IPC, résout les problèmes de concaténation de colonnes, et fusionne l'ensemble des données dans un fichier Excel exploitable.

---

## Scripts Obsolètes / Outils de Diagnostic

Ces scripts ont été utilisés ponctuellement pour le débogage et la mise en place du pipeline. Ils n'ont plus besoin d'être exécutés.

### `check_pdfs.py`
**Rôle :** Outil de diagnostic binaire.
**Historique :** Avant la correction de `download_pdfs.py`, de nombreux fichiers PDF ne s'ouvraient pas. Ce script a été écrit pour inspecter la signature binaire (magic bytes) des fichiers téléchargés. Il a permis de découvrir que la majorité des "faux PDF" étaient en réalité des archives `ZIP/DOCX` ou de vieux `.doc`.

### `extract_html.py`
**Rôle :** Script de test initial.
**Historique :** Un simple script de brouillon utilisé au tout début du projet pour télécharger le code HTML brut d'un seul lien au hasard (`sample_report.html`) afin d'étudier la structure des balises HTML du site.
