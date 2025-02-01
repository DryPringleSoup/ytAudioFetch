import sys, io
from PyQt5 import QtWidgets, QtCore
from ytAudioFetch import downloadAndTagAudio, downloadOrTagAudioWithJson, ID3_ALIASES

class FolderSelector(QtWidgets.QWidget):
    def __init__(self, placeholder="Enter folder path", parent=None):
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
        self.browseButton.clicked.connect(self.browseFolder)
        layout.addWidget(self.browseButton)

        # Remove extra spacing
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

    def browseFolder(self):
        """Opens a folder selection dialog and updates the text field."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.folderInput.setText(folder)

    def getFolderPath(self):
        """Returns the selected folder path."""
        return self.folderInput.text()

# Custom class to capture printed output
class OutputCapture(io.StringIO):
    def __init__(self, label):
        super().__init__()
        self.label = label
        self.output_buffer = ""  # Initialize the output buffer
        self.output_clear = False

    def write(self, message):
        # Store the newest message in the buffer
        # if there's a newline, clear the buffer
        if self.output_clear:
            if message.strip():
                self.output_buffer = message
                self.output_clear = False
        else: self.output_buffer += message
        if "\n" in message: self.output_clear = True
        if len(self.output_buffer) >= 50: self.output_buffer = self.output_buffer[:50]+"..." 

        # Update the label with the new message
        self.label.setText("Output\n"+self.output_buffer)

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
        self.setGeometry(0, 0, 600, 600)

        # Center the window on the screen
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
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

        # Download status
        self.statusLabel = QtWidgets.QLabel("", self)
        layout.addWidget(self.statusLabel)

        # Progress information
        self.progressLabel = QtWidgets.QLabel("Output:\n", self)
        layout.addWidget(self.progressLabel)
        # Redirect stdout to capture print statements
        self.output_capture = OutputCapture(self.progressLabel)
        sys.stdout = self.output_capture

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
        self.urlOutputDirInput = FolderSelector("Enter the folder you want to save your MP3 files here", self)
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
        self.jsonInput = FolderSelector("Enter the path of the JSON File you want to use", self)
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
        self.jsonStartButton = QtWidgets.QPushButton("Start Download", self)
        self.jsonStartButton.clicked.connect(self.startJsonExtract)
        layout.addWidget(self.jsonStartButton)

    def toggleUrlOptions(self):
        self.urlOptionsGroup.setVisible(not self.urlOptionsGroup.isVisible())
    
    def toggleJsonOptions(self):
        self.jsonOptionsGroup.setVisible(not self.jsonOptionsGroup.isVisible())

    def browseFolder(self):
        # Open a dialog to select a directory
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder: self.outputDirInput.setText(folder)
    
    def browseJsonFile(self):
        """Opens a file dialog to select a JSON file and updates the text field."""
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select JSON File", "", "JSON Files (*.json);;All Files (*)")

        if file_path:
            self.outputDirInput.setText(file_path)  # Update input field with selected JSON file path
    
    def startURLDownload(self):
        ytURL = self.urlInput.text()
        outputDir = self.urlOutputDirInput.getFolderPath()
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
        jsonFile = self.jsonInput.getFolderPath()
        download = self.jsonDownloadSwitch.isChecked()
        changeableTags = [tag for tag in ID3_ALIASES.keys() if eval("self.json{tag.capitalize()}Switch.isChecked()")]

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
        self.progressLabel.setText("Output:\n" + self.output_capture.output_buffer)
        if message: self.statusLabel.setText(message)
    
    def toggleJsonSwitch(self):
        """Makes the button transparent but keeps its text grayed out."""
        selected = "QPushButton {}"
        deselected = """
                QPushButton {
                    background-color: transparent; /* Hide button body */
                    border: none; /* Remove border */
                    color: gray; /* Gray out text */
                }
        """

        if self.useJson:
            self.useJson = False
            self.urlButton.setStyleSheet(selected)
            self.jsonButton.setStyleSheet(deselected)
            self.urlModeGroup.setVisible(True)
            self.jsonModeGroup.setVisible(False)
        else:
            self.useJson = True
            self.urlButton.setStyleSheet(deselected)
            self.jsonButton.setStyleSheet(selected)
            self.urlModeGroup.setVisible(False)
            self.jsonModeGroup.setVisible(True)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = YTAudioFetcherGUI()
    window.show()
    sys.exit(app.exec_())