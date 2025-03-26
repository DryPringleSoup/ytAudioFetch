import sys, re, os, webbrowser
from functools import partial
from PyQt5 import QtWidgets, QtCore, QtGui
from colorama import Fore
from ytAudioFetch import ytafURL, ytafJSON, ID3_ALIASES, HOME_DIR

def strikeText(self, event): # QtLineEdit and QtCheckBox don't use strike through so this is a workaround
    super(type(self), self).paintEvent(event)
    if not self.isEnabled():  # Only apply strikethrough when disabled
        painter = QtGui.QPainter(self)
        pen = QtGui.QPen(self.palette().color(self.foregroundRole()))
        pen.setWidth(2)
        painter.setPen(pen)

        text_rect = self.fontMetrics().boundingRect(self.text())
        y = self.rect().center().y()
        painter.drawLine(text_rect.left(), y, text_rect.right()+20, y)

# Custom Widgets
class StrikableLineEdit(QtWidgets.QLineEdit): paintEvent = strikeText
class StrikableCheckBox(QtWidgets.QCheckBox): paintEvent = strikeText

class FileBrowser(QtWidgets.QWidget):
    
    # getExistingDirectory returns string while getOpenFileName returns tuple so this normalize it to work with browse()
    browseType = {
        "file": partial(QtWidgets.QFileDialog.getOpenFileName, caption="Select File", directory=HOME_DIR, filter="All Files (*)"),
        "folder": lambda self: (QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory", HOME_DIR), ""),
        "json": partial(QtWidgets.QFileDialog.getOpenFileName, caption="Select JSON File", directory=HOME_DIR, filter="JSON Files (*.json);;All Files (*)")
    }

    def __init__(self, browseType, placeholder = "Enter path", parent=None):
        super().__init__(parent)

        # Create layout
        layout = QtWidgets.QHBoxLayout(self)

        # Folder input field
        self.folderInput = StrikableLineEdit(self)
        self.folderInput.setPlaceholderText(placeholder)
        layout.addWidget(self.folderInput)

        # Browse button
        self.browseButton = QtWidgets.QPushButton("🗁", self)
        self.browseButton.setFixedSize(40, 30)  # Adjust size if needed
        self.browseButton.clicked.connect(partial(self.browse, browseType))
        self.browseButton.setStyleSheet("QPushButton { font-weight: bold; }")
        layout.addWidget(self.browseButton)

        # Remove extra spacing
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
    
    def browse(self, browseType):
        """Opens a file dialog to select a something based on the type parameter."""
        path, _ = FileBrowser.browseType[browseType](self)
        if path: self.folderInput.setText(path)

    def setPath(self, path):
        """Sets the selected folder path."""
        self.folderInput.setText(path)

    def getPath(self):
        """Returns the selected folder path."""
        return self.folderInput.text()
    
    def setPlaceholderText(self, placeholder):
        self.folderInput.setPlaceholderText(placeholder)

# Processing
class OutputCapture(QtCore.QObject):
    textUpdated = QtCore.pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.outputBuffer = ""  # buffer for output label
        self.original_stdout = sys.stdout # console

    def write(self, message):
        # Write the message to the original stdout (console)
        self.original_stdout.write(message)

        if message == "\n": self.outputBuffer = "" # reset buffer if new line
        else:
            if message.endswith("\n"): self.outputBuffer = message[:-1]
            else: self.outputBuffer += message

            # Remove ANSI color codes
            for color in [Fore.RED, Fore.GREEN, Fore.BLUE, Fore.MAGENTA, Fore.YELLOW]: self.outputBuffer = self.outputBuffer.replace(color, "")
            
            # Update the label with the new message
            self.textUpdated.emit(self.outputBuffer)
    
    def flush(self): pass  # Required for compatibility with some interfaces

class Worker(QtCore.QThread):
    outputSignal = QtCore.pyqtSignal(str)

    def __init__(self, mode, arguments):
        super().__init__()
        self.mode = mode
        self.arguments = arguments

    def run(self):
        try:
            if self.mode == 0: skipList = ytafURL(self.arguments)
            elif self.mode == 1: skipList = ytafJSON(self.arguments)
            else: raise ValueError(f"Invalid mode: {self.mode}")

            if skipList:
                skipString = ''.join([f"\n\t{thing}:\t{error}" for thing, error in skipList])
                self.outputSignal.emit(f"The following had to be skipped:{skipString}")
            else: self.outputSignal.emit("Process completed without failure.")
        except Exception as e: self.outputSignal.emit(f"An error occurred: {e}")

        self.finished.emit()

#GUI
class YTAudioFetcherGUI(QtWidgets.QWidget):
    baseStyleSheet = """
    QWidget { font-size: 9pt; }
    QWidget:disabled, QPushButton#shade {
        background-color: rgba(110, 90, 130, 20);
        border: none;
        color: gray;
    }
    QScrollArea { border: none; }
    QTextEdit {
        background-color: transparent;
        border: None
    }
    """
    lightMode = baseStyleSheet
    darkMode = baseStyleSheet[:15]+"background-color: #1A082A; color: #FFFFFF;"+baseStyleSheet[15:] # puts the style in after "\nQwidget { "
    scriptModes = 2
    isProcessing = False

    def __init__(self):
        self.scriptMode = 0
        self.isDarkMode = False
        super().__init__()
        self.initUI() # Initialize all the widgets in the UI
        self.setScriptMode(self.scriptMode) # Properly sets the look of the mode
    
    def initUI(self):
        # Set the window title and size
        self.setWindowTitle('YouTube Audio Fetch')
        self.setWindowIcon(QtGui.QIcon("ytaf.svg"))
        self.setMinimumWidth(400)

        # Center the window on the screen
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        windowSize = self.geometry()
        x = (screen.width() - windowSize.width()) // 2
        y = (screen.height() - windowSize.height()) // 2
        self.move(x, y)

        # Create layout
        self.layout = QtWidgets.QVBoxLayout()

        # Mode toggle buttons: They really just do the same thing (toggling the mode); the buttons really show which mode is active
        self.scriptModeToggleLayout = QtWidgets.QHBoxLayout()
        scriptModeSwitch = lambda: self.setScriptMode((self.scriptMode + 1) % YTAudioFetcherGUI.scriptModes)

        self.urlButton = QtWidgets.QPushButton("Youtube URL", self)
        self.urlButton.clicked.connect(scriptModeSwitch)
        self.scriptModeToggleLayout.addWidget(self.urlButton)

        self.jsonButton = QtWidgets.QPushButton("JSON file", self)
        self.jsonButton.clicked.connect(scriptModeSwitch)
        self.scriptModeToggleLayout.addWidget(self.jsonButton)

        self.layout.addLayout(self.scriptModeToggleLayout)

        # Mode label and help button
        self.scriptModeInfoLayout = QtWidgets.QHBoxLayout()

        self.scriptModeLabel = QtWidgets.QLabel(self)
        self.scriptModeInfoLayout.addWidget(self.scriptModeLabel, 1)

        self.helpButton = QtWidgets.QPushButton("?", self)
        self.helpButton.setFixedSize(20, 20)
        self.helpButton.setStyleSheet("font-weight: bold;")
        self.helpButton.clicked.connect(lambda: webbrowser.open("help.html"))
        self.scriptModeInfoLayout.addWidget(self.helpButton)

        self.layout.addLayout(self.scriptModeInfoLayout)

        #layout for the actual input fields
        self.scriptModeLayout = QtWidgets.QVBoxLayout()

        # URL input field
        self.urlInput = StrikableLineEdit(self)
        self.urlInput.setPlaceholderText("Enter your YouTube playlist or video URL here")
        self.scriptModeLayout.addWidget(self.urlInput)

        # File browser for output directory
        self.outputDirInput = FileBrowser("folder", "Enter the folder you want to save your MP3 files here", self)
        self.scriptModeLayout.addWidget(self.outputDirInput)
        
        # Menu for extra settings
        self.initOptionsMenu()
        self.optionsGroup.setVisible(False)

        self.startButton = QtWidgets.QPushButton("𝙎 𝙏 𝘼 𝙍 𝙏", self)
        self.startButton.clicked.connect(self.startYTDLP)
        self.scriptModeLayout.addWidget(self.startButton)
        
        # Using a QTextEdit instead of QLabel because it allows for scrolling and text highlighing/copying
        self.statusLabel = QtWidgets.QTextEdit(self)
        self.statusLabel.setReadOnly(True)  # Make the text read-only
        self.statusLabel.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.statusLabel.setMinimumHeight(50)  # Adjust this value as needed
        self.statusLabel.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Ignored)
        self.scriptModeLayout.addWidget(self.statusLabel,1)

        self.outputLabel = QtWidgets.QLabel("Output:", self)
        self.scriptModeLayout.addWidget(self.outputLabel)

        self.scriptModeGroup = QtWidgets.QGroupBox(self)
        self.scriptModeGroup.setLayout(self.scriptModeLayout)
        self.layout.addWidget(self.scriptModeGroup)

        # Redirect stdout to capture print statements
        self.outputCapture = OutputCapture()
        self.outputCapture.textUpdated.connect(self.outputConsole2Labels, QtCore.Qt.QueuedConnection)
        sys.stdout = self.outputCapture

        self.setLayout(self.layout)
    
    def setScriptMode(self, scriptMode):
        self.scriptModeLayout.removeWidget(self.saveFilePathInput)
        urlModeSpecificWidgets = [
            self.urlInput,
            self.outputDirInput,
            self.operationSwitchsDict["save tags"],
            self.tagExistingSwitch,
            self.overwriteSavesSwitch,
            self.saveFilePathInputLabel
        ]

        if scriptMode == 0:
            self.urlButton.setObjectName("")
            self.jsonButton.setObjectName("shade")
            self.scriptModeLabel.setText("Download, tag, and/or save audio from YouTube")
            
            for widget in urlModeSpecificWidgets: widget.setVisible(True)

            self.optionsLayout.addWidget(self.saveFilePathInput)
            self.saveFilePathInput.setPlaceholderText("Enter the path of the save file you want to save to")
        else:
            self.urlButton.setObjectName("shade")
            self.jsonButton.setObjectName("")
            self.scriptModeLabel.setText("Download and/or tag audio from JSON")

            for widget in urlModeSpecificWidgets: widget.setVisible(False)

            self.scriptModeLayout.insertWidget(0,self.saveFilePathInput)
            self.saveFilePathInput.setPlaceholderText("Enter the path of the save file you want to extract from")
        
        # makes it so that already inputted paths in each save don't get lost when switching
        self.saveFilePathsHidden[self.scriptMode] = self.saveFilePathInput.getPath()
        self.saveFilePathInput.setPath(self.saveFilePathsHidden[scriptMode])

        self.scriptMode = scriptMode
        self.updateOptions()
        self.setThemeMode(self.isDarkMode)
        self.verticalCollapse()
    
    def updateOptions(self):
        downloading = self.operationSwitchsDict["download audio"].isChecked()
        tagging = self.operationSwitchsDict["tag audio"].isChecked()
        saving = self.operationSwitchsDict["save tags"].isChecked()
        extracting = (self.scriptMode == 0 and (tagging or saving)) or (self.scriptMode == 1 and tagging)
        shouldGetCover = tagging and self.tagSwitchsDict["thumbnail"].isChecked()

        self.replaceFilesSwitch.setEnabled(downloading)
        self.tagExistingSwitch.setEnabled(tagging)
        self.tagSelectionLabel.setEnabled(extracting)
        self.tagsGroup.setEnabled(extracting)
        self.coverOptionsGroup.setEnabled(shouldGetCover)
        self.showCoverOptionsButton.setStyleSheet("" if shouldGetCover else "text-decoration: line-through;")
        self.overwriteSavesSwitch.setEnabled(saving)
        self.saveFilePathInputLabel.setEnabled(saving)
        self.saveFilePathInput.setEnabled(saving or self.scriptMode == 1)

        if not (downloading or extracting):
            self.startButton.setDisabled(True)
            self.statusLabel.setText("At least one operation must be selected")
        elif not YTAudioFetcherGUI.isProcessing:
            self.startButton.setDisabled(False)
            self.statusLabel.setText("")
    
    def verticalCollapse(self):
        width = self.width()
        self.adjustSize()
        self.resize(width, self.height())

    def initOptionsMenu(self):
        # Options button
        self.optionsButton = QtWidgets.QPushButton("Advanced Options", self)
        self.optionsButton.clicked.connect(lambda: self.optionsGroup.setVisible(not self.optionsGroup.isVisible()))
        self.scriptModeLayout.addWidget(self.optionsButton)

        # Options menu layout
        self.optionsLayout = QtWidgets.QVBoxLayout()

        self.darkModeToggle = QtWidgets.QRadioButton("dark mode", self)
        self.darkModeToggle.setChecked(self.isDarkMode)
        self.darkModeToggle.clicked.connect(self.toggleThemeMode)
        self.optionsLayout.addWidget(self.darkModeToggle)

        self.verboseSkipListSwitch = StrikableCheckBox("show ALL operations that were skipped (false = show only skipped downloads)", self)
        self.optionsLayout.addWidget(self.verboseSkipListSwitch)

        self.initOperationsCheckList() # checks for downloading, tagging, and saving

        self.replaceFilesSwitch = StrikableCheckBox("replace existing files", self)
        self.optionsLayout.addWidget(self.replaceFilesSwitch)

        self.tagExistingSwitch = StrikableCheckBox("tag existing files", self)
        self.optionsLayout.addWidget(self.tagExistingSwitch)

        self.tagSelectionLabel = QtWidgets.QLabel("Select tags to extract:", self)
        self.optionsLayout.addWidget(self.tagSelectionLabel)

        self.initTagsCheckList() # lists of ID3 tags that are supported to be tagged or saved
        self.tagSwitchsDict["thumbnail"].setText("thumbnail (cover)")
        self.tagSwitchsDict["thumbnail"].toggled.connect(self.updateOptions)

        self.initCoverOptions() # all cover options
        self.coverOptionsGroup.setVisible(False)

        self.overwriteSavesSwitch = StrikableCheckBox("Overwrite data in save file", self)
        self.optionsLayout.addWidget(self.overwriteSavesSwitch)

        self.saveFilePathInputLabel = QtWidgets.QLabel("File to save to:", self)
        self.optionsLayout.addWidget(self.saveFilePathInputLabel)

        # File Browser for save file
        self.saveFilePathInput = FileBrowser("json", parent=self)
        self.saveFilePathsHidden = [ os.path.join(HOME_DIR, "ytAudioFetchSave.json"), "" ]
        self.saveFilePathInput.setPath(self.saveFilePathsHidden[self.scriptMode])
        self.optionsLayout.addWidget(self.saveFilePathInput)

        self.optionsGroup = QtWidgets.QGroupBox("Options:", self)
        self.optionsGroup.setLayout(self.optionsLayout)
        self.scriptModeLayout.addWidget(self.optionsGroup)
    
    def toggleThemeMode(self):
        self.isDarkMode = not self.isDarkMode
        self.setThemeMode(self.isDarkMode)

    def setThemeMode(self, darkMode):
        self.setStyleSheet(YTAudioFetcherGUI.darkMode if darkMode else YTAudioFetcherGUI.lightMode)
    
    def initOperationsCheckList(self):    
        # Operations layout
        self.operationsLayout = QtWidgets.QHBoxLayout()

        self.operationSwitchsDict = { opt: StrikableCheckBox(opt, self) for opt in ["download audio", "tag audio", "save tags"] }
        for optSwitch in self.operationSwitchsDict.values():
            optSwitch.setChecked(True)
            optSwitch.toggled.connect(self.updateOptions)
            self.operationsLayout.addWidget(optSwitch)

        self.operationsGroup = QtWidgets.QGroupBox(self)
        self.operationsGroup.setStyleSheet("border: none;")
        self.operationsGroup.setLayout(self.operationsLayout)
        self.optionsLayout.addWidget(self.operationsGroup)
    
    def initTagsCheckList(self):    
        # Operations layout
        self.tagsLayout = QtWidgets.QGridLayout()
        columns = 3

        self.tagSwitchsDict = { tag: StrikableCheckBox(tag, self) for tag in ID3_ALIASES }
        for i, tagSwitch in enumerate(self.tagSwitchsDict.values()):
            tagSwitch.setChecked(True)
            self.tagsLayout.addWidget(tagSwitch, i // columns, i % columns)

        self.tagsGroup = QtWidgets.QGroupBox(self)
        self.tagsGroup.setStyleSheet("border: none;")
        self.tagsGroup.setLayout(self.tagsLayout)
        self.optionsLayout.addWidget(self.tagsGroup)

        self.tagRequests = list(ID3_ALIASES)
    
    def initCoverOptions(self):
        self.showCoverOptionsButton = QtWidgets.QPushButton("Cover Tagging Options", self)
        self.showCoverOptionsButton.clicked.connect(lambda: self.coverOptionsGroup.setVisible(not self.coverOptionsGroup.isVisible()))
        self.optionsLayout.addWidget(self.showCoverOptionsButton)

        self.coverOptionsLayout = QtWidgets.QVBoxLayout()

        self.clearCoversSwitch = QtWidgets.QCheckBox("Clear existing covers", self)
        self.clearCoversSwitch.setChecked(True)
        self.coverOptionsLayout.addWidget(self.clearCoversSwitch)

        self.coverDirInput = FileBrowser("folder", "Enter folder to save covers to", parent=self)
        self.coverOptionsLayout.addWidget(self.coverDirInput)
        
        self.initcoverQualityOption(self.coverOptionsLayout) # slider for thumbnail coverQuality

        self.coverOptionsGroup = QtWidgets.QGroupBox(self)
        self.coverOptionsGroup.setLayout(self.coverOptionsLayout)
        self.optionsLayout.addWidget(self.coverOptionsGroup)

    def initcoverQualityOption(self, layout):
        # add value label and warning laid out horizontally
        self.coverQualityInfoLayout = QtWidgets.QHBoxLayout()
        self.coverQualityInfoLayout.setContentsMargins(0, 0, 0, 0)

        self.coverQualitySliderLabel = QtWidgets.QLabel(self)
        self.coverQualityInfoLayout.addWidget(self.coverQualitySliderLabel, 1)

        self.coverQualityWarningLabel = QtWidgets.QLabel("*Qualities above 95 have diminishing returns and may make large files sizes", self)
        self.coverQualityWarningLabel.setStyleSheet("font-size: 7pt;") # smaller font
        self.coverQualityWarningLabel.setVisible(False)
        self.coverQualityInfoLayout.addWidget(self.coverQualityWarningLabel)

        layout.addLayout(self.coverQualityInfoLayout)

        # add slider, end labels, and buttons laid out vertically
        self.coverQualitySliderLayout = QtWidgets.QHBoxLayout()
        self.coverQualitySliderLayout.setContentsMargins(0, 0, 0, 0)
        
        self.coverQualityDownButton = QtWidgets.QPushButton("◄", self)
        self.coverQualityDownButton.setFixedSize(30, 30)
        self.coverQualityDownButton.clicked.connect(lambda: self.coverQualitySlider.setValue(self.coverQualitySlider.value() - 1))
        self.coverQualityDownButton.setStyleSheet("border: none;")
        self.coverQualityDownButton.setAutoRepeat(True)
        self.coverQualityDownButton.setAutoRepeatDelay(400)
        self.coverQualityDownButton.setAutoRepeatInterval(80)
        self.coverQualitySliderLayout.addWidget(self.coverQualityDownButton)

        self.coverQualitySliderMinimumLabel = QtWidgets.QLabel("0", self)
        self.coverQualitySliderLayout.addWidget(self.coverQualitySliderMinimumLabel)

        self.coverQualitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.coverQualitySlider.setMinimum(0)
        self.coverQualitySlider.setMaximum(100)
        self.coverQualitySlider.valueChanged.connect(self.setcoverQuality)
        self.coverQualitySlider.setValue(75)
        self.coverQualitySlider.setTickInterval(10)
        self.coverQualitySlider.setTickPosition(QtWidgets.QSlider.TicksBothSides)
        self.coverQualitySlider.setStyleSheet("QSlider::handle:horizontal { background: white; border: 1px solid #aaa; border-radius: 3px; }")
        self.coverQualitySliderLayout.addWidget(self.coverQualitySlider)
        
        self.coverQualitySliderMaximumLabel = QtWidgets.QLabel("100", self)
        self.coverQualitySliderLayout.addWidget(self.coverQualitySliderMaximumLabel)

        self.coverQualityUpButton = QtWidgets.QPushButton("►", self)
        self.coverQualityUpButton.setFixedSize(30, 30)
        self.coverQualityUpButton.setStyleSheet("border: none;")
        self.coverQualityUpButton.clicked.connect(lambda: self.coverQualitySlider.setValue(self.coverQualitySlider.value() + 1))
        self.coverQualityUpButton.setAutoRepeat(True)
        self.coverQualityUpButton.setAutoRepeatDelay(400)
        self.coverQualityUpButton.setAutoRepeatInterval(80)
        self.coverQualitySliderLayout.addWidget(self.coverQualityUpButton)

        layout.addLayout(self.coverQualitySliderLayout)
    
    def setcoverQuality(self):
        self.coverQualitySliderLabel.setText(f"Cover Compression Quality: {self.coverQualitySlider.value()}")
        if self.coverQualitySlider.value() > 95:
            self.coverQualityWarningLabel.setVisible(True)
            self.coverQualitySlider.setStyleSheet("""
            QSlider::sub-page:horizontal {
                background: red;
                height: 7px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #aaa;
                border-radius: 3px;
            }
            """)
        else:
            self.coverQualitySlider.setStyleSheet("QSlider::handle:horizontal { background: white; border: 1px solid #aaa; border-radius: 3px; }")
            self.coverQualityWarningLabel.setVisible(False)
    
    def startYTDLP(self):
        #Input validation
        ytURL = self.urlInput.text()
        outputDir = self.outputDirInput.getPath()
        saveFilePath = self.saveFilePathInput.getPath() if self.saveFilePathInput.isEnabled() else ""

        if self.scriptMode == 0 and not (ytURL and outputDir):
            self.statusLabel.setText("Please fill in all fields.")
            return

        elif self.scriptMode == 1 and not saveFilePath:
            self.statusLabel.setText("Please fill in all fields.")
            return
        
        downloading = self.operationSwitchsDict["download audio"].isChecked()
        tagging = self.operationSwitchsDict["tag audio"].isChecked()
        saving = self.operationSwitchsDict["save tags"].isChecked() if self.scriptMode == 0 else False
        extracting = (self.scriptMode == 0 and (tagging or saving)) or (self.scriptMode == 1 and tagging)

        if not (downloading or extracting): # technically this is redundant due to self.updateOptions but just in case
            self.statusLabel.setText("At least one operation must be selected")
            return

        # enabled check is also redundant here because it is only enabled if you aren't extracting and so not
        # referencing the changeableTags list. It's more or less just to skip the check if you aren't extracting
        changeableTags = [ tag for tag in ID3_ALIASES if self.tagSwitchsDict[tag].isChecked() ] if self.tagsGroup.isEnabled() else []

        if extracting and not changeableTags:
            self.statusLabel.setText("Please select at least one tag to extract.")
            return

        # Not checking for enabled here because the script is already not gonna use these if they aren't enabled
        # The disabling in the GUI is essentially just for the user to see what is and isn't getting used in the script
        replacingFiles = self.replaceFilesSwitch.isChecked()
        tagExisting = self.tagExistingSwitch.isChecked()
        
        clearCovers = self.clearCoversSwitch.isChecked()
        coverDir = self.coverDirInput.getPath()
        coverQuality = self.coverQualitySlider.value()
        
        overwriteSave = self.overwriteSavesSwitch.isChecked()
        verboseSkipList = self.verboseSkipListSwitch.isChecked()

        arguDict = {
            "ytURL": ytURL,
            "outputDir": outputDir,
            "saveFilePath": saveFilePath,
            "downloading": downloading,
            "tagging": tagging,
            "saving": saving,
            "replacingFiles": replacingFiles,
            "tagExisting": tagExisting,
            "changeableTags": changeableTags,
            "clearCovers": clearCovers,
            "coverDir": coverDir,
            "coverQuality": coverQuality,
            "overwriteSave": overwriteSave,
            "verboseSkipList": verboseSkipList
        }

        print(*[f"{k}: {v}" for k, v in arguDict.items()], sep="\n")

        self.startButton.setDisabled(True)
        YTAudioFetcherGUI.isProcessing = True
        self.statusLabel.setText("Processing...")
        QtWidgets.QApplication.processEvents() # used to force the GUI to update because updates happen every GUI event loop when this for loop blocks

        # Create a worker thread
        self.worker = Worker(self.scriptMode, arguDict)
        self.worker.outputSignal.connect(self.statusLabel.setText, QtCore.Qt.QueuedConnection)
        self.worker.finished.connect(self.renableStartButton)
        self.worker.start()
    
    # Thread emit functions

    def outputConsole2Labels(self, output):
        # Update status label with video index
        # regex checks for "['Video' or 'JSON entry'] [num] of [num]"
        output = output.strip()

        # Truncate the buffer
        truncateLength = 80
        if len(output) >= truncateLength: output = output[:truncateLength]+"..."

        bufferMatch = re.search(r"(?:Video|JSON entry) \d+ of \d+ - .*", output)
        if bufferMatch: self.statusLabel.setText("Processing: " + bufferMatch.group(0))
        elif not (output.startswith("Video ") or output.startswith("JSON entry ")): self.outputLabel.setText("Output:\n"+output)

    def renableStartButton(self):
        self.startButton.setEnabled(True)
        YTAudioFetcherGUI.isProcessing = False


if __name__ == '__main__':
    try:
        app = QtWidgets.QApplication(sys.argv)
        window = YTAudioFetcherGUI()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        errorDialog = QtWidgets.QMessageBox()
        errorDialog.setText("An error occurred: " + str(e))
        errorDialog.setIcon(QtWidgets.QMessageBox.Critical)
        errorDialog.exec_()