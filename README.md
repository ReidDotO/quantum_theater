# Quantum Theater

Quantum Theater is an interactive playable adaptive experience that combines physical game pieces (Aruco tags) with a digital game master powered by Claude and text-to-speech. The experience creates a mysterious quantum-themed narrative that responds to player actions in real-time.

## Setup

1. **Install Dependencies**:
   ```
   pip install python-dotenv anthropic elevenlabs pygame SpeechRecognition opencv-python numpy
   ```
   Maybe more? tbd

2. **Initialize the Environment**:
   ```
   python init_quantum_theater.py
   ```
   This will create all necessary JSON files with sample data.

3. **API Keys**:
   - Add your Anthropic API key and ElevenLabs API key to the `.env` file

## Run it

1. **Run aruco_tracker.py**
    ```
   python aruco_tracker.py
   ```

2. **Run quantum_theater.py**
    ```
   python quantum_theater.py
   ```