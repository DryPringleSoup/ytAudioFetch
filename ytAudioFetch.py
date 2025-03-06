import os, requests, yt_dlp, json, re, mimetypes
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, WOAS, TIT2, TPE1, TPUB, APIC, COMM
from typing import Any, Tuple, List, Dict, Union
from colorama import Fore, init
init(autoreset=True)

HOME_DIR = os.path.expanduser("~")
RETRY_LIMIT = 3
FILENAME_FORMAT = "YTAF-%(id)s-%(title)s.%(ext)s"
ID3_ALIASES = { # official ID3 tagnames: https://exiftool.org/TagNames/ID3.html
    "url": WOAS, # SourceURL
    "title": TIT2, # Title
    "artist": TPE1, # Artist
    "uploader": TPUB, # Publisher
    "thumbnail": APIC, # Picture
    "description": COMM # Comment
}
def hook(d: Dict[str, Any]) -> None:
    if d["status"] == "finished": print("  [dl hook] Finished downloading info of", d['info_dict']['title'], end="")
YDL_VERBOSE_EXTRACTION_OPTS = {
    "format": "bestaudio/best",
    "extractaudio": True,
    "audioformat": "mp3",
    "outtmpl": FILENAME_FORMAT,
    "concurrent-fragments": 4,
    "restrict-filenames": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "320", # the highest I found youtube goes is 320
    }],
    "quiet": False,
    "progress_hooks": [hook],
}
YDL_CONCISE_EXTRACTION_OPTS = { # For single videos extraction both of these options behave the same
    "extract_flat": True,
    "outtmpl": FILENAME_FORMAT
}

#URL MODE
def ytafURL(arguments: Dict) -> List[Tuple[str, str]]:
    """
    Downloads audio from a YouTube URL and saves it to the specified directory.
    
    Args:
        arguments (Dict): A dictionary containing the following keys:
            ytURL (str): The URL of the YouTube video or playlist.
            outputDir (str): The directory where the audio will be saved.
            saveFilePath (str, optional): The path to the save file. Defaults to ~/.ytAudioFetchSave.json.
            downloading (bool, optional): Whether to download the audio file. Defaults to True.
            tagging (bool, optional): Whether to tag the audio file. Defaults to True.
            saving (bool, optional): Whether to save the tag data to a JSON file. Defaults to True.
            replacingFiles (bool, optional): Whether to replace the audio file if it already exists. Defaults to False.
            tagExisting (bool, optional): Whether to tag existing files. Defaults to False
            changeableTags (List[str], optional): A list of tags that can be changed. Defaults to None which means all tags can be changed.
            overwriteSave (bool, optional): Whether to overwrite the save file if it already exists. Defaults to False.
            verboseSkipList (bool, optional): Whether to print all operations that were skipped or just downloads. Defaults to False.
    Returns:
        List[Tuple[str, str]]: A list of tuples each containing the link to a skipped video/playlist and the reason for skipping.
    """
    # Validate and prepare input arguments
    params = validateAndPrepareArgsURL(arguments)
    if params is None: return []
    ( ytURL, outputDir, saveFilePath, downloading, tagging, saving, replacingFiles,
      tagExisting, changeableTags, overwriteSave, verboseSkipList ) = params

    skipList = []
    
    # Extract basic info (with retry logic)
    info = extractBasicInfo(ytURL, outputDir, skipList)
    numVideos = len(info.get('entries', []))
    
    # Setup ydl options for verbose download/tagging operations
    ydlOpts = YDL_VERBOSE_EXTRACTION_OPTS.copy()
    ydlOpts["outtmpl"] = os.path.join(outputDir, ydlOpts["outtmpl"])
    
    # Load save data
    if saving: saveData = loadSaveData(saveFilePath)
    else: saveData = {}
    
    print()
    for i, entry in enumerate(info.get("entries", []), start=1): # Process each entry in the info
        print(Fore.BLUE + f"Video {i} of {numVideos}", "-", entry['url'])
        processEntryURL(
            entry, ydlOpts, saveData, downloading, tagging,
            saving, replacingFiles, tagExisting, overwriteSave,
            changeableTags, skipList, verboseSkipList
        )
        print("\n")
    else: print(Fore.BLUE + "Processing of all entries complete")
    
    if saving:
        with open(saveFilePath, "w") as saveFile: json.dump(saveData, saveFile, indent=4)
        print(Fore.GREEN + "All data has been properly saved to:", saveFilePath)

    return skipList

def validateAndPrepareArgsURL(arguments: Dict) -> Tuple[str, str, str, bool, bool, bool, bool, bool, List[str], bool, bool]:
    """Validates and prepares the input arguments for the ytafURL function."""
    ytURL = arguments.get("ytURL")
    outputDir = arguments.get("outputDir")
    if not ytURL: raise ValueError("ytURL is required in argument dictionary")
    if not outputDir: raise ValueError("outputDir is required in argument dictionary")
    
    downloading = arguments.get("downloading", True)
    tagging = arguments.get("tagging", True)
    saving = arguments.get("saving", True)
    if not (downloading or tagging or saving):
        print(Fore.YELLOW + "All operations are set to False.")
        return None  # Early exit can be handled in the caller

    changeableTags = arguments.get("changeableTags", list(ID3_ALIASES))
    if not (downloading or changeableTags): # Since this passed previous check, if downloading is false either tagging or saving must be true
        print(Fore.YELLOW + "Tagging or saving requires at least one tag to be changeable.")
        return None

    saveFilePath = os.path.expanduser( arguments.get("saveFilePath", os.path.join(HOME_DIR, ".ytAudioFetchSave.json")))
    replacingFiles = arguments.get("replacingFiles", False)
    tagExisting = arguments.get("tagExisting", False)
    overwriteSave = arguments.get("overwriteSave", False)
    verboseSkipList = arguments.get("verboseSkipList", False)
    outputDir = os.path.expanduser(outputDir)
    os.makedirs(outputDir, exist_ok=True)
    
    return ytURL, outputDir, saveFilePath, downloading, tagging, saving, replacingFiles, tagExisting, changeableTags, overwriteSave, verboseSkipList

def loadSaveData(saveFilePath: str) -> Dict[str, Dict[str, str]]:
    """Loads save data from a JSON file."""
    print(Fore.BLUE + "Loading save data from " + saveFilePath)
    try:
        with open(saveFilePath, "r") as saveFile: return json.load(saveFile)
    except:
        print("Error loading JSON file. Initializing with empty data.")
        return {}
    finally: print()

def extractBasicInfo(ytURL: str, outputDir: str, skipList: List[Tuple[str, str]]) -> Dict:
    """
    Downloads basic info of a YouTube playlist/video and normalizes it to a playlist-like structure.
    Significantly faster than extracting the info with the base flags and allows for really fast checking of repeat video.
    
    Args:
        ytURL (str): The URL of the YouTube playlist/video.
        outputDir (str): The path to the output directory.
        skipList (List[Tuple[str, str]]): A list of tuples where the first element is a YouTube URL and the second element is the reason why it was skipped.
    
    Returns:
        Dict: A dictionary containing the basic info of the playlist/video.
    """
    ydlOpts = YDL_CONCISE_EXTRACTION_OPTS.copy()
    ydlOpts["outtmpl"] = os.path.join(outputDir, ydlOpts["outtmpl"])
    
    with yt_dlp.YoutubeDL(ydlOpts) as ydl:
        for i in range(RETRY_LIMIT):
            try:
                info = ydl.extract_info(ytURL, download=False)
                break
            except yt_dlp.utils.DownloadError as e:
                extractionError = e
                # Check for non-connection errors on first try
                if i == 0 and not isConnectionError(extractionError):
                    addToSkipList(skipList, ytURL, extractionError)
                    info = {"entries": []}
                    break
                else:
                    print(Fore.RED + f"Error extracting: {extractionError}")
                    if i < RETRY_LIMIT - 1:
                        print(Fore.YELLOW + "Retrying...")
        else:
            print(Fore.RED + f"Failed to extract information for {ytURL}")
            addToSkipList(skipList, ytURL, extractionError)
            info = {"entries": []}
    
    # playlists have the basename: "playlist" 
    if info.get("webpage_url_basename") == "watch" and not skipList:
        # Normalize single video to a playlist-like structure
        info["url"] = info["webpage_url"]
        info = {"entries": [info]}
    
    # For Debugging: outputs all entry information in readable format
    # for entry in info.get("entries", []): print("\n".join(f"{key}: {value}" for key, value in entry.items()),end="\n\n")
    return info

def processEntryURL(entry: Dict[str, Any], ydlOpts: Dict[str, Any], saveData: Dict[str, Dict[str, str]], downloading: bool,
                    tagging: bool, saving: bool, replacingFiles: bool, tagExisting: bool, overwriteSave: bool,
                    changeableTags: List[str], skipList: List[Tuple[str, str]], verboseSkipList: bool) -> None:
    """
    Processes a single entry in a playlist.
    
    Args:
        entry (Dict[str, Any]): A dictionary containing the info of the YouTube video.
        ydlOpts (Dict[str, Any]): A dictionary of options for the yt-dlp YoutubeDL object.
        saveData (Dict[str, Dict[str, str]]): A dictionary containing existing save data.
        downloading (bool): Whether to download the audio file.
        tagging (bool): Whether to tag the audio file.
        saving (bool): Whether to save the tag data to a JSON file.
        replacingFiles (bool): Whether to replace the audio file if it already exists.
        tagExisting (bool): Whether to tag existing files.
        overwriteSave (bool): Whether to overwrite the save file if it already exists.
        changeableTags (List[str]): A list of tags that can be changed.
        skipList (List[Tuple[str, str]]): A list of tuples where the first element is a YouTube URL and the second element is the reason why it was skipped.
        verboseSkipList (bool): Whether to print all operations that were skipped or just downloads.
    """

    if entry.get("duration") is None: # Skip if video is unavailable
        print(Fore.RED + "Skipping unavailable video: " + entry["url"])
        with yt_dlp.YoutubeDL(ydlOpts) as ydl:
            try: ydl.extract_info(entry["url"], download=False)
            except yt_dlp.utils.DownloadError as e: addToSkipList(skipList, entry["url"], e)
        return

    audioFilePath = getActualFileName(entry, ydlOpts)
    audioFileExists = os.path.exists(audioFilePath)
    audioSaveExists = audioFilePath in saveData
    shouldDownload = downloading and (replacingFiles or not audioFileExists)
    shouldTag = tagging and changeableTags and ((tagExisting and audioFileExists) or shouldDownload)
    shouldSave = saving and changeableTags and (overwriteSave or not audioSaveExists)

    if shouldDownload or ((shouldTag or shouldSave) and hasVerboseTags(changeableTags)):
        print(Fore.GREEN + f"{'Downloading' if shouldDownload else 'Extracting info for'} ({entry['url']}):", entry["title"])
        with yt_dlp.YoutubeDL(ydlOpts) as ydl:
            for i in range(RETRY_LIMIT):
                try:
                    verboseInfo = ydl.extract_info(entry["url"], download=shouldDownload)

                    """
                    For some reason, the verbose extraction doesn't always give the full title which messes up the filename
                    As an example this video: https://www.youtube.com/watch?v=UnIhRpIT7nc
                    The full title is "inabakumori - Lagtrain (Vo. Kaai Yuki) / 稲葉曇『ラグトレイン』Vo. 歌愛ユキ"
                    The verbose extraction only gives: "稲葉曇『ラグトレイン』Vo. 歌愛ユキ" (verboseInfo["title" or "fulltitle"])
                    This is mad doubly confusing because the concise extraction gives it perfect fine
                    """
                    os.rename(getActualFileName(verboseInfo, ydlOpts), audioFilePath)

                    # The original, full resolution thumbnail can only be accessed through verbose extraction
                    entry["thumbnail"] = verboseInfo["thumbnail"]
                    entry["description"] = verboseInfo["description"]
                    break
                except yt_dlp.utils.DownloadError as e:
                    extractionError = e

                    if i == 0:

                        if not isConnectionError(extractionError): # if its not a connection error, don't retry
                            # age restricted videos still have a thumbnail, thoughnot the full res one
                            if "confirm your age" in str(extractionError): entry["thumbnail"] = entry["thumbnails"][-1]["url"]
                            i = RETRY_LIMIT-1
                            break
                            
                    else:
                        print(Fore.RED + f"Error {'downloading' if shouldDownload else 'extracting'}: {extractionError}")
                        if i < RETRY_LIMIT - 1: print(Fore.YELLOW + "Retrying...")
            
            if i == RETRY_LIMIT-1:
                print(Fore.RED + f"Failed to {'download' if shouldDownload else 'extract information for'} {entry['url']}")
                addToSkipList(skipList, entry["url"], extractionError)
                return

    audioFileExists = os.path.exists(audioFilePath)
    shouldTag = shouldTag and audioFileExists
    
    if shouldTag or shouldSave:
        print(Fore.GREEN + "Parsing entry data...")
        metadata = parseEntryData(entry, changeableTags)
    
    if shouldTag:
        print(Fore.GREEN + "Adding tags to:", audioFilePath)
        result, wasTagged = addID3Tags(audioFilePath, metadata)
        if wasTagged: print(Fore.GREEN + audioFilePath + " has been fully downloaded and tagged")
        elif verboseSkipList: addToSkipList(skipList, entry["url"], result)
    
    if shouldSave:
        print(Fore.GREEN + ("Overwriting save" if audioSaveExists else "Saving initial") + " data...")
        for key, value in metadata.items(): print( key.capitalize()+": "+value )
        
        if audioFilePath in saveData:
            if overwriteSave: saveData[audioFilePath].update(metadata)
        else: saveData[audioFilePath] = metadata
    elif not overwriteSave and audioSaveExists:  
        print(Fore.YELLOW + "Cannot overwrite existing save data, skipping...")
        if verboseSkipList: addToSkipList(skipList, entry["url"], "Skipped Saving. Save data already exists when save overwrite is disabled.")

def getActualFileName(infoDict: Dict[str, Any], ydlOpts: Dict[str, Any]) -> str:
    """Returns the actual file name of a video from its info dictionary."""
    return os.path.normpath( changeFileExt( yt_dlp.YoutubeDL(ydlOpts).prepare_filename(infoDict), "mp3" ) )

def hasVerboseTags(changeableTags: List[str]) -> bool:
    """Some tags need verbose info dict, this function checks if any of tags requested are one of those"""
    return any(tag in ["thumbnail","description"] for tag in changeableTags)

def parseEntryData(data: Dict[str, str], tagRequests: List[str] = None) -> Dict[str, str]:
    """
    Parses entry data from the YouTube video information.
    
    Args:
        data (Dict[str, str]): The YouTube video information.
        tagRequests (List[str], optional): A list of tags that can be changed. Defaults to None which means all tags can be changed.
    
    Returns:
        Dict[str, str]: The parsed entry data.
    """
    if not tagRequests: tagRequests = list(ID3_ALIASES)

    parsedData = {}
    for tag in ID3_ALIASES:
        if tag in tagRequests: parsedData[tag] = data.get(tag)

    if "artist" in tagRequests or "title" in tagRequests:
        title = data.get("title")

        # If video title is in the form "[artist] - [title]" parse it into the tags like that
        # otherwise let the artist tag just be the uploadeS
        # This is obviously not always accurate but it's good enough for me not to spend more time on it
        if " - " in title: artist, title = title.split(" - ", 1)
        else: artist = data.get("uploader").replace(" - Topic", "")

        parsedData["artist"] = artist
        parsedData["title"] = title

    return parsedData

# JSON mode
def ytafJSON(arguments: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Args:
        arguments (Dict): A dictionary containing the following keys:
            saveFilePath (str): The path to the save file to be extracted from
            downloading (bool, optional): Whether to download the audio files. Defaults to True.
            tagging (bool, optional): Whether to tag the audio files. Defaults to True.
            replacingFiles (bool, optional): Whether to replace the audio if it already exists. Defaults to False.
            changeableTags (List[str], optional): A list of tags that can be changed. Defaults to None which means all tags can be changed.
            verboseSkipList (bool, optional): Whether to print all operations that were skipped or just downloads. Defaults to False.
    """
    # Validate and prepare input arguments
    params = validateAndPrepareArgsJSON(arguments)
    if params is None: return []
    ( saveFilePath, downloading, tagging, replacingFiles, changeableTags, verboseSkipList ) = params

    # Load save data
    saveData = loadSaveData(saveFilePath)
    entries = len(saveData)
    skipList = []

    # Setup ydl options for verbose download/tagging operations
    ydlVerbose = YDL_VERBOSE_EXTRACTION_OPTS.copy()
    
    print()
    for i, (audioFilePath, data) in enumerate(saveData.items(), start=1):
        print(Fore.BLUE+f"JSON entry {i} of {entries}", "-", audioFilePath)
        print(*[ f"{key}: {value}" for key, value in data.items()], sep="\n")
        processEntryJSON(
            audioFilePath, data, ydlVerbose, downloading, tagging,
            replacingFiles, changeableTags, skipList, verboseSkipList
        )
        print("\n")
    else: print(Fore.BLUE + "Processing of all entries complete")
    
    return skipList

def validateAndPrepareArgsJSON(arguments: Dict) -> Tuple[str, bool, bool, bool, List[str], bool]:
    """Validates and prepares the input arguments for the ytafJSON function."""
    saveFilePath = arguments.get("saveFilePath")
    if not saveFilePath: raise ValueError("saveFilePath is required is argument dictionary")

    downloading = arguments.get("downloading", True)
    tagging = arguments.get("tagging", True)
    if not (downloading or tagging):
        print(Fore.YELLOW+"All operations are set to False.")
        return None  # Early exit can be handled in the caller
    
    changeableTags = arguments.get("changeableTags", list(ID3_ALIASES))

    if not (downloading or changeableTags): # Since this passed previous check, if downloading is false either tagging or saving must be true
        print(Fore.YELLOW + "Tagging requires at least one tag to be changeable.")

    saveFilePath = os.path.expanduser(saveFilePath)
    replacingFiles = arguments.get("replacingFiles", False)
    verboseSkipList = arguments.get("verboseSkipList", False)
    
    return saveFilePath, downloading, tagging, replacingFiles, changeableTags, verboseSkipList

def processEntryJSON(audioFilePath: str, data: Dict[str, Dict[str, str]], ydlOpts: Dict[str, Any], downloading: bool, tagging: bool,
                     replacingFiles: bool, changeableTags: List[str], skipList: List[Tuple[str, str]], verboseSkipList: bool) -> None:
    """
    Processes a single entry from a JSON file. More or less just processEntryURL but with no saving functionality
    since it's already extracting from a JSON file.
    
    Args:
        audioFilePath (str): The path to the audio file.
        data (Dict[str, Dict[str, str]]): The data extracted from the JSON file.
        ydlOpts (Dict[str, Any]): The options for the verbose download.
        downloading (bool): Whether to download the audio file.
        tagging (bool): Whether to tag the audio file.
        replacingFiles (bool): Whether to replace existing audio files.
        changeableTags (List[str]): The list of tags that can be changed.
        skipList (List[Tuple[str, str]]): The list of skipped entries.
        verboseSkipList (bool): Whether to print all operations that were skipped or just downloads.
    """
    if mimetypes.guess_type(audioFilePath)[0] != "audio/mpeg":
        print(Fore.RED+"Warning!", audioFilePath, "is not an MP3, skipping...")
        skipList.append((audioFilePath, "Not an MP3"))
        return

    audioFileExists = os.path.exists(audioFilePath)
    shouldDownload = downloading and (replacingFiles or not audioFileExists)

    if shouldDownload:
        ydlOpts["outtmpl"] = changeFileExt(audioFilePath, "%(ext)s")
        url = data.get("url")
        if url:
            print(Fore.GREEN + f"Downloading {data['url']} to {audioFilePath}")
            with yt_dlp.YoutubeDL(ydlOpts) as ydl:
                for i in range(RETRY_LIMIT):
                    try:
                        ydl.extract_info(data["url"], download=shouldDownload)
                        audioFileExists = True
                        break
                    except yt_dlp.utils.DownloadError as e:
                        extractionError = e
                        # Check for non-connection errors on first try
                        if i == 0 and not isConnectionError(extractionError):
                            addToSkipList(skipList, data["url"], extractionError)
                            skipList[-1] = (audioFilePath, f"({skipList[-1][0]}) {skipList[-1][1]}")
                            break
                        else:
                            print(Fore.RED + f"Error {'downloading' if shouldDownload else 'extracting'}: {extractionError}")
                            if i < RETRY_LIMIT - 1: print(Fore.YELLOW + "Retrying...")
                else:
                    print(Fore.RED + f"Failed to {'download' if shouldDownload else 'extract information for'} {data['url']}")
                    addToSkipList(skipList, data["url"], extractionError)
                    skipList[-1] = (audioFilePath, f"({skipList[-1][0]}) {skipList[-1][1]}")
                    return
        else:
            print(Fore.YELLOW + "No URL found for this entry, skipping...")
            addToSkipList(skipList, audioFilePath, "No URL found for this entry")
    
    audioFileExists = os.path.exists(audioFilePath)
    shouldTag = tagging and changeableTags and audioFileExists

    if shouldTag:
        metadata = { key: data.get(key) for key in changeableTags if data.get(key) }
        result, wasTagged = addID3Tags(audioFilePath, metadata)
        if wasTagged: print(Fore.GREEN + audioFilePath + " has been fully downloaded and tagged")
        elif verboseSkipList: addToSkipList(skipList, audioFilePath, result)

# Other general helper functions
def addToSkipList(skipList: List[Tuple[str, str]], ytURL: str, error: Union[yt_dlp.utils.DownloadError, str]):
    """Adds an entry to the skip list."""
    if isinstance(error, yt_dlp.utils.DownloadError):
        error = str(error).split(": ")[-1]
        tldr = [
            ("confirm your age", "Age Restriction"),
            ("Private video", "Private video"),
            ("Bad Request", "Bad Playlist URL"),
            ("is not a valid URL", "Invalid URL"),
            ("Failed to resolve", "Failed connection to YouTube"),
            ("Failed to extract", "Failed to extract any player response; possible connection issue")
        ]
        for phrase, reason in tldr:
            if phrase in error:
                error = reason
                break
        if error == "Video unavailable": error += ". Link likely points to non-existent or unlisted video."
        if error == "Forbidden": error += ". Check your internet and/or try to download again."
    skipList.append((ytURL, error))

def isConnectionError(error: yt_dlp.utils.DownloadError) -> bool:
    """Checks if the given error is a connection error."""
    error = str(error)
    return any(phrase in error for phrase in ["Failed to resolve", "Failed to extract"])

def changeFileExt(filename: str, newExt: str) -> str:
    """Changes the file extension of the given filename."""
    for i, char in enumerate(filename[::-1]):
        if char == ".": break
    return filename[:len(filename)-i]+newExt

# Tagging functions
def addID3Tags(audioFilePath: str, data: Dict[str, str] = None) -> Tuple[str, bool]:
    """
    Adds ID3 tags to the audio file.
    
    Args:
        audioFilePath (str): The path to the audio file.
        data (Dict[str, str], optional): The data for the ID3 tags. Defaults to None.
    
    Returns:
        Tuple[str, bool]: A tuple containing the message and a boolean indicating whether the operation was successful.
    """
    if not os.path.exists(audioFilePath):
        print(Fore.RED+"Warning!","Audio file does not exist:", audioFilePath)
        print(Fore.YELLOW+"Skipping ID3 tagging...")
        return (f"Skipping ID3 tagging. Audio file {repr(audioFilePath)} does not exist.", False)

    if not data: data = {}

    try:
        audio = MP3(audioFilePath, ID3=ID3)
        coverInData = "thumbnail" in data
        cover = data.copy().pop("thumbnail", None)
        url = data.copy().pop("url", None)
        for tag, value in data.items():
            if tag in ID3_ALIASES:
                id3Tag = ID3_ALIASES[tag]
                tagText = value or f"[No {tag}]"
                print(Fore.MAGENTA+f"Adding {tag} tag:", tagText)
                audio.tags.add(id3Tag(encoding=3, text=[tagText]))
            else: print(Fore.YELLOW+"Warning!","Unknown tag:", tag)

        if url:
            print(Fore.MAGENTA+"Adding URL:", url)
            audio.tags.add(WOAS(encoding=3, url=url))

        # Cover path from either online or local source
        if coverInData:
            if cover:
                isLink = re.match(r"^https?://", cover)
                if isLink: cover = downloadThumbnail(cover)
                elif not os.path.exists(cover): cover = "NoCover.jpg"
                elif mimetypes.guess_type(cover)[0] != "image/jpeg":
                    newCover = changeFileExt(cover, "jpg")
                    convertToJpg(cover, newCover)
                    cover = newCover
            else: cover = "NoCover.jpg"

            print(Fore.MAGENTA+"Adding cover image:", cover)
            with open(cover, "rb") as img:
                audio.tags.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3, desc=u'Cover',
                    data=img.read()
                ))
            
            if cover != "NoCover.jpg":
                os.remove(cover)
                print(Fore.YELLOW+"Deleted Temp Thumbnail:", cover)
        
        audio.save()
        print(f"Tags added to {audioFilePath}")
        return ("success", True)
    except Exception as e:
        print(Fore.RED+f"Error adding tags to {audioFilePath}:", e)
        return (f"Tagging error with {repr(audioFilePath)} ~ "+str(e), False)

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
    response = requests.get(thumbnailURL)
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

# Input validation
def strInput(inputText: str) -> str:
    """Asks the user for input until a non-empty string is entered."""
    while not (string := input(inputText)): pass
    return string

def boolInput(inputText: str) -> bool:
    """Asks the user for input until a valid boolean value is entered."""
    return input(inputText).lower() in ["y","","yes","true"]


if __name__ == "__main__": # User inputs
    while True: # Keeps asking for input until a valid mode is entered
        mode = strInput("URL or JSON mode? (0 or 1): ")

        if mode not in ["0", "1"]: # Yes I know that I could probably make this a boolInput but this is incase I'd ever want to add more modes
            print(Fore.RED+"Invalid mode. Please enter 0 or 1.")
            continue
        
        print("Operations:")
        print("\td: Download audio\tt: Tag audio"+("\ts: Save tags" if mode == "0" else ""))
        downloadMethod = strInput("Include the letters for each of operation you want to perform: ").lower()
        downloading, tagging, saving = "d" in downloadMethod, "t" in downloadMethod, "s" in downloadMethod and mode == "0"
        
        if not (downloading or tagging or saving):
            print(Fore.RED+"No operations selected. Terminating...")
            break
        
        if tagging or saving:
            availableTags = list(ID3_ALIASES)
            print("Available tags:", *[f"\t{i+1}: {tag}" for i, tag in enumerate(availableTags)], sep="\n")
            selectedTags = strInput("Enter the tags you want to change: ")
            selectedTags = {i for i in range(1,len(availableTags)+1) if str(i) in selectedTags}
            changeableTags = [ availableTags[i-1] for i in selectedTags ]
        else: changeableTags = []

        if not (downloading or changeableTags): # Since this passed previous check, if downloading is false either tagging or saving must be true
            print(Fore.YELLOW + "Tagging or saving requires at least one tag to be changeable.")
            break
        
        arguments = { # There were too many arguments so I'm stuff them all in a dictionary
            "ytURL": strInput("Enter the YouTube playlist/video URL: ") if mode == "0" else None,
            "outputDir": strInput("Enter the directory to save the MP3 files: ") if mode == "0" else None,
            "saveFilePath": strInput("Enter the path of the JSON save file: ") if mode == "1" or saving else None,
            "downloading": downloading,
            "tagging": tagging,
            "saving": saving,
            "replacingFiles": boolInput("Replace existing files? (y/n): ") if downloading else False,
            "tagExisting": boolInput("tag existing files? (y/n): ") if mode == "1" and tagging else False,
            "changeableTags": changeableTags,
            "overwriteSave": boolInput("Overwrite data in save file? (y/n): ") if saving else False,
            "verboseSkipList": boolInput("Verbose skip list (show all operations skipped)? (y/n): ")
        }

        print("\n\n")
        if mode == "0": skipList = ytafURL(arguments)
        elif mode == "1": skipList = ytafJSON(arguments)

        if skipList: # Report skipped entries
            print()
            print(Fore.RED + f"The following {['videos', 'entries'][int(mode)]} had to be skipped:")
            for thing, error in skipList: print(f"\t{thing}:\t{error}")
        
        break