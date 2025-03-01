# ytAudioFetch
Light [yt-dlp](https://github.com/yt-dlp/yt-dlp) gui that fetches audio from playlists/videos as .mp3's and tags them with artists, titles, and cover art/thumbnail

## Installation
### Installer
If you're on linux just download the ytafLinuxInstaller and run it
### Command Line
1. Clone repository:
   ```bash
   git clone https://github.com/DryPringleSoup/ytAudioFetch.git
   ```

2. Create virtual environment
   ```bash
   python -m venv ytafenv
   ```
3. Activate environment
  - On Windows
     ```bash
     ytafenv\Scripts\activate
     ```
  - On Linux
     ```bash
     source ytafenv\bin\activate
     ```

4. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

5. Run GUI
   ```bash
   python ytAudioFetchGUI.py
   ```

Copy and paste
- Windows
    ```bash
    git clone https://github.com/DryPringleSoup/ytAudioFetch.git
    python -m venv ytafenv
    ytafenv\Scripts\activate
    pip install -r requirements.txt
    python ytAudioFetchGUI.py
    ```

- Linux
    ```bash
    git clone https://github.com/DryPringleSoup/ytAudioFetch.git
    python -m venv ytafenv
    source ytafenv\bin\activate
    pip install -r requirements.txt
    python ytAudioFetchGUI.py
    ```