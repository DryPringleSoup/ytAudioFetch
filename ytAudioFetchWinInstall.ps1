# Download necessary dependencies and clone repo
try {
    # Check if dependencies are already installed
    $dependencies = @("Git.Git", "python", "pip", "ffmpeg")
    foreach ($dependency in $dependencies) {
        if (Get-Package -Name $dependency -ErrorAction SilentlyContinue) { Write-Host "$dependency is already installed." }
        else { winget install $dependency }
    }
    
    # Overwrite existing ytAudioFetch directory
    cd ~
    Remove-Item -Path "~\ytAudioFetch" -Recurse -Force
    git clone https://github.com/DryPringleSoup/ytAudioFetch.git
    cd ytAudioFetch
    python -m venv ytafenv
    ytafenv\Scripts\Activate.ps1
    pip install -r requirements.txt

} catch {
    Write-Host "Error occurred: $_"
    exit 1
}

# Download executable and place on desktop
$repoUrl = "https://github.com/DryPringleSoup/ytAudioFetch/raw/refs/heads/master/"
$filePath = "ytAudioFetch.exe"
$gitUrl = $repoUrl + $filePath
$desktopPath = [Environment]::GetFolderPath("Desktop")
$outputPath = Join-Path -Path $desktopPath -ChildPath $filePath

try {
    Invoke-WebRequest -Uri $gitUrl -OutFile $outputPath
    Write-Host "File downloaded successfully: $outputPath"
} catch {
    Write-Host "Error occurred: $_"
    exit 1
}