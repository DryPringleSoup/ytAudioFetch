import os,requests, yt_dlp, json, re, mimetypes
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, WOAS, TIT2, TPE1, TPUB, APIC
from typing import Any
from colorama import Fore, init
init(autoreset=True)

HOME_DIR = os.path.expanduser("~")
ID3_ALIASES = {
    "url": ("WOAS", WOAS),
    "title": ("TIT2", TIT2),
    "artist": ("TPE1", TPE1),
    "uploader": ("TPUB", TPUB),
    "thumbnail": ("APIC", APIC)
}

def hook(d):
    if d["status"] == "finished": print("\n[dl hook] Finished downloading info of", d['info_dict']['title'])

def ytafURL(arguments: dict) -> None:
    """
    Downloads audio from a YouTube URL and saves it to the specified directory.
    
    Args:
        arguements (dict): A dictionary containing the following keys:
            ytURL (str): The URL of the YouTube video or playlist.
            outputDir (str): The directory where the audio will be saved.
            shouldDownload (bool, optional): Whether to download the audio file. Defaults to True.
            shouldTag (bool, optional): Whether to tag the audio file. Defaults to True.
            shouldSave (bool, optional): Whether to save the tag data to a JSON file. Defaults to True.
            saveFilePath (str, optional): The path to the save file. Defaults to ~/.ytAudioFetchSave.json.
            replacing (bool, optional): Whether to replace the audio file if it already exists. Defaults to False.
            overwriteSave (bool, optional): Whether to overwrite the save file if it already exists. Defaults to False.
            changeableTags (list[str], optional): A list of tags that can be changed. Defaults to None which means all tags can be changed.
    """
    ytURL = arguments.get("ytURL")
    outputDir = arguments.get("outputDir")


    if not ytURL: raise ValueError("ytUrl is required is arguement dictionary")
    if not outputDir: raise ValueError("outputDir is required is arguement dictionary")

    shouldDownload = arguments.get("shouldDownload", True)
    shouldTag = arguments.get("shouldTag", True)
    shouldSave = arguments.get("shouldSave", True)
    
    if not (shouldDownload or shouldTag or shouldSave):
        print(Fore.YELLOW+"All operations are set to False.")
        return

    saveFilePath = arguments.get("saveFilePath", os.path.join(HOME_DIR, ".ytAudioFetchSave.json"))
    replacing = arguments.get("replacing", False)
    overwriteSave = arguments.get("overwriteSave", False)
    changeableTags = arguments.get("changeableTags", list(ID3_ALIASES.keys()))

    outputDir: str = os.path.expanduser(outputDir)
    os.makedirs(outputDir, exist_ok=True)
    
    #download basic info of the playlist/video, significantly faster than extracting the info with the flags in ydlOpts
    #also allpws for really fast checking of repeat video if replacing is set to False
    with yt_dlp.YoutubeDL({ "extract_flat": True, "ignoreerrors": True }) as ydl:
        info = ydl.extract_info(ytURL, download=False)
        
        """
        If a playlist has a unavaliable video, that video's duration is None.
        However, if ytURL is single video, then, when extracted, info itself is None.
        So, I'm normalizing None info to have a None duration since that's how I'm
        checking for unavaliablity. I'm also setting the URL for its subsequent skip message.

        The reason why I'm not putting this in the if statement above is because
        it's possible that for some reason the info is None even if the URL is a playlist
        """        
        if info is None: info = { "entries": [{"duration": None, "url": ytURL}] }
        elif "playlist?list=" not in ytURL: # If the URL is a single video, the info is not in a list and urk is in "webpage_url"
            # Normalizes single-video-extarcted info to be semi-consistent with the playlist-extracted info
            info["url"] = info["webpage_url"]
            info = { "entries": [info] }

    ydlOpts = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": os.path.join(outputDir, "YTAF-%(id)s-%(title)s.%(ext)s"),
        "concurrent-fragments": 4,
        "restrict-filenames": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "ignoreerrors": True,
        "sanitize_filename": True,
        "quiet": False,
        "progress_hooks": [hook],
    }

    if os.path.exists(saveFilePath):
        with open(saveFilePath, "r") as saveFile: saveData = json.load(saveFile)
    else: saveData = {}

    with yt_dlp.YoutubeDL(ydlOpts) as ydl:
        for i, entry in enumerate(info["entries"], start=1):
            print(Fore.BLUE+f"Video {i} of {len(info['entries'])}")
            if entry["duration"] is None:
                print(Fore.RED+"Skipping unavaliable video: "+entry["url"], end="\n\n\n")
                continue
            
            audioFilePath: str = ydl.prepare_filename(entry) # form file path from ydl prompts
            audioFilePath: str = changeFileExt(audioFilePath,"mp3") # change file extension
            
            # if a file path was changed because it had bad characters, its save entry is just { "corrected": newAudioFilePath }, this check for that
            audioSaveExists: bool = audioFilePath in saveData
            if audioSaveExists: audioFilePath: str = saveData[audioFilePath].get("corrected", audioFilePath)
            audioSaveExists: bool = audioFilePath in saveData
            audioFileExists: bool = os.path.exists(audioFilePath)
            # shouldSave is true if the user asked to save in the first place (in the first
            # place) and either the audio file does not exist or the user asked to overwrite
            shouldSave: bool = shouldSave and (not audioSaveExists or overwriteSave)
            
            # If you are replacing or the audio file does not exist parse the data, otherwise (not replacing and the audio file exists) skip
            if shouldTag or shouldSave:
                if replacing or not audioFileExists:
                    print(Fore.GREEN+"Parsing entry data...")
                    """
                    for some reason the max resolution thumbnail is not included
                    when extracting playlists with extract_flat set to True.
                    Even weirder is that the thumbnail is included when extracting
                    a single video because ydl extracts the info the same it does
                    when extract_flat is set to False even though it's set to True.
                    """
                    # if entry was taken from a single video max resolution thumbnail is in entry["thumbnail"]
                    # if entry was taken from a playlist best conpressed resolution thumbnail is in entry["thumbnails"][-1]["url"]
                    entry["thumbnail"] = entry.get("thumbnail", entry["thumbnails"][-1]["url"])
                    metadata: dict[str, str] = parseEntryData(entry)
                    
                    # Saving
                    if shouldSave:
                        print(Fore.GREEN+("Overwriting save data..." if audioSaveExists else "Saving initial data..."))
                        print(*[ key.capitalize()+": "+value for key, value in metadata.items() ], sep="\n")
                        saveData[audioFilePath] = metadata
                    else: print(Fore.YELLOW+"Cannot overwrite existing save data")
                else:
                    print(Fore.YELLOW+"File already exists, skipping: "+entry["title"], end="\n\n\n")
                    continue
            else: print(Fore.YELLOW+"No (tagging or saving) requested, skipping data parsing...")
            


            if shouldDownload: print(Fore.GREEN+f"Downloading ({metadata['url']}):", metadata["title"])
            for i in range(3): # Try downloading video 3 times in case of throttling
                try:
                    verboseInfo = ydl.extract_info(metadata["url"], download=shouldDownload)
                    break
                except Exception as e:
                    print(Fore.RED+"Error downloading:", e)
                    print(Fore.YELLOW+"Retrying...")
            else: print(Fore.RED+f"Failed to download {'' if shouldDownload else 'information for '}{metadata['url']}") # If all 3 attempts fail, print error
            
            if shouldTag or shouldSave:
                oldAudioFilePath: str = audioFilePath
                audioFilePath: str = ydl.prepare_filename(verboseInfo)
                audioFilePath: str = changeFileExt(audioFilePath,"mp3")
                pathChange = audioFilePath != oldAudioFilePath
                if pathChange:
                    print(
                        Fore.YELLOW+"Old audio file path had invalid/invisible characters, using new audio file path",
                        "Old Path: "+audioFilePath, "New Path: "+oldAudioFilePath, sep="\n"
                    )
                metadata["thumbnail"] = verboseInfo["thumbnail"]

                if shouldTag:
                    print(Fore.GREEN+"Adding tags to:", audioFilePath)
                    wasTagged: bool = addID3Tags(audioFilePath, metadata)
                    if wasTagged: print(Fore.GREEN+audioFilePath+" has been fully downloaded and tagged", end="\n\n\n")

                if shouldSave:
                    #delete old audio save from save file
                    if pathChange:
                        print(Fore.YELLOW+"Moving audio save to current audio file path, old save is now justs points new audio file path")
                        saveData[oldAudioFilePath] = { "corrected": audioFilePath }
                    print("Updating save file to include max resolution thumbnail:", metadata["thumbnail"])
                    saveData[audioFilePath] = metadata
                    print(Fore.BLUE+"Writing to save file...")
                    with open(saveFilePath, "w") as saveFile: json.dump(saveData, saveFile, indent=4)
                    print(Fore.GREEN+"All data has been properly saved to:", saveFilePath)
        else: print(Fore.BLUE+"Processing of all entries complete", end="\n\n\n")

def ytafJSON(JsonFilePath, download: bool = True, changeableTags: list[str] = None) -> None:
    """
    Downloads audio files from YouTube with tag data from a JSON file.

    Args:
        JsonFilePath (str): The path to the JSON file containing the tag data.
        download (bool, optional): Whether to download the audio files. Defaults to True.
        changeableTags (list[str], optional): A list of tags that can be changed. Defaults to None which means
        all tags can be changed. If all entries are not included, the ones not included are assumed to be changeable.
    """
    if changeableTags is None: changeableTags: list[str] = list(ID3_ALIASES.keys())
    
    JsonFilePath: str = os.path.expanduser(JsonFilePath)
    if not os.path.exists(JsonFilePath):
        print(Fore.RED+"JSON file does not exist:", JsonFilePath)
        return

    with open(JsonFilePath, "r") as saveFile: saveData = json.load(saveFile)
    entries = len(saveData)
    
    for i, (audioFilePath, data) in enumerate(saveData.items()):
        print(Fore.BLUE+f"JSON entry {i+1} of {entries}:", audioFilePath)
        print(*[ f"{key}: {value}" for key, value in data.items()], sep="\n")

        if "corrected" in data:
            print(Fore.YELLOW+"Audio file path had invalid/invisible characters, and had been changed to:", audioFilePath, end="\n\n\n")
            continue

        if not os.path.exists(audioFilePath):
            print(Fore.YELLOW+"File does not exist:", audioFilePath)
            if download:
                print(Fore.GREEN+"Downloading:", data["url"])
                simpleAudioDownload(data["url"], audioFilePath)
            else:
                print(Fore.YELLOW+"No downloads allowed. Skipping...")
                continue

        print(Fore.GREEN+"Adding tags to:", audioFilePath)
        data: dict[str, str] = { key: value for key, value in data.items() if key in changeableTags }
        addID3Tags(audioFilePath, data)

        print(Fore.GREEN+audioFilePath+" has been fully downloaded and tagged", end="\n\n\n")
    else: print(Fore.BLUE+"Processing of all entries complete")

def simpleAudioDownload(url: str, outputPath: str, returnInfo: bool = False) -> None:
    """
    Downloads an audio file from YouTube and saves it to the specified output path.
    
    Args:
        url (str): The URL of the YouTube video or playlist.
        outputPath (str): The path to save the audio file to.
        returnInfo (bool, optional): Whether to return information about the downloaded audio file. Defaults to False.
    """
    ydlOpts: dict[str, Any] = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "temp-YTAF-%(id)s-%(title)s.%(ext)s",
        "concurrent-fragments": 4,
        "restrict-filenames": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": False,
        "progress_hooks": [hook],
    }

    print(Fore.GREEN+"Downloading:", url)
    with yt_dlp.YoutubeDL(ydlOpts) as ydl:
        for i in range(3):
            try:
                info: dict[str, Any] = ydl.extract_info(url, download=True)
                break
            except Exception as e:
                print(Fore.RED+"Error downloading:", e)
                print(Fore.YELLOW+"Retrying...")
        else: # If all 3 attempts fail, print error
            print(Fore.RED+"Failed to download: ", url)
            return None
        
        print(Fore.GREEN+"Successfully downloaded:", info["title"])
        audioFilePath: str = changeFileExt(ydl.prepare_filename(info), "mp3")
        print(Fore.GREEN+"Saved to:", audioFilePath)
        print(Fore.GREEN+"Renaming to:", outputPath)
        os.rename(audioFilePath, outputPath)
        if returnInfo: return info

def changeFileExt(filename: str, newExt: str) -> str:
    """
    Changes the file extension of the given filename.
    
    Args:
        filename (str): The original filename.
        newExt (str): The new file extension.
    
    Returns:
        str: The filename with the new extension.
    """
    for i, char in enumerate(filename[::-1]):
        if char == ".": break
    return filename[:len(filename)-i]+newExt

def parseEntryData(data: dict[str, str]) -> dict[str, str]:
    """
    Parses entry data from the YouTube video information.
    
    Args:
        data (dict[str, str]): The YouTube video information.
    
    Returns:
        dict[str, str]: The parsed entry data.
    """
    title: str = data["title"]
    uploader: str = data["uploader"]

    # If video title is in the form "[artist] - [title]" parse it into the tags like that
    # otherwise let the artist tag just be the uploader
    # This is obviously not always accurate but it's good enough for me not to spend more time on it
    if " - " in title: artist, title = title.split(" - ", 1)
    else: artist = uploader

    return {
        "url": data["url"],
        "title": title,
        "artist": artist,
        "uploader": uploader,
        "thumbnail": data["thumbnail"]
    }

def addID3Tags(audioFilePath: str, data: dict[str, str] = None) -> bool:
    """
    Adds ID3 tags to the audio file.
    
    Args:
        audioFilePath (str): The path to the audio file.
        data (dict[str, str], optional): The data for the ID3 tags. Defaults to None.
    """
    if not os.path.exists(audioFilePath):
        print(Fore.RED+"Warning!","Audio file does not exist:", audioFilePath)
        print(Fore.YELLOW+"Skipping ID3 tagging...")
        return False

    if not data: data = {}

    try:
        audio = MP3(audioFilePath, ID3=ID3)
        cover: str = data.pop("thumbnail", None)
        for tag, value in data.items():
            if tag in ID3_ALIASES:
                id3Tag = ID3_ALIASES[tag][1]
                tagText = value or f"[No {tag}]"
                print(Fore.MAGENTA+f"Adding {tag} tag:", tagText)
                audio.tags.add(id3Tag(encoding=3, text=[tagText]))
            else: print(Fore.YELLOW+"Warning!","Unknown tag:", tag)

        # Cover path from either online or local source
        if cover:
            isLink: bool = re.match(r"^https?://", cover)
            coverIsTemp: bool = False
            if isLink:
                cover: str = downloadThumbnail(cover)
                coverIsTemp: bool = True
            elif not os.path.exists(cover): cover: str = "NoCover.jpg"
            elif mimetypes.guess_type(cover)[0] != "image/jpeg":
                newCover: str = changeFileExt(cover, "jpg")
                convertToJpg(cover, newCover)
                cover: str = newCover
                coverIsTemp: bool = True
        else: cover: str = "NoCover.jpg"

        print(Fore.MAGENTA+"Adding cover image:", cover)
        with open(cover, "rb") as img:
            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3, desc=u'Cover',
                data=img.read()
            ))
        if coverIsTemp:
            os.remove(cover)
            print(Fore.YELLOW+"Deleted Temp Thumbnail:", cover)

        audio.save()
        print(f"Tags added for: {data['title']} by {data['artist']}")
        return True
    except Exception as e: print(Fore.RED+f"Error adding tags to {audioFilePath}:", e)

def convertToJpg(inputImagePath: str, outputImagePath: str) -> None:
    """
    Converts an image to JPEG format.
    
    Args:
        inputImagePath (str): The path to the input image.
        outputImagePath (str): The path to the output image.
    """
    try:
        with Image.open(inputImagePath) as img:
            rgb_img = img.convert('RGB')
            rgb_img.save(outputImagePath, 'JPEG')
            print("Image converted and saved as", outputImagePath)
    except Exception as e: print("An error occurred when converting:", {e})

def downloadThumbnail(thumbnailURL: str) -> str:
    """
    Downloads a thumbnail image from a URL.
    
    Args:
        thumbnailURL (str): The URL of the thumbnail image.
    
    Returns:
        str: The filename of the downloaded thumbnail.
    """
    response: int = requests.get(thumbnailURL)
    if response.status_code == 200:
        print(Fore.GREEN+"Successfully downloaded thumbnail:", thumbnailURL)
        cover = "temp-YTAF-"+thumbnailURL.split("/")[-1]
        print("Temp Thumbnail Filename:", cover)
        with open(cover, "wb") as f: f.write(response.content)

        # Covers don't appear correctly in other formats
        if mimetypes.guess_type(cover)[0] != "image/jpeg": #convert cover image to jpeg
            newcover = changeFileExt(cover, "jpg")
            convertToJpg(cover, newcover)
            print(Fore.YELLOW+"Deleting old cover image:", cover)
            os.remove(cover)
            cover = newcover
        return cover
    else:
        print(Fore.RED+"Failed to download thumbnail:", thumbnailURL)
        return "NoCover.jpg"

def strInput(inputText: str) -> str:
    """Asks the user for input until a non-empty string is entered."""
    while not (string := input(inputText)): pass
    return string

def boolInput(inputText: str) -> bool:
    """Asks the user for input until a valid boolean value is entered."""
    return input(inputText).lower() in ["y","","yes","true"]


if __name__ == "__main__": # User inputs
    while True: # Keeps asking for input until a valid mode is entered
        mode: str = strInput("URL or JSON mode? (1 or 2): ")

        if mode not in ["1", "2"]:
            print(Fore.RED+"Invalid mode. Please enter 1 or 2.")
            continue
        
        print("Operations:")
        print("\td: Download audio\tt: Tag audio"+("s: save tags" if mode == "1" else ""))
        downloadMethod: str = strInput("Include the letters for each of operation you want to perform: ").lower()
        shouldDownload, shouldTag, shouldSave = "d" in downloadMethod, "t" in downloadMethod, "s" in downloadMethod
        
        if not (shouldDownload or shouldTag or shouldSave):
            print(Fore.RED+"No operations selected. Terminating...")
            break
        
        arguments: dict[str, Any] = { # There were too many arguments so I'm stuff them all in a dictionary
            "ytURL": strInput("Enter the YouTube playlist/video URL: ") if mode == "1" else None,
            "outputDir": strInput("Enter the directory to save the MP3 files: ") if mode == "1" else None,
            "shouldDownload": shouldDownload,
            "shouldTag": shouldTag,
            "shouldSave": shouldSave,
            "saveFilePath": strInput("Enter the path of the JSON save file: ") if shouldSave else None,
            "replacing": boolInput("Replace existing files? (y/n): ") if shouldDownload else False,
            "overwriteSave": boolInput("Overwrite data in save file? (y/n): ") if shouldSave else False
        }

        if shouldTag:
            availableTags: list[str] = list(ID3_ALIASES.keys())
            print("Avaliable tags:", *[f"\t{i+1}: {tag}" for i, tag in enumerate(availableTags)], sep="\n")
            selectedTags: str = strInput("Enter the tags you want to change: ")
            selectedTags: set[int] = {i for i in range(4) if str(i) in selectedTags}
            changeableTags: list[str] = [ availableTags[i] for i in selectedTags ]
            arguments["changeableTags"] = changeableTags
        else: arguments["changeableTags"] = []

        if mode == "1": ytafURL(arguments)
        elif mode == "2": ytafJSON(arguments)

        break