import sys
import io
from PyQt5 import QtWidgets, QtCore
from ytAudioFetch import downloadAndTagAudio  # Import the function from your existing script

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

    def __init__(self, ytURL, outputDir, replacing, useLog, overwriteLog):
        super().__init__()
        self.ytURL = ytURL
        self.outputDir = outputDir
        self.replacing = replacing
        self.useLog = useLog
        self.overwriteLog = overwriteLog

    def run(self):
        # Call the downloadAndTagAudio function with the provided arguments
        downloadAndTagAudio(self.ytURL, self.outputDir, self.replacing, self.useLog)
        # Emit the final output to the main thread
        self.outputSignal.emit("Audio download completed.")

class YTAudioFetcherGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Set the window title and size
        self.setWindowTitle('YouTube Audio Fetch')
        self.setGeometry(100, 100, 400, 300)

        # Create layout
        layout = QtWidgets.QVBoxLayout()

        # URL input
        self.urlInput = QtWidgets.QLineEdit(self)
        self.urlInput.setPlaceholderText("Enter your YouTube playlist or video URL here")
        layout.addWidget(self.urlInput)

        # Output folder input and browse button
        outputLayout = QtWidgets.QHBoxLayout()
        self.outputDirInput = QtWidgets.QLineEdit(self)
        self.outputDirInput.setPlaceholderText("Enter the folder you want to save your MP3 files here")
        outputLayout.addWidget(self.outputDirInput)

        self.browseButton = QtWidgets.QPushButton("Browse", self)
        self.browseButton.clicked.connect(self.browseFolder)
        outputLayout.addWidget(self.browseButton)

        layout.addLayout(outputLayout)

        # Toggle Options button
        self.toggleOptionsButton = QtWidgets.QPushButton("Toggle Options", self)
        self.toggleOptionsButton.clicked.connect(self.toggleOptions)
        layout.addWidget(self.toggleOptionsButton)

        # Group box for options
        self.optionsGroup = QtWidgets.QGroupBox("Options", self)
        self.optionsLayout = QtWidgets.QVBoxLayout()
        
        # Replace existing files switch
        self.replaceSwitch = QtWidgets.QCheckBox("Replace existing MP3 files", self)
        self.optionsLayout.addWidget(self.replaceSwitch)

        # Use log files switch
        self.logSwitch = QtWidgets.QCheckBox("Use log file for tag data", self)
        self.logSwitch.setChecked(True)  # Set the checkbox to be checked by default
        self.optionsLayout.addWidget(self.logSwitch)

        # Overwrite log files switch
        self.overwriteSwitch = QtWidgets.QCheckBox("Overwrite data in log file", self)
        self.optionsLayout.addWidget(self.overwriteSwitch)

        self.optionsGroup.setLayout(self.optionsLayout)
        self.optionsGroup.setVisible(False)  # Initially hide the options group
        layout.addWidget(self.optionsGroup)

        # Start button
        self.startButton = QtWidgets.QPushButton("Start Download", self)
        self.startButton.clicked.connect(self.startDownload)
        layout.addWidget(self.startButton)

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
        self.setLayout(layout)
        self.setStyleSheet("background-color: #1A082A; color: #FFFFFF;")
    
    def toggleOptions(self):
        self.optionsGroup.setVisible(not self.optionsGroup.isVisible())

    def browseFolder(self):
        # Open a dialog to select a directory
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder: self.outputDirInput.setText(folder)
    def startDownload(self):
        ytURL = self.urlInput.text()
        outputDir = self.outputDirInput.text()
        replacing = self.replaceSwitch.isChecked()
        useLog = self.logSwitch.isChecked()
        overwriteLog = self.overwriteSwitch.isChecked()

        if not ytURL or not outputDir:
            self.statusLabel.setText("Please fill in all fields.")
            return

        self.statusLabel.setText("Downloading...")
        QtWidgets.QApplication.processEvents()

        # Create a worker thread
        self.worker = Worker(ytURL, outputDir, replacing, useLog, overwriteLog)
        self.worker.outputSignal.connect(self.updateLabel)
        self.worker.start()

    def updateLabel(self, message=None):
        # Update the label with the current output buffer
        self.progressLabel.setText("Output:\n" + self.output_capture.output_buffer)
        if message: self.statusLabel.setText(message)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = YTAudioFetcherGUI()
    window.show()
    sys.exit(app.exec_())