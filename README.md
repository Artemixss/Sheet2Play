# Sheet2Play

> A program that converts physical sheet music into interactive piano roll visualizations.

## Architecture & Current State

Sheet2Play takes physical sheet music (or PDFs), uses deep learning to extract the notes into an `.mxl` file, and then feeds it into a custom engine to create a playable piano visualization. 

The project is split into two main components:

### 1. The Interactive Visualization Engine 
A custom C# application built with Raylib. This is the frontend rendering engine. It parses standardized musical data (`.mxl`, `.midi`) and translates it into a responsive, falling-note "piano roll" interface. 
* **Performance:** Capable of rendering at 144 FPS.
* **Audio:** Features zero-latency, millisecond-perfect audio synchronization.

### 2. The Optical Music Recognition (OMR) Pipeline (In Development)
The ultimate goal of this project is to use a custom YOLO-based neural network to read raw sheet music images and extract the exact pixel coordinates of the musical symbols. 

**Temporary Dependency:** The custom model is currently in development. To validate the C# engine right now, it uses the open-source software **Audiveris** to handle the heavy lifting of PDF-to-XML conversion. 

## Requirements & Setup Warning
**Note**: Because the program uses heavy third-party software for testing instead of the custom neural network local setup is complex.*

To run the full conversion pipeline locally, your machine requires:
* **Audiveris** * **MuseScore 4** * **VirtualMIDISynth (CoolSoft)** *Future updates will completely deprecate these dependencies once the custom deep learning algorithm finishes.*

## Usage

1. Clone the repository and navigate to the `Visualization_engine` folder.
2. Execute `program.cs` to launch the C# rendering engine.
3. **Drag & Drop:** You can drop a `.pdf`, `.jpg`, `.mxl`, or `.midi` file directly into the application window to initialize the sequence.

## Controls

* **Spacebar:** Play / Pause playback.
* **Timeline Scrubbing:** Click and drag the progress slider to move forward or backward through the track.
