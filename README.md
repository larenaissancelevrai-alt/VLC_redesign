# VLC Redesign — version réparée

Lecteur multimédia de bureau Python / PySide6 / libVLC.

## Démarrage sous Windows

1. Installez Python 3.10 ou plus récent (Python 3.14 peut être moins compatible avec certaines dépendances).
2. Installez VLC Media Player 64 bits depuis https://www.videolan.org/vlc/ si Python est en 64 bits.
3. Ouvrez PowerShell dans ce dossier et lancez :

   ```powershell
   python -m pip install -r requirements.txt
   python main.py
   ```

   Ou double-cliquez sur `Lancer_VLC_Redesign.bat`.

## Notes

Cette archive regroupe la version récente du projet et rétablit les modules Python manquants (`asyncwork.py`, `config.py`, `miniplayer.py`, `panels.py`, `wizard.py`). Certaines vues annexes ont été reconstruites à partir des interfaces utilisées par `main.py`; elles sont donc fonctionnelles de base, mais peuvent ne pas reproduire exactement les composants originaux absents de l'archive source.

## Créer le .exe et publier des mises à jour

- **En local (Windows)** : double-cliquez sur `build.bat` → `dist\VLC Redesign\VLC Redesign.exe` (+ `Output\VLC_Redesign_Setup.exe` si Inno Setup est installé).
- **Automatique (recommandé)** : mettez le projet sur GitHub, renseignez `GITHUB_REPO` dans `version.py`, puis :

  ```
  git tag v1.0.1
  git push origin v1.0.1
  ```
  GitHub compile l'installateur et crée la release. Les applications installées proposent la mise à jour au prochain lancement (Paramètres → Mises à jour).
- VLC Media Player (64 bits) doit être installé sur le PC de l'utilisateur.
- Les réglages restent dans le dossier utilisateur : ils sont conservés à chaque mise à jour.
