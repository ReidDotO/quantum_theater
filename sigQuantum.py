import json
import time
import threading
import speech_recognition as sr
import pygame
import os
from pathlib import Path

class QuantumTheater:
    def __init__(self):
        # Game state
        self.game_state = "setup"  # setup, waiting_for_start, phase1, phase2, complete
        self.player_a_phrase_said = False
        self.player_b_gesture_made = False
        
        # Player positions
        self.player_a_start = 5
        self.player_b_start = 4
        self.player_a_target = 10
        self.player_b_target = 11
        
        # Audio setup
        pygame.mixer.init()
        self.audio_device = None
        
        # Speech recognition
        self.recognizer = sr.Recognizer()
        
        # List available microphones and select one
        print("Available microphones:")
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"  {index}: {name}")
        
        # You can change this index to select a different microphone
        microphone_index = 3  # Default microphone (usually index 0)
        self.microphone = sr.Microphone(device_index=microphone_index)
        print(f"Using microphone: {sr.Microphone.list_microphone_names()[microphone_index]}")
        
        # Threading for microphone listening
        self.listening_thread = None
        self.stop_listening = False
        
        # File paths
        self.grid_locations_file = Path('narrative_elements/perspective_grid_locations.json')
        self.vr_message_file = Path('narrative_elements/vrMessage.json')
        self.gesture_file = Path(r'C:\Users\Reid\Desktop\ToLP\QuantumTheater\TD\CombinedWorkflows\HandGestureValue.json')
        self.target_sections_file = Path('narrative_elements/target_sections.json')
        self.audio_input_dir = Path('audio_input')
        
        # Create directories if they don't exist
        self.grid_locations_file.parent.mkdir(exist_ok=True)
        self.audio_input_dir.mkdir(exist_ok=True)
        
        # Initialize JSON files
        self.initialize_json_files()
        
        # Hints and messages
        self.player_a_initial_hint = """I hide my secrets in a wave unseen,
But shine your light — I am not what I've been.
Your very glance disturbs my stealthy course,
And locks me down with unseen force.
What am I?"""
        
        self.player_a_position_hint = "Go to section 10"
        self.player_b_gesture_hint = "Make the quantum entanglement gesture, or a thumbs up, toward the observer."
        self.player_b_position_hint = "Go to section 11"
        
        # Expected responses
        self.expected_phrase = "observer effect"
        self.expected_gesture = 5  # Random gesture number 1-15
        
        print("Quantum Theater initialized!")
    
    def initialize_json_files(self):
        """Initialize all required JSON files"""
        # Initialize vrMessage.json
        if not self.vr_message_file.exists():
            initial_vr_message = {
                "vrMessage": [
                    {"string": "Welcome to Quantum Theater. Please take your starting positions."}
                ]
            }
            with open(self.vr_message_file, 'w') as f:
                json.dump(initial_vr_message, f, indent=4)
        
        # Initialize gesture.json
        if not self.gesture_file.exists():
            initial_gesture = {
                "h1:None": self.expected_gesture
            }
            with open(self.gesture_file, 'w') as f:
                json.dump(initial_gesture, f, indent=4)
        
        # Initialize target_sections.json
        if not self.target_sections_file.exists():
            initial_targets = {
                "player_a": {
                    "tag_number": 100,
                    "target_section": None
                },
                "player_b": {
                    "tag_number": 88,
                    "target_section": None
                }
            }
            with open(self.target_sections_file, 'w') as f:
                json.dump(initial_targets, f, indent=4)
    
    def update_vr_message(self, message):
        """Update the VR message JSON file"""
        vr_message = {
            "vrMessage": [
                {"string": message}
            ]
        }
        with open(self.vr_message_file, 'w') as f:
            json.dump(vr_message, f, indent=4)
        print(f"VR Message updated: {message}")
    
    def update_target_sections(self, player_a_target=None, player_b_target=None):
        """Update target sections for players"""
        try:
            with open(self.target_sections_file, 'r') as f:
                targets = json.load(f)
            
            if player_a_target is not None:
                targets["player_a"]["target_section"] = player_a_target
            if player_b_target is not None:
                targets["player_b"]["target_section"] = player_b_target
            
            with open(self.target_sections_file, 'w') as f:
                json.dump(targets, f, indent=4)
            
            print(f"Target sections updated - Player A: {player_a_target}, Player B: {player_b_target}")
        except Exception as e:
            print(f"Error updating target sections: {e}")
    
    def clear_target_sections(self):
        """Clear all target sections"""
        try:
            with open(self.target_sections_file, 'r') as f:
                targets = json.load(f)
            
            targets["player_a"]["target_section"] = None
            targets["player_b"]["target_section"] = None
            
            with open(self.target_sections_file, 'w') as f:
                json.dump(targets, f, indent=4)
            
            print("Target sections cleared")
        except Exception as e:
            print(f"Error clearing target sections: {e}")
    
    def get_player_positions(self):
        """Read player positions from the grid locations JSON file"""
        try:
            if self.grid_locations_file.exists():
                with open(self.grid_locations_file, 'r') as f:
                    data = json.load(f)
                
                # Extract player positions
                player_a_pos = None
                player_b_pos = None
                
                for tag_id, tag_data in data.items():
                    if tag_id == "100":  # Player A
                        player_a_pos = tag_data.get("grid_section")
                    elif tag_id == "88":  # Player B
                        player_b_pos = tag_data.get("grid_section")
                
                return player_a_pos, player_b_pos
            else:
                return None, None
        except Exception as e:
            print(f"Error reading player positions: {e}")
            return None, None
    
    def play_audio_hint(self, hint_text, audio_filename=None):
        """Play audio hint to Player B"""
        print(f"🎧 AUDIO HINT TO PLAYER B: {hint_text}")
        
        # If an audio filename is provided, try to play it
        if audio_filename:
            audio_file_path = self.audio_input_dir / audio_filename
            if audio_file_path.exists():
                try:
                    pygame.mixer.music.load(str(audio_file_path))
                    pygame.mixer.music.play()
                    print(f"🔊 Playing audio file: {audio_filename}")
                except Exception as e:
                    print(f"❌ Error playing audio file {audio_filename}: {e}")
            else:
                print(f"⚠️ Audio file not found: {audio_filename}")
        else:
            # Fallback to text-to-speech or just print
            print("📢 (Audio would play here in full implementation)")
    
    def listen_for_player_a(self):
        """Listen for Player A's microphone input"""
        try:
            with self.microphone as source:
                print("🎤 Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                print("🎤 Listening for Player A... (speak now!)")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                try:
                    text = self.recognizer.recognize_google(audio).lower()
                    print(f"Player A said: {text}")
                    
                    # Check for correct phrase
                    if self.expected_phrase in text:
                        print("✅ Player A said the correct phrase!")
                        self.player_a_phrase_said = True
                        return True
                    
                    # Check for repeat hint command
                    if "repeat hint" in text or "repeat" in text:
                        print("🔄 Player A requested hint repeat")
                        self.update_vr_message(self.player_a_initial_hint)
                        return False
                    
                except sr.UnknownValueError:
                    print("Could not understand Player A's speech")
                except sr.RequestError as e:
                    print(f"Could not request results: {e}")
                    
        except sr.WaitTimeoutError:
            print("No speech detected from Player A")
        except Exception as e:
            print(f"Error listening for Player A: {e}")
        
        return False
    
    def check_gesture(self):
        """Check if the correct gesture was made by reading gesture.json"""
        try:
            if self.gesture_file.exists():
                with open(self.gesture_file, 'r') as f:
                    data = json.load(f)
                
                # Parse the new format: {"h1:None": 5.0}
                gesture_number = data.get("h1:None")
                if gesture_number == self.expected_gesture:
                    print("✅ Correct gesture detected!")
                    return True
                else:
                    print(f"Gesture detected: {gesture_number}, expected: {self.expected_gesture}")
                    return False
            else:
                return False
        except Exception as e:
            print(f"Error checking gesture: {e}")
            return False
    
    def check_player_positions(self):
        """Check if both players are in their target positions"""
        player_a_pos, player_b_pos = self.get_player_positions()
        
        a_in_position = (player_a_pos == self.player_a_target)
        b_in_position = (player_b_pos == self.player_b_target)
        
        print(f"Player A position: {player_a_pos} (target: {self.player_a_target}) - {'✅' if a_in_position else '❌'}")
        print(f"Player B position: {player_b_pos} (target: {self.player_b_target}) - {'✅' if b_in_position else '❌'}")
        
        return a_in_position and b_in_position
    
    def setup_phase(self):
        """Initial setup phase"""
        print("\n=== SETUP PHASE ===")
        print("Setting up Quantum Theater...")
        
        # Update VR message with initial instructions
        setup_message = f"""Welcome to Quantum Theater!

Starting Positions:
- Player A (VR): Go to section {self.player_a_start}
- Player B (Headphones): Go to section {self.player_b_start}

Quantum mechanics tells us that observation affects reality.
In this experiment, your actions will determine the outcome.

Take your positions and await further instructions."""
        
        self.update_vr_message(setup_message)
        
        # Set initial target sections (starting positions)
        self.update_target_sections(self.player_a_start, self.player_b_start)
        
        # Play setup audio for Player B
        self.play_audio_hint("Welcome to Quantum Theater. Please take your starting position in section 4.", "setup_audio.mp3")
        
        print("Setup complete. Waiting for players to take starting positions...")
        self.game_state = "waiting_for_start"
    
    def waiting_for_start_phase(self):
        """Wait for players to reach starting positions"""
        print("\n=== WAITING FOR START POSITIONS ===")
        
        while self.game_state == "waiting_for_start":
            player_a_pos, player_b_pos = self.get_player_positions()
            
            a_in_start = (player_a_pos == self.player_a_start)
            b_in_start = (player_b_pos == self.player_b_start)
            
            if a_in_start and b_in_start:
                print("✅ Both players in starting positions!")
                self.game_state = "phase1"
                break
            
            print(f"Waiting... Player A: {player_a_pos}/{self.player_a_start}, Player B: {player_b_pos}/{self.player_b_start}")
            time.sleep(2)
    
    def phase1_riddle(self):
        """Phase 1: Player A solves the riddle"""
        print("\n=== PHASE 1: THE RIDDLE ===")
        
        # Give Player A the riddle
        self.update_vr_message(self.player_a_initial_hint)
        
        # Give Player B the gesture instruction
        self.play_audio_hint(self.player_b_gesture_hint, "gesture_instruction.mp3")
        
        print("Player A: Solve the quantum riddle")
        print("Player B: Make the correct gesture toward Player A")
        
        # Wait for both conditions to be met
        while not (self.player_a_phrase_said and self.player_b_gesture_made):
            # Check for Player A's phrase
            if not self.player_a_phrase_said:
                if self.listen_for_player_a():
                    self.player_a_phrase_said = True
                    # Send the observation message after correct phrase
                    self.update_vr_message("Look at the other player and see how their gestures change your world while observed")
            
            # Check for Player B's gesture
            if not self.player_b_gesture_made:
                if self.check_gesture():
                    self.player_b_gesture_made = True
            
            time.sleep(0.5)
        
        print("✅ Phase 1 complete! Both conditions met.")
        self.game_state = "phase2"
    
    def phase2_positioning(self):
        """Phase 2: Players move to target positions"""
        print("\n=== PHASE 2: POSITIONING ===")
        
        # Update target sections for final positions
        self.update_target_sections(self.player_a_target, self.player_b_target)
        
        # Tell Player A where to go
        self.update_vr_message(self.player_a_position_hint)
        
        # Tell Player B where to go
        self.play_audio_hint(self.player_b_position_hint, "position_instruction.mp3")
        
        print("Players: Move to your target positions")
        print(f"Player A target: Section {self.player_a_target}")
        print(f"Player B target: Section {self.player_b_target}")
        
        # Wait for both players to reach target positions
        while not self.check_player_positions():
            time.sleep(1)
        
        print("✅ Both players in target positions!")
        # Clear target sections when both players reach their targets
        self.clear_target_sections()
        self.game_state = "complete"
    
    def run(self):
        """Main game loop"""
        print("🚀 Starting Quantum Theater...")
        
        try:
            # Setup phase
            self.setup_phase()
            
            # Wait for starting positions
            self.waiting_for_start_phase()
            
            # Phase 1: Riddle and gesture
            self.phase1_riddle()
            
            # Phase 2: Positioning
            self.phase2_positioning()
            
            # Game complete
            print("\n🎉 LOOP COMPLETE! 🎉")
            print("Quantum entanglement achieved!")
            print("The observer effect has been demonstrated.")
            print("Both players have successfully completed the quantum experiment.")
            
            # Final message
            completion_message = """EXPERIMENT COMPLETE!

You have successfully demonstrated quantum mechanics principles:
- The Observer Effect: Your observation affected the outcome
- Quantum Entanglement: Your coordinated actions created a shared state
- Wave Function Collapse: Your choices determined the final reality

The quantum theater experiment is complete."""
            
            self.update_vr_message(completion_message)
            self.play_audio_hint("Experiment complete. Well done!", "completion_audio.mp3")
            
            # Clear target sections when game is complete
            self.clear_target_sections()
            
        except KeyboardInterrupt:
            print("\n⚠️ Game interrupted by user")
            # Clear target sections on interruption
            self.clear_target_sections()
        except Exception as e:
            print(f"❌ Error during game: {e}")
            # Clear target sections on error
            self.clear_target_sections()
        finally:
            print("Shutting down Quantum Theater...")

def main():
    """Main entry point"""
    print("=" * 50)
    print("QUANTUM THEATER")
    print("A Quantum Mechanics Interactive Experience")
    print("=" * 50)
    
    # Check if required dependencies are available
    try:
        import speech_recognition
        import pygame
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        print("Please install required packages:")
        print("pip install SpeechRecognition pygame pyaudio")
        return
    
    # Create and run the game
    game = QuantumTheater()
    game.run()

if __name__ == "__main__":
    main()
