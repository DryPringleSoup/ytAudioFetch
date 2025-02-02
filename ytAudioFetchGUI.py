import sys, io
from functools import partial
from PyQt5 import QtWidgets, QtCore, QtGui
from ytAudioFetch import downloadAndTagAudio, downloadOrTagAudioWithJson, ID3_ALIASES

HOME_DIR = QtCore.QDir.homePath()

class FileBrowser(QtWidgets.QWidget):
    
    # getExistingDirectory returns string while getOpenFileName returns tuple so this normalize it to work with browse()
    BROWSE_TYPE = {
        "file": partial(QtWidgets.QFileDialog.getOpenFileName, caption="Select File", directory=HOME_DIR, filter="All Files (*)"),
        "folder": lambda self: (QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory", HOME_DIR), ""),
        "json": partial(QtWidgets.QFileDialog.getOpenFileName, caption="Select JSON File", directory=HOME_DIR, filter="JSON Files (*.json);;All Files (*)")
    }

    def __init__(self, type, placeholder="Enter path", parent=None):
        super().__init__(parent)

        # Create layout
        layout = QtWidgets.QHBoxLayout(self)

        # Folder input field
        self.folderInput = QtWidgets.QLineEdit(self)
        self.folderInput.setPlaceholderText(placeholder)
        layout.addWidget(self.folderInput)

        # Browse button
        self.browseButton = QtWidgets.QPushButton("🗁", self)
        self.browseButton.setFixedSize(40, 30)  # Adjust size if needed
        self.browseButton.clicked.connect(partial(self.browse, type))
        self.browseButton.setStyleSheet("QPushButton { font-weight: bold; }")
        layout.addWidget(self.browseButton)

        # Remove extra spacing
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
    
    def browse(self, type):
        """Opens a file dialog to select a something based on the type parameter."""
        path, _ = FileBrowser.BROWSE_TYPE[type](self)
        if path: self.folderInput.setText(path)

    def getPath(self):
        """Returns the selected folder path."""
        return self.folderInput.text()

# Custom class to capture printed output
class OutputCapture(io.StringIO):
    def __init__(self, label):
        super().__init__()
        self.label = label
        self.outputBuffer = ""  # Initialize the output buffer
        self.outputClear = False
        self.original_stdout = sys.stdout

    def write(self, message):
        # Store the newest message in the buffer
        # if there's a newline, clear the buffer
        if self.outputClear:
            if message.strip():
                self.outputBuffer = message
                self.outputClear = False
        else: self.outputBuffer += message
        if "\n" in message: self.outputClear = True
        if len(self.outputBuffer) >= 50: self.outputBuffer = self.outputBuffer[:50]+"..."
        
        #Write to console
        self.original_stdout.write(message)

        # Update the label with the new message
        self.label.setText("Output\n"+self.outputBuffer)

    def flush(self): pass  # Required for compatibility with some interfaces

class Worker(QtCore.QThread):
    outputSignal = QtCore.pyqtSignal(str)

    def __init__(self, mode = None, ytURL = None, outputDir = None, replacing = None, useLog = True, overwriteLog = None, jsonFilePath = None, download = None, changeableTags = None):
        super().__init__()
        self.mode = mode
        if mode.lower() == "url":
            self.ytURL = ytURL
            self.outputDir = outputDir
            self.replacing = replacing
            self.useLog = useLog
            self.overwriteLog = overwriteLog
        elif mode.lower() == "json":
            self.jsonFilePath = jsonFilePath
            self.download = download
            self.changeableTags = changeableTags
        else: raise ValueError(f"Invalid mode: {mode}")

    def run(self):       
        if self.mode.lower() == "url":
            downloadAndTagAudio(self.ytURL, self.outputDir, self.replacing, self.useLog)
            self.outputSignal.emit("Audio download completed.")
        elif self.mode.lower() == "json":
            downloadOrTagAudioWithJson(self.jsonFilePath, self.download, self.changeableTags)
            self.outputSignal.emit("JSON extraction completed.")

class YTAudioFetcherGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.useJson = True
        self.initUI()

    def initUI(self):
        # Set the window title and size
        self.setWindowTitle('YouTube Audio Fetch')
        self.setWindowIcon(QtGui.QIcon("ytaf.svg"))
        self.setMinimumWidth(600)

        # Center the window on the screen
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        windowSize = self.geometry()
        x = (screen.width() - windowSize.width()) // 2
        y = (screen.height() - windowSize.height()) // 2
        self.move(x, y)

        # Create layout
        layout = QtWidgets.QVBoxLayout()

        # URL and JSON mode toggle
        jsonToggleLayout = QtWidgets.QHBoxLayout()
        self.urlButton = QtWidgets.QPushButton("Use YouTube URL", self)
        self.urlButton.clicked.connect(self.toggleJsonSwitch)
        jsonToggleLayout.addWidget(self.urlButton)

        self.jsonButton = QtWidgets.QPushButton("Use JSON file", self)
        self.jsonButton.clicked.connect(self.toggleJsonSwitch)
        jsonToggleLayout.addWidget(self.jsonButton)

        layout.addLayout(jsonToggleLayout)

        self.urlModeGroup = QtWidgets.QGroupBox("URL", self)
        self.urlModeLayout = QtWidgets.QVBoxLayout()

        self.jsonModeGroup = QtWidgets.QGroupBox("JSON", self)
        self.jsonModeLayout = QtWidgets.QVBoxLayout()

        layout.addWidget(self.urlModeGroup)
        layout.addWidget(self.jsonModeGroup)

        # URL mode UI
        self.urlModeInitUI(self.urlModeLayout)
        self.urlModeGroup.setLayout(self.urlModeLayout)

        # JSON mode UI
        self.jsonModeInitUI(self.jsonModeLayout)
        self.jsonModeGroup.setLayout(self.jsonModeLayout)

        # Add a stretchable spacer item to absorb any extra vertical space
        layout.addStretch()

        # Download status
        self.statusLabel = QtWidgets.QLabel("", self)
        layout.addWidget(self.statusLabel)

        # Progress information
        self.progressLabel = QtWidgets.QLabel("Output:\n", self)
        layout.addWidget(self.progressLabel)
        # Redirect stdout to capture print statements
        self.outputCapture = OutputCapture(self.progressLabel)
        sys.stdout = self.outputCapture

        # Set layout and style
        self.toggleJsonSwitch()
        self.setLayout(layout)
        self.setStyleSheet("background-color: #1A082A; color: #FFFFFF; font-size: 20px;")
    
    def urlModeInitUI(self, layout):
        # URL input
        self.urlInput = QtWidgets.QLineEdit(self)
        self.urlInput.setPlaceholderText("Enter your YouTube playlist or video URL here")
        layout.addWidget(self.urlInput)

        # Output folder input and browse button
        self.urlOutputDirInput = FileBrowser("folder", "Enter the folder you want to save your MP3 files here", self)
        layout.addWidget(self.urlOutputDirInput)

        # Toggle Options button
        self.urlToggleOptionsButton = QtWidgets.QPushButton("Toggle Options", self)
        self.urlToggleOptionsButton.clicked.connect(self.toggleUrlOptions)
        layout.addWidget(self.urlToggleOptionsButton)

        # Group box for options
        self.urlOptionsGroup = QtWidgets.QGroupBox("Options:", self)
        self.urlOptionsLayout = QtWidgets.QVBoxLayout()
        
        # Replace existing files switch
        self.urlReplaceSwitch = QtWidgets.QCheckBox("Replace existing MP3 files", self)
        self.urlOptionsLayout.addWidget(self.urlReplaceSwitch)

        # Use log files switch
        self.urlLogSwitch = QtWidgets.QCheckBox("Use log file for tag data", self)
        self.urlLogSwitch.setChecked(True)  # Set the checkbox to be checked by default
        self.urlOptionsLayout.addWidget(self.urlLogSwitch)

        # Overwrite log files switch
        self.urlOverwriteSwitch = QtWidgets.QCheckBox("Overwrite data in log file", self)
        self.urlOptionsLayout.addWidget(self.urlOverwriteSwitch)

        self.urlOptionsGroup.setLayout(self.urlOptionsLayout)
        self.urlOptionsGroup.setVisible(False)  # Initially hide the options group
        layout.addWidget(self.urlOptionsGroup)

        # Start button
        self.urlStartButton = QtWidgets.QPushButton("Start Download", self)
        self.urlStartButton.clicked.connect(self.startURLDownload)
        layout.addWidget(self.urlStartButton)
    
    def jsonModeInitUI(self, layout):
        # JSON file input
        self.jsonInput = FileBrowser("json", "Enter the path of the JSON File you want to use", self)
        layout.addWidget(self.jsonInput)

        # Options button
        self.jsonToggleOptionsButton = QtWidgets.QPushButton("Toggle Options", self)
        self.jsonToggleOptionsButton.clicked.connect(self.toggleJsonOptions)
        layout.addWidget(self.jsonToggleOptionsButton)

        # Group box for options
        self.jsonOptionsGroup = QtWidgets.QGroupBox("Options:", self)
        self.jsonOptionsLayout = QtWidgets.QVBoxLayout()
        
        # Download audio switch
        self.jsonDownloadSwitch = QtWidgets.QCheckBox("Download audio", self)
        self.jsonDownloadSwitch.setChecked(True)
        self.jsonOptionsLayout.addWidget(self.jsonDownloadSwitch)

        # Changeable tags switch
        self.jsonTagSelectionLabel = QtWidgets.QLabel("Select tags to extract", self)
        self.jsonOptionsLayout.addWidget(self.jsonTagSelectionLabel)

        jsonTagSelectionLayout = QtWidgets.QHBoxLayout()
        self.jsonUrlSwitch = QtWidgets.QCheckBox("URL", self)
        self.jsonUrlSwitch.setChecked(True)
        self.jsonOptionsLayout.addWidget(self.jsonUrlSwitch)
        jsonTagSelectionLayout.addWidget(self.jsonUrlSwitch)

        self.jsonTitleSwitch = QtWidgets.QCheckBox("Title", self)
        self.jsonTitleSwitch.setChecked(True)
        self.jsonOptionsLayout.addWidget(self.jsonTitleSwitch)
        jsonTagSelectionLayout.addWidget(self.jsonTitleSwitch)

        self.jsonArtistSwitch = QtWidgets.QCheckBox("Artist", self)
        self.jsonArtistSwitch.setChecked(True)
        self.jsonOptionsLayout.addWidget(self.jsonArtistSwitch)
        jsonTagSelectionLayout.addWidget(self.jsonArtistSwitch)

        self.jsonThumbnailSwitch = QtWidgets.QCheckBox("Thumbnail", self)
        self.jsonThumbnailSwitch.setChecked(True)
        self.jsonOptionsLayout.addWidget(self.jsonThumbnailSwitch)
        jsonTagSelectionLayout.addWidget(self.jsonThumbnailSwitch)

        self.jsonOptionsLayout.addLayout(jsonTagSelectionLayout)

        self.jsonOptionsGroup.setLayout(self.jsonOptionsLayout)
        self.jsonOptionsGroup.setVisible(False)  # Initially hide the options group
        layout.addWidget(self.jsonOptionsGroup)

        # Start button
        self.jsonStartButton = QtWidgets.QPushButton("Start Extraction", self)
        self.jsonStartButton.clicked.connect(self.startJsonExtract)
        layout.addWidget(self.jsonStartButton)

    def toggleUrlOptions(self):
        self.urlOptionsGroup.setVisible(not self.urlOptionsGroup.isVisible())
    
    def toggleJsonOptions(self):
        self.jsonOptionsGroup.setVisible(not self.jsonOptionsGroup.isVisible())
    
    def startURLDownload(self):
        ytURL = self.urlInput.text()
        outputDir = self.urlOutputDirInput.getPath()
        replacing = self.urlReplaceSwitch.isChecked()
        useLog = self.urlLogSwitch.isChecked()
        overwriteLog = self.urlOverwriteSwitch.isChecked()

        if not ytURL or not outputDir:
            self.statusLabel.setText("Please fill in all fields.")
            return

        self.statusLabel.setText("Downloading...")
        QtWidgets.QApplication.processEvents()

        # Create a worker thread
        self.worker = Worker(mode="url", ytURL=ytURL, outputDir=outputDir, replacing=replacing, useLog=useLog, overwriteLog=overwriteLog)
        self.worker.outputSignal.connect(self.updateLabel)
        self.worker.start()
    
    def startJsonExtract(self):
        jsonFile = self.jsonInput.getPath()
        download = self.jsonDownloadSwitch.isChecked()
        changeableTags = [tag for tag in ID3_ALIASES.keys() if eval(f"self.json{tag.capitalize()}Switch.isChecked()")]

        if not jsonFile:
            self.statusLabel.setText("Please fill in all fields.")
            return

        self.statusLabel.setText("Extracting...")
        QtWidgets.QApplication.processEvents()

        # Create a worker thread
        self.worker = Worker(mode="json", jsonFilePath=jsonFile, download=download, changeableTags=changeableTags)
        self.worker.outputSignal.connect(self.updateLabel)
        self.worker.start()

    def updateLabel(self, message=None):
        # Update the label with the current output buffer
        self.progressLabel.setText("Output:\n" + self.outputCapture.outputBuffer)
        if message: self.statusLabel.setText(message)
    
    def toggleJsonSwitch(self):
        """Makes the button transparent but keeps its text grayed out."""
        selected = "QPushButton {}"
        deselected = """
                QPushButton {
                    background-color: rgba(110, 90, 130, 20);
                    border: none;
                    color: gray;
                }
        """
        self.useJson = not self.useJson
        self.urlButton.setStyleSheet(deselected if self.useJson else selected)
        self.jsonButton.setStyleSheet(selected if self.useJson else deselected)
        self.urlModeGroup.setVisible(not self.useJson)
        self.jsonModeGroup.setVisible(self.useJson)
        self.adjustSize()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = YTAudioFetcherGUI()
    window.show()
    sys.exit(app.exec_())