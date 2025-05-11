# Check if winget is available, if not, offer alternative method.
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget not found. Please install winget (https://aka.ms/getwinget) or use another method to install dependencies."
    exit 1
}

# Download necessary dependencies and clone repo
$repoPath = Join-Path -Path $HOME -ChildPath "ytAudioFetch"
try {
    # Check if dependencies are already installed
    $dependencies = @("Git.Git", "python", "ffmpeg")
    foreach ($dependency in $dependencies) {
        if (Get-Package -Name $dependency -ErrorAction SilentlyContinue) { Write-Host "$dependency is already installed." }
        else { winget install $dependency }
    }
    
    # Pull repo if already cloned, otherwise clone
    if (Test-Path $repoPath) {
        Set-Location $repoPath
        git reset --hard
        git pull
    } else {
        git clone https://github.com/DryPringleSoup/ytAudioFetch.git $repoPath
        Set-Location $repoPath
        python -m venv ytafenv
    }
    
    # Update/install requirements for python veny
    & "ytafenv\Scripts\Activate.ps1"
    try { pip install -r requirements.txt }
    catch { # Install with plain pip because requirements.txt doesn't work sometimes for some reason
        Write-Host "Error occurred with installing with requirements.txt: $_"
        try { pip install requests yt-dlp mutagen pillow pyqt5 colorama }
        catch {
            Write-Host "Error occurred with installing with plain pip: $_"
            exit 1
        }
    }

} catch {
    Write-Host "Error occurred: $_"
    exit 1
}

# copy ytAudioFetch.exe to desktop
$filePath = Join-Path -Path $repoPath -ChildPath "ytAudioFetch.exe"
$outputPath = Join-Path -Path [Environment]::GetFolderPath("Desktop") -ChildPath "ytAudioFetch.exe"
Copy-Item -Path $filePath -Destination $outputPath -Force