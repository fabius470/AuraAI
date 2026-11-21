# AURA // CORE — Guida completa al download, setup e comandi VS Code

> **Modello AI predefinito:** `qwen2.5:3b` (compatibile anche con altri modelli locali scaricabili tramite Ollama, come `llama3.2`).

Guida passo passo per scaricare **AuraAI** da GitHub, installare **Visual Studio Code**, **Python** e **Ollama**, scaricare il modello AI in locale e lanciare tutti i comandi necessari direttamente dal terminale di VS Code su `http://127.0.0.1:5000`.

---

## 1. Scaricare il progetto da GitHub (ZIP)

1. Vai sulla pagina GitHub ufficiale di **AuraAI**:
   ```text
   [https://github.com/TUO-USERNAME/TUO-REPO](https://github.com/TUO-USERNAME/TUO-REPO)
   ```
   *(Sostituisci con l'URL effettivo del repository non appena disponibile)*
2. Clicca sul pulsante verde **`<> Code`** in alto a destra e seleziona **`Download ZIP`**.
3. Estrai lo `.zip` in una cartella comoda sul tuo PC (ad esempio `C:\Users\TuoNome\Documents\auraai`).

---

## 2. Installare Visual Studio Code, Python e Ollama

1. **Visual Studio Code:** scaricalo da [https://code.visualstudio.com/](https://code.visualstudio.com/) e installalo. Apri poi la cartella estratta del progetto con **File → Apri cartella...**.
2. **Python:** scaricalo da [https://www.python.org/downloads/](https://www.python.org/downloads/) (consigliata una versione recente, es. Python 3.10+). Su Windows spunta **"Add python.exe to PATH"** durante l'installazione.
3. **Ollama:** scaricalo da [https://ollama.com/](https://ollama.com/) e installalo. Lascialo attivo in background in ascolto su `http://127.0.0.1:11434`.

---

## 3. Aprire il terminale in VS Code

Dentro **Visual Studio Code**, apri il terminale integrato:
- Scorciatoia rapida: premi **`Ctrl + ù`** (oppure **`Ctrl + shift + P`** → digita *Terminal: Create New Terminal*).
- Oppure dal menu in alto: **Terminale → Nuovo terminale**.

Controlla che il terminale si trovi già nella cartella del progetto (ad esempio `.../auraai`). Se non ci sei dentro, spostati con:

```powershell
cd C:\percorso\della\cartella\auraai
```

---

## 4. Comandi da eseguire nel terminale di VS Code

### A. Verificare Python e Ollama
Controlla che entrambi rispondano correttamente:

```powershell
python --version
ollama --version
```

### B. Scaricare (pullare) il modello AI (`qwen2.5:3b`)
Con Ollama attivo, scarica il modello predefinito del progetto:

```powershell
ollama pull qwen2.5:3b
```

*(Opzionale)* Per verificare che il modello sia installato o scaricarne un altro:

```powershell
ollama list
ollama pull llama3.2
```

### C. Creare e attivare l'ambiente virtuale (`.venv`)
Crea l'ambiente virtuale nella cartella del progetto:

```powershell
python -m venv .venv
```

Poi attivalo (scegli il comando in base alla shell aperta in VS Code):

- **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
  *(Se PowerShell blocca lo script per i permessi di esecuzione, esegui prima `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)*

- **Windows (Command Prompt / CMD):**
  ```cmd
  .venv\Scripts\activate.bat
  ```

- **Linux / macOS:**
  ```bash
  source .venv/bin/activate
  ```

Quando è attivo, vedrai il prefisso `(.venv)` all'inizio della riga del terminale.

### D. Installare Flask e le dipendenze
Con l'ambiente virtuale attivo, installa **Flask** (e `requests`, se il tuo `app.py` lo utilizza per chiamare le API locali):

```powershell
pip install flask requests
```

*(Se ti serve solo Flask: `pip install flask`)*

### E. Eseguire l'app AuraAI
Assicurati che Ollama sia in esecuzione, poi avvia il server Flask con:

```powershell
python app.py
```

Una volta avviato, apri il browser e vai su:

```text
[http://127.0.0.1:5000](http://127.0.0.1:5000)
```

Per fermare il server in qualsiasi momento, torna sul terminale di VS Code e premi **`Ctrl + C`**.

---

## 5. Struttura del progetto

```text
auraai/
├── app.py
├── templates/
│   ├── chat.html
│   ├── login.html
│   └── rules.html
├── .gitignore
└── README.md
```

Ricordati di includere nel `.gitignore` i file locali come `.venv/`, `__pycache__/`, database `.db` o file utenti locali (`users.json`) prima di caricare il progetto su GitHub.

Appena hai il link del repository passalo pure qui e lo inseriamo al posto del segnaposto!
