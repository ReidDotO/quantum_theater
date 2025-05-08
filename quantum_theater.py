"""
Quantum Theater - Interactive Experience
A quantum-themed narrative experience that responds to physical markers and user interaction.
"""

import json
import os
import sys
import time
import random
import math
import speech_recognition as sr
import threading
import warnings
import traceback
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic
from elevenlabs import generate, save, set_api_key, voices
import pygame

# Suppress ALSA warnings
warnings.filterwarnings("ignore", category=UserWarning)
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Create a context manager for suppressing ALSA errors
class ALSAErrorSuppressor:
    def __enter__(self):
        self.stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr.close()
        sys.stderr = self.stderr

# Initialize speech recognition with ALSA error suppression
with ALSAErrorSuppressor():
    sr.Microphone()

# Load environment variables
load_dotenv()
anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
set_api_key(os.getenv('ELEVENLABS_API_KEY'))

# Create output directories if they don't exist
AUDIO_OUTPUT_DIR = Path('audio_outputs')
AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)

TRANSCRIPTS_DIR = Path('transcripts')
TRANSCRIPTS_DIR.mkdir(exist_ok=True)

# Configuration
ELEM_DIR = Path('narrative_elements')
ELEM_DIR.mkdir(exist_ok=True)

MARKER_POSITIONS_FILE = ELEM_DIR / 'marker_positions.json'
PROTAGONISTS_FILE = ELEM_DIR / 'protagonists.json'
ANTAGONISTS_FILE = ELEM_DIR / 'antagonists.json'
GOALS_FILE = ELEM_DIR / 'goals.json'
OBSTACLES_FILE = ELEM_DIR / 'obstacles.json'
WORLD_RULES_FILE = ELEM_DIR / 'world_rules.json'
SUPPORTING_ROLES_FILE = ELEM_DIR / 'supporting_roles.json'
SETTINGS_FILE = ELEM_DIR / 'settings.json'
TIME_DYNAMICS_FILE = ELEM_DIR / 'time_dynamics.json'
AGENCY_FILE = ELEM_DIR / 'agency.json'
TRANSFORMATIONS_FILE = ELEM_DIR / 'transformations.json'
TONE_FILE = ELEM_DIR / 'tone.json'
NARRATIVE_STRUCTURES_FILE = ELEM_DIR / 'narrative_structures.json'
TRIGGER_WORD = "oracle"  # Trigger word for voice commands

# Game states
GAME_STATES = [
    "setup",           # Initial setup phase
    "introduction",    # Introduction to the narrative
    "exploration",     # Main exploration/play phase
    "climax",          # Climax/critical decision point
    "collapse",        # Quantum collapse phase
    "resolution",      # Resolution/closing
    "epilogue"         # Optional epilogue/reflection
]

class QuantumTheater:
    def __init__(self):
        # Initialize pygame mixer for audio
        pygame.mixer.init()
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Adjust for ambient noise
        with self.microphone as source:
            print("Calibrating microphone for ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=3)
            print("Microphone calibrated")
        
        # Load game data
        self.load_game_data()
        
        # Game state
        self.questions_remaining = 30
        self.game_state = "setup"
        self.narrative = {}
        self.current_instruction = ""
        self.marker_history = {}  # To track marker positions over time
        self.last_movement_check = time.time()
        self.movement_check_interval = 30.0  # seconds
        self.last_scenario_time = 0
        self.scenario_cooldown = 20.0  # seconds between scenario changes
        self.last_processed_markers = set()  # Track which markers we've seen
        
        # Narrative context tracking
        self.narrative_context = {
            "recent_speech": [],  # Last 3 speech segments
            "recent_movements": [],  # Last 3 significant movements
            "phase_start_time": None,
            "total_movements": 0,
            "last_state_change": None
        }
        
        # Marker to narrative element mapping
        self.marker_mapping = {
            "79": "protagonist",
            "88": "antagonist",
            "62": "goal",
            "74": "obstacle",
            "100": "supporting_role",
            "67": "location"  # Changed from "setting" to "location"
        }
        
        # Selected narrative elements
        self.selected_elements = {
            "narrative_structure": None,
            "protagonist": None,
            "antagonist": None,
            "goal": None,
            "obstacle": None,
            "world_rule": None,
            "supporting_role": None,
            "setting": None,
            "time_dynamic": None,
            "agency_mechanic": None,
            "transformation": None,
            "tone": None,
            "location": None  # Added location to track current location within setting
        }
        
        # Voice recognition flags
        self.is_listening = False
        self.audio_playing = False
        self.voice_volume = 0.8
        self.event_volume = 0.4
        
        # Voice selection
        self.voice_id = self.select_voice()
        
        # Transcript for logging
        self.transcript = []
        
        # Thread lock for synchronization
        self.lock = threading.Lock()
        
        # Load sound effects if available
        self.load_sound_effects()
        
        # Game phases tracking
        self.completed_phases = []
        self.current_phase_start_time = time.time()
        self.current_phase_duration = 0  # in seconds, 0 means no time limit

    def load_game_data(self):
        """Load all game data from JSON files."""
        try:
            # Load data files
            with open(PROTAGONISTS_FILE, 'r') as f:
                self.protagonists_data = json.load(f)
            
            with open(ANTAGONISTS_FILE, 'r') as f:
                self.antagonists_data = json.load(f)
            
            with open(GOALS_FILE, 'r') as f:
                self.goals_data = json.load(f)
            
            with open(OBSTACLES_FILE, 'r') as f:
                self.obstacles_data = json.load(f)
            
            with open(WORLD_RULES_FILE, 'r') as f:
                self.world_rules_data = json.load(f)
            
            with open(SUPPORTING_ROLES_FILE, 'r') as f:
                self.supporting_roles_data = json.load(f)
            
            with open(SETTINGS_FILE, 'r') as f:
                self.settings_data = json.load(f)
            
            with open(TIME_DYNAMICS_FILE, 'r') as f:
                self.time_dynamics_data = json.load(f)
            
            with open(AGENCY_FILE, 'r') as f:
                self.agency_data = json.load(f)
            
            with open(TRANSFORMATIONS_FILE, 'r') as f:
                self.transformations_data = json.load(f)
            
            with open(TONE_FILE, 'r') as f:
                self.tone_data = json.load(f)
            
            with open(NARRATIVE_STRUCTURES_FILE, 'r') as f:
                self.narrative_structures_data = json.load(f)
                
            print("Game data loaded successfully.")
        except Exception as e:
            print(f"Error loading game data: {e}")
            traceback.print_exc()
            raise

    def load_sound_effects(self):
        """Load sound effects for the game if they exist."""
        self.sound_effects = {}
        
        sound_dir = Path('sound_effects')
        if sound_dir.exists() and sound_dir.is_dir():
            for sound_file in sound_dir.glob('*.wav'):
                effect_name = sound_file.stem
                try:
                    self.sound_effects[effect_name] = pygame.mixer.Sound(str(sound_file))
                    print(f"Loaded sound effect: {effect_name}")
                except Exception as e:
                    print(f"Error loading sound effect {effect_name}: {e}")
        else:
            print("No sound effects directory found. Continuing without sound effects.")

    def play_sound_effect(self, effect_name):
        """Play a sound effect if it exists."""
        if effect_name in self.sound_effects:
            self.sound_effects[effect_name].set_volume(self.event_volume)
            self.sound_effects[effect_name].play()
        else:
            print(f"Sound effect '{effect_name}' not found.")

    def select_voice(self):
        """Select a voice from the available ElevenLabs voices."""
        try:
            available_voices = voices()
            if available_voices:
                # Attempt to find a voice that sounds mystical or otherworldly
                preferred_voices = ["Bella", "Onyx", "Nova", "Echo", "Wyvern", "Tempus"]
                for voice_name in preferred_voices:
                    for voice in available_voices:
                        if voice_name.lower() in voice.name.lower():
                            print(f"Selected voice: {voice.name}")
                            return voice.voice_id
                
                # If no preferred voice is found, use a random voice
                random_voice = random.choice(available_voices)
                print(f"Selected random voice: {random_voice.name}")
                return random_voice.voice_id
            else:
                print("No voices available. Using default voice.")
                return None
        except Exception as e:
            print(f"Error selecting voice: {e}")
            return None
    
    def get_current_markers(self):
        """Read current marker positions from the JSON file."""
        try:
            with open(MARKER_POSITIONS_FILE, 'r') as f:
                #print("loaded Marker JSON File")
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: {MARKER_POSITIONS_FILE} not found.")
            return {}
        except json.JSONDecodeError:
            print(f"Warning: {MARKER_POSITIONS_FILE} contains invalid JSON.")
            return {}
    
    def calculate_distance(self, pos1, pos2):
        """Calculate Euclidean distance between two positions."""
        dx = pos1['x'] - pos2['x']
        dy = pos1['y'] - pos2['y']
        return math.sqrt(dx * dx + dy * dy)
    
    def calculate_angle(self, pos1, pos2):
        """Calculate the angle between two positions in degrees."""
        dx = pos2['x'] - pos1['x']
        dy = pos2['y'] - pos1['y']
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        return angle_deg
    
    def calculate_marker_relationships(self, markers):
        """Calculate spatial relationships between markers."""
        relationships = []
        
        # Create a list of marker IDs for easier iteration
        marker_ids = list(markers.keys())
        
        # If we have at least two markers, calculate distances and angles
        if len(marker_ids) >= 2:
            for i in range(len(marker_ids)):
                for j in range(i+1, len(marker_ids)):
                    id1, id2 = marker_ids[i], marker_ids[j]
                    pos1 = markers[id1]['position']
                    pos2 = markers[id2]['position']
                    
                    distance = self.calculate_distance(pos1, pos2)
                    angle = self.calculate_angle(pos1, pos2)
                    
                    # Create a description of the relationship
                    relationships.append({
                        "marker1": id1,
                        "marker2": id2,
                        "distance": distance,
                        "angle": angle,
                        "description": f"Marker {id1} is {distance:.1f} units away from marker {id2} at an angle of {angle:.1f} degrees."
                    })
        
        return relationships
    
    def detect_significant_patterns(self, markers, relationships):
        """Detect significant patterns in marker arrangements."""
        print("looking for patterns")
        patterns = []
        
        # Check for markers in close proximity (potential interaction)
        close_markers = []
        for rel in relationships:
            if rel["distance"] < 50:  # Adjust threshold as needed
                close_markers.append((rel["marker1"], rel["marker2"]))
                patterns.append(f"Markers {rel['marker1']} and {rel['marker2']} are in close proximity.")
        
        # Check for markers forming geometric shapes
        if len(markers) >= 3:
            # Simple triangle detection
            triangles = []
            marker_ids = list(markers.keys())
            for i in range(len(marker_ids)):
                for j in range(i+1, len(marker_ids)):
                    for k in range(j+1, len(marker_ids)):
                        id1, id2, id3 = marker_ids[i], marker_ids[j], marker_ids[k]
                        triangles.append((id1, id2, id3))
                        patterns.append(f"Markers {id1}, {id2}, and {id3} form a triangle.")
        
        # Check for markers in specific zones
        for marker_id, data in markers.items():
            x, y = data['position']['x'], data['position']['y']
            if x < 200 and y < 200:
                patterns.append(f"Marker {marker_id} is in the upper-left quadrant.")
            elif x >= 200 and y < 200:
                patterns.append(f"Marker {marker_id} is in the upper-right quadrant.")
            elif x < 200 and y >= 200:
                patterns.append(f"Marker {marker_id} is in the lower-left quadrant.")
            else:
                patterns.append(f"Marker {marker_id} is in the lower-right quadrant.")
        
        # Check for linear arrangements
        if len(markers) >= 3:
            marker_ids = list(markers.keys())
            for i in range(len(marker_ids) - 2):
                for j in range(i + 1, len(marker_ids) - 1):
                    for k in range(j + 1, len(marker_ids)):
                        id1, id2, id3 = marker_ids[i], marker_ids[j], marker_ids[k]
                        pos1 = markers[id1]['position']
                        pos2 = markers[id2]['position']
                        pos3 = markers[id3]['position']
                        
                        # Calculate slopes between the points
                        try:
                            slope1 = (pos2['y'] - pos1['y']) / (pos2['x'] - pos1['x'])
                            slope2 = (pos3['y'] - pos2['y']) / (pos3['x'] - pos2['x'])
                            
                            # If slopes are very close, points are approximately colinear
                            if abs(slope1 - slope2) < 0.1:
                                patterns.append(f"Markers {id1}, {id2}, and {id3} form a line.")
                        except ZeroDivisionError:
                            # Handle vertical lines
                            if abs(pos1['x'] - pos2['x']) < 5 and abs(pos2['x'] - pos3['x']) < 5:
                                patterns.append(f"Markers {id1}, {id2}, and {id3} form a vertical line.")
        
        # Check for circular arrangements
        if len(markers) >= 3:
            marker_ids = list(markers.keys())
            positions = [markers[marker_id]['position'] for marker_id in marker_ids]
            
            # Calculate center of mass
            center_x = sum(pos['x'] for pos in positions) / len(positions)
            center_y = sum(pos['y'] for pos in positions) / len(positions)
            center = {'x': center_x, 'y': center_y}
            
            # Calculate distances from center
            distances = [self.calculate_distance(pos, center) for pos in positions]
            avg_distance = sum(distances) / len(distances)
            
            # If all points are roughly equidistant from center, they form a circle
            if all(abs(dist - avg_distance) < 15 for dist in distances):
                patterns.append(f"The markers form a circular arrangement.")
        
        return patterns
    
    def select_narrative_elements(self, markers, relationships, patterns):
        """Select narrative elements randomly from available options."""
        selected = self.selected_elements.copy()
        
        # Select elements randomly from each category
        selected["narrative_structure"] = random.choice(self.narrative_structures_data["structures"])
        selected["protagonist"] = random.choice(random.choice(self.protagonists_data["archetypes"])["protagonists"])
        selected["antagonist"] = random.choice(random.choice(self.antagonists_data["categories"])["antagonists"])
        selected["goal"] = random.choice(random.choice(self.goals_data["categories"])["goals"])
        selected["obstacle"] = random.choice(random.choice(self.obstacles_data["categories"])["obstacles"])
        selected["world_rule"] = random.choice(random.choice(self.world_rules_data["categories"])["rules"])
        selected["supporting_role"] = random.choice(random.choice(self.supporting_roles_data["categories"])["roles"])
        selected["setting"] = random.choice(random.choice(self.settings_data["categories"])["settings"])
        selected["time_dynamic"] = random.choice(random.choice(self.time_dynamics_data["categories"])["dynamics"])
        selected["agency_mechanic"] = random.choice(random.choice(self.agency_data["categories"])["mechanics"])
        selected["transformation"] = random.choice(random.choice(self.transformations_data["categories"])["transformations"])
        selected["tone"] = random.choice(random.choice(self.tone_data["categories"])["tones"])
        
        return selected
    
    def update_narrative_context(self, speech_segments=None, movement=None):
        """Update the narrative context with new information."""
        if speech_segments:
            # Add new speech segments to context
            self.narrative_context["recent_speech"].extend(speech_segments)
            # Keep only the last 3 segments
            self.narrative_context["recent_speech"] = self.narrative_context["recent_speech"][-3:]
        
        if movement:
            # Add new movement to context
            self.narrative_context["recent_movements"].append(movement)
            # Keep only the last 3 movements
            self.narrative_context["recent_movements"] = self.narrative_context["recent_movements"][-3:]
            self.narrative_context["total_movements"] += 1

    def get_narrative_context_prompt(self):
        """Generate a prompt section describing the current narrative context."""
        context_parts = []
        
        # Add current game state and phase duration
        phase_duration = time.time() - self.narrative_context["phase_start_time"] if self.narrative_context["phase_start_time"] else 0
        context_parts.append(f"CURRENT STATE: {self.game_state} (Phase duration: {int(phase_duration)} seconds)")
        
        # Add recent speech context
        if self.narrative_context["recent_speech"]:
            context_parts.append("\nRECENT NARRATIVE:")
            for speech in self.narrative_context["recent_speech"]:
                context_parts.append(f"- {speech}")
        
        # Add movement context
        if self.narrative_context["recent_movements"]:
            context_parts.append("\nRECENT MOVEMENTS:")
            for movement in self.narrative_context["recent_movements"]:
                marker_id = movement["marker_id"]
                element_type = self.marker_mapping.get(marker_id, "unknown")
                if element_type in self.selected_elements:
                    element = self.selected_elements[element_type]
                    context_parts.append(f"- {element['name']} moved {movement['distance']:.1f} units")
        
        # Add total movement count
        context_parts.append(f"\nTotal movements in this phase: {self.narrative_context['total_movements']}")
        
        return "\n".join(context_parts)

    def create_narrative_description(self, selected_elements, stage="introduction"):
        """Create a narrative description based on the selected elements and game stage."""
        protagonist = selected_elements["protagonist"]
        antagonist = selected_elements["antagonist"]
        goal = selected_elements["goal"]
        obstacle = selected_elements["obstacle"]
        world_rule = selected_elements["world_rule"]
        supporting_role = selected_elements["supporting_role"]
        setting = selected_elements["setting"]
        time_dynamic = selected_elements["time_dynamic"]
        agency_mechanic = selected_elements["agency_mechanic"]
        transformation = selected_elements["transformation"]
        tone = selected_elements["tone"]
        narrative_structure = selected_elements["narrative_structure"]
        
        # Create a prompt for Claude to generate a narrative
        prompt_base = f"""You are the Game Master for Quantum Theater, an interactive quantum narrative experience. 
Your role is to create an immersive, thought-provoking quantum narrative based on the elements I'll provide. 
Your narrative should be poetic, mysterious, and a bit funny, exploring quantum concepts through storytelling and acting as a bit of a cheeky bastard.

IMPORTANT: Keep your responses concise and impactful. Aim for 2-3 sentences per speech segment. Break longer responses into multiple <speech> segments.

{self.get_narrative_context_prompt()}

NARRATIVE STRUCTURE:
{narrative_structure['name']}: {narrative_structure['description']}
Pattern: {narrative_structure['pattern']}

PROTAGONIST:
{protagonist['name']}: {protagonist['description']}
Traits: {', '.join(protagonist['traits'])}
Desires: {', '.join(protagonist['desires'])}

ANTAGONIST:
{antagonist['name']}: {antagonist['description']}
Methods: {', '.join(antagonist['methods'])}
Motivations: {antagonist['motivations'][0]}

GOAL:
{goal['name']}: {goal['description']}
Challenges: {', '.join(goal['challenges'][:2])}

OBSTACLE:
{obstacle['name']}: {obstacle['description']}
Effects: {', '.join(obstacle['effects'][:2])}

WORLD RULE:
{world_rule['name']}: {world_rule['description']}
Implications: {', '.join(world_rule['implications'][:2])}

SUPPORTING ROLE:
{supporting_role['name']}: {supporting_role['description']}
Functions: {', '.join(supporting_role['functions'][:2])}

SETTING:
{setting['name']}: {setting['description']}
Properties: {', '.join(setting['properties'][:2])}

TIME DYNAMIC:
{time_dynamic['name']}: {time_dynamic['description']}
Properties: {', '.join(time_dynamic['properties'][:2])}

AGENCY MECHANIC:
{agency_mechanic['name']}: {agency_mechanic['description']}

TRANSFORMATION:
{transformation['name']}: {transformation['description']}
Triggers: {', '.join(transformation['triggers'][:2])}

TONE:
{tone['name']}: {tone['description']}
Elements: {', '.join(tone['elements'][:2])}

CURRENT GAME STATE: {stage}

Please provide your response in the following format:
<speech>First 2-3 sentences of narrative</speech>
<speech>Next 2-3 sentences if needed</speech>
<instructions>Optional instructions for the players here</instructions>
<next_state>true</next_state> or <next_state>false</next_state>
"""
        
        # Add state-specific instructions to the prompt
        state_instructions = {
            "introduction": """
In the introduction phase, your role is to:
1. Welcome players to the quantum narrative
2. Introduce the key elements (protagonist, setting, goal) in an engaging way
3. Establish the tone and atmosphere of the experience
4. Explain how marker movements can influence the narrative
5. Make players feel comfortable with the interactive nature of the experience

Keep each speech segment brief (2-3 sentences) and impactful.

Evaluate if:
- Players understand their role in the narrative
- The basic premise and goal are clear
- The tone and atmosphere are established
- Players are ready to begin exploring

If these elements are established, include <next_state>true</next_state>.
Otherwise, continue the introduction and include <next_state>false</next_state>.""",
            
            "exploration": """
In the exploration phase, your role is to:
1. Respond to player interactions and marker movements
2. Develop the narrative based on player choices
3. Introduce challenges and obstacles
4. Build tension toward the climax
5. Provide opportunities for meaningful choices

Keep each speech segment brief (2-3 sentences) and impactful.

IMPORTANT: Do not reintroduce the setting or characters. Build upon the existing narrative context and respond to the specific movements and interactions that have occurred.

Evaluate if:
- Players have made significant progress toward their goal
- Key narrative elements have been explored
- Tension is building appropriately
- Players are ready for the climax

If these conditions are met, include <next_state>true</next_state>.
Otherwise, continue the exploration and include <next_state>false</next_state>.""",
            
            "climax": """
In the climax phase, your role is to:
1. Present the critical decision point
2. Heighten the tension and stakes
3. Make the consequences of choices clear
4. Create a sense of urgency
5. Lead toward the quantum collapse

Keep each speech segment brief (2-3 sentences) and impactful.

IMPORTANT: Do not reintroduce the setting or characters. Build upon the existing narrative context and respond to the specific movements and interactions that have occurred.

Evaluate if:
- Players have made their critical decision
- The tension has reached its peak
- The narrative is ready for collapse
- The consequences are clear

If these conditions are met, include <next_state>true</next_state>.
Otherwise, continue building toward the climax and include <next_state>false</next_state>.""",
            
            "collapse": """
In the collapse phase, your role is to:
1. Show the consequences of the players' choices
2. Create a sense of quantum uncertainty
3. Allow the narrative to unravel
4. Prepare for resolution
5. Maintain engagement through the transition

Keep each speech segment brief (2-3 sentences) and impactful.

IMPORTANT: Do not reintroduce the setting or characters. Build upon the existing narrative context and respond to the specific movements and interactions that have occurred.

Evaluate if:
- The consequences have been fully realized
- The quantum collapse is complete
- The narrative is ready for resolution
- Players understand the impact of their choices

If these conditions are met, include <next_state>true</next_state>.
Otherwise, continue the collapse process and include <next_state>false</next_state>.""",
            
            "resolution": """
In the resolution phase, your role is to:
1. Provide closure to the narrative
2. Reflect on the journey
3. Acknowledge the players' choices
4. Create a satisfying conclusion
5. Leave room for future possibilities

Keep each speech segment brief (2-3 sentences) and impactful.

IMPORTANT: Do not reintroduce the setting or characters. Build upon the existing narrative context and respond to the specific movements and interactions that have occurred.

Evaluate if:
- The narrative has reached a satisfying conclusion
- All major plot threads are resolved
- Players feel their choices mattered
- The experience feels complete

If these conditions are met, include <next_state>true</next_state>.
Otherwise, continue the resolution and include <next_state>false</next_state>."""
        }
        
        prompt = prompt_base + state_instructions.get(stage, "")
        
        # Get Claude's response
        try:
            message = anthropic.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response = message.content[0].text
            
            # Extract speech segments, instructions, and next_state flag
            speech_segments = []
            instructions = ""
            next_state = False
            
            # Extract all speech segments
            speech_parts = response.split("<speech>")
            for part in speech_parts[1:]:  # Skip the first part (before first <speech> tag)
                if "</speech>" in part:
                    speech = part.split("</speech>")[0].strip()
                    if speech:  # Only add non-empty segments
                        speech_segments.append(speech)
            
            if "<instructions>" in response and "</instructions>" in response:
                instructions = response.split("<instructions>")[1].split("</instructions>")[0].strip()
            
            if "<next_state>" in response and "</next_state>" in response:
                next_state = response.split("<next_state>")[1].split("</next_state>")[0].strip().lower() == "true"
            
            # If no speech segments were found, use the whole response as one segment
            if not speech_segments:
                speech_segments = [response]
            
            # Update narrative context with new speech segments
            self.update_narrative_context(speech_segments=speech_segments)
            
            return {
                "speech_segments": speech_segments,
                "instructions": instructions,
                "next_state": next_state,
                "full_response": response
            }
            
        except Exception as e:
            print(f"Error getting Claude's response: {e}")
            return {
                "speech_segments": ["The quantum field fluctuates, making communication temporarily unclear. Please try again as the wave function stabilizes."],
                "instructions": "",
                "next_state": False,
                "full_response": ""
            }

    def check_state_advancement(self, narrative_response):
        """Check if the current game state should advance based on Claude's assessment."""
        if narrative_response.get("next_state", False):
            current_index = GAME_STATES.index(self.game_state)
            if current_index < len(GAME_STATES) - 1:
                previous_state = self.game_state
                self.game_state = GAME_STATES[current_index + 1]
                
                print(f"\nAdvancing from {previous_state} to {self.game_state}")
                
                # Update narrative context for state change
                self.narrative_context["last_state_change"] = time.time()
                self.narrative_context["phase_start_time"] = time.time()
                self.narrative_context["total_movements"] = 0
                
                # Play a state transition sound
                self.play_sound_effect("transition")
                
                # Generate narrative for the new state
                new_narrative = self.create_narrative_description(self.selected_elements, stage=self.game_state)
                
                # Update transcript
                self.transcript.append({
                    "type": "state_transition",
                    "from_state": previous_state,
                    "to_state": self.game_state,
                    "narrative": new_narrative["speech_segments"][0],
                    "timestamp": datetime.now().isoformat()
                })
                
                # Play narrative segments
                self.play_narrative_segments(new_narrative)
                
                return {
                    "type": "state_transition",
                    "from_state": previous_state,
                    "to_state": self.game_state,
                    "text": new_narrative["speech_segments"][0]
                }
        
        return None
    
    def detect_marker_changes(self):
        """Detect changes in markers from the last check."""
        current_markers = self.get_current_markers()
        current_marker_ids = set(current_markers.keys())
        
        # Check for new markers
        new_markers = current_marker_ids - self.last_processed_markers
        
        # Check for removed markers
        removed_markers = self.last_processed_markers - current_marker_ids
        
        # Update last processed markers
        self.last_processed_markers = current_marker_ids
        
        return {
            "current": current_markers,
            "new": new_markers,
            "removed": removed_markers,
            "has_changes": bool(new_markers or removed_markers)
        }
    
    def detect_significant_movements(self):
        """Detect significant movements in marker positions."""
        current_markers = self.get_current_markers()
        significant_movements = []
        
        for marker_id, data in current_markers.items():
            current_pos = data['position']
            
            # Check if we've seen this marker before
            if marker_id in self.marker_history:
                previous_pos = self.marker_history[marker_id]['position']
                distance = self.calculate_distance(current_pos, previous_pos)
                
                # If movement exceeds threshold, record it
                if distance > 20:  # Adjust threshold as needed
                    significant_movements.append({
                        "marker_id": marker_id,
                        "from": previous_pos,
                        "to": current_pos,
                        "distance": distance
                    })
            
            # Update marker history
            self.marker_history[marker_id] = data
        
        return significant_movements
    
    def generate_and_play_audio(self, text):
        """Generate and play audio using ElevenLabs API."""
        if not text:
            print("No text to generate audio for.")
            return
        
        try:
            print(f"\nGenerating audio for: {text}")
            
            # Set audio playing flag
            self.audio_playing = True
            
            # Generate audio
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            audio = generate(
                text=text,
                voice=self.voice_id,
                model="eleven_monolingual_v1"
            )
            
            # Save the audio file
            audio_filename = f"quantum_narrative_{timestamp}.mp3"
            audio_path = str(AUDIO_OUTPUT_DIR / audio_filename)
            save(audio, audio_path)
            print(f"Saved audio file: {audio_filename}")
            
            # Play the audio file
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.set_volume(self.voice_volume)
            pygame.mixer.music.play()
            
            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Reset audio playing flag
            self.audio_playing = False
                
            return audio_path
            
        except Exception as e:
            print(f"Error generating or playing audio: {e}")
            traceback.print_exc()
            self.audio_playing = False
    
    def listen_for_command(self):
        """Listen for voice commands with trigger word."""
        try:
            print("\nListening for commands... (Say 'Oracle' to activate)")
            self.is_listening = True
            
            with ALSAErrorSuppressor():
                with self.microphone as source:
                    audio = self.recognizer.listen(source)
                
                try:
                    text = self.recognizer.recognize_google(audio).lower()
                    print(f"Heard: {text}")
                    
                    # Check for trigger word
                    if TRIGGER_WORD in text:
                        # Extract command after trigger word
                        command = text.split(TRIGGER_WORD, 1)[1].strip()
                        
                        # If there's a command after the trigger word, process it
                        if command:
                            return command
                        else:
                            print("Trigger word detected, but no command found.")
                    
                except sr.UnknownValueError:
                    print("Could not understand audio")
                except sr.RequestError as e:
                    print(f"Could not request results; {e}")
                    
                return None
                
        except Exception as e:
            print(f"Error in voice recognition: {e}")
            return None
        finally:
            self.is_listening = False
    
    def handle_voice_command(self, command):
        """Handle a voice command from the player."""
        # Check for help/clue requests
        if any(word in command for word in ["help", "clue", "hint", "confused"]):
            if self.questions_remaining > 0:
                self.questions_remaining -= 1
                print(f"\nProviding a clue. Questions remaining: {self.questions_remaining}")
                
                # Generate clue
                clue_response = self.create_narrative_description(self.selected_elements, stage="clue")
                
                # Play a sound effect if available
                self.play_sound_effect("insight")
                
                # Update transcript
                self.transcript.append({
                    "type": "clue_request",
                    "game_state": self.game_state,
                    "player_input": command,
                    "gm_response": clue_response["speech_segments"][0],
                    "questions_remaining": self.questions_remaining,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Generate and play audio
                self.generate_and_play_audio(clue_response["speech_segments"][0])
                
                # Check for state advancement
                state_change = self.check_state_advancement(clue_response)
                if state_change:
                    return state_change
                
                return {
                    "type": "clue",
                    "text": clue_response["speech_segments"][0],
                    "questions_remaining": self.questions_remaining
                }
            else:
                no_questions_response = "The quantum field has grown opaque to direct questioning. You must now interpret the patterns and discover the path forward through your own observations and actions."
                print(f"\n{no_questions_response}")
                
                # Play a sound effect if available
                self.play_sound_effect("denied")
                
                # Update transcript
                self.transcript.append({
                    "type": "no_questions_remaining",
                    "game_state": self.game_state,
                    "player_input": command,
                    "gm_response": no_questions_response,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Generate and play audio
                self.generate_and_play_audio(no_questions_response)
                
                return {
                    "type": "no_questions",
                    "text": no_questions_response
                }
        
        # Exit command
        elif any(word in command for word in ["exit", "quit", "end", "stop"]):
            print("\nEnding session...")
            
            # Play a sound effect if available
            self.play_sound_effect("exit")
            
            farewell = "The quantum experience concludes, folding back into potential. Your journey remains encoded in the fabric of possibility."
            self.generate_and_play_audio(farewell)
            
            return {
                "type": "exit",
                "text": "Ending the quantum theater experience."
            }
        
        # General response to other inputs - let Claude interpret commands more flexibly
        else:
            # Get Claude to respond to the player's input
            prompt = f"""You are the Game Master for Quantum Theater .0, an interactive quantum narrative experience. A player has said: "{command}"

Respond in character as the narrative voice of this quantum experience. Your response should be:
1. Brief (10-50 words)
2. Maintain the established tone and atmosphere
3. Treat the player's words as if they are the protagonist speaking or acting in the quantum narrative
4. Provide a meaningful response that feels like part of the ongoing story
5. Wrap your response in <speech></speech> tags
6. Include <next_state>true</next_state> if the current game state's goals have been achieved, otherwise <next_state>false</next_state>

Current narrative state:
- Game phase: {self.game_state}
- Protagonist: {self.selected_elements['protagonist']['name']}
- Setting: {self.selected_elements['setting']['name']}
- Tone: {self.selected_elements['tone']['name']}
- Narrative structure: {self.selected_elements['narrative_structure']['name']}"""
            
            try:
                message = anthropic.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=500,
                    temperature=0.7,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                response = message.content[0].text
            except Exception as e:
                print(f"Error getting Claude's response: {e}")
                response = "<speech>The quantum field fluctuates, making your words ripple through reality in unexpected ways. Perhaps try a different approach as the possibilities stabilize.</speech><next_state>false</next_state>"
            
            # Extract speech and next_state
            speech = response
            next_state = False
            
            if "<speech>" in response and "</speech>" in response:
                speech = response.split("<speech>")[1].split("</speech>")[0].strip()
            
            if "<next_state>" in response and "</next_state>" in response:
                next_state = response.split("<next_state>")[1].split("</next_state>")[0].strip().lower() == "true"
            
            # Play a sound effect if available
            self.play_sound_effect("response")
            
            # Update transcript
            self.transcript.append({
                "type": "player_interaction",
                "game_state": self.game_state,
                "player_input": command,
                "gm_response": speech,
                "timestamp": datetime.now().isoformat()
            })
            
            # Generate and play audio
            self.generate_and_play_audio(speech)
            
            # Check for state advancement
            if next_state:
                state_change = self.check_state_advancement({"next_state": True})
                if state_change:
                    return state_change
            
            return {
                "type": "response",
                "text": speech
            }
    
    def handle_movement_response(self, movements):
        """Generate and play a response to marker movements."""
        if not movements:
            return
        
        # Don't respond to movements during audio playback
        if self.audio_playing:
            return
        
        print(f"\nResponding to {len(movements)} marker movements...")
        
        # Play movement sound
        self.play_sound_effect("movement")
        
        # Create a description of the movement in terms of narrative elements
        movement_description = []
        for movement in movements:
            marker_id = movement["marker_id"]
            if marker_id in self.marker_mapping:
                element_type = self.marker_mapping[marker_id]
                if element_type in self.selected_elements:
                    element = self.selected_elements[element_type]
                    movement_description.append(f"{element['name']} has moved {movement['distance']:.1f} units.")
        
        # Update narrative context with the movement
        self.update_narrative_context(movement=movements[0])  # Use the first movement for context
        
        # The response depends on the current game state
        if self.game_state == "introduction":
            # In introduction, movement advances to exploration
            narrative_response = self.create_narrative_description(self.selected_elements, stage=self.game_state)
            state_change = self.check_state_advancement(narrative_response)
            if state_change:
                return state_change
        elif self.game_state in ["exploration", "climax"]:
            # In exploration or climax, movements develop the narrative
            narrative_response = self.create_narrative_description(self.selected_elements, stage=self.game_state)
            
            # Update transcript
            self.transcript.append({
                "type": "movement_response",
                "game_state": self.game_state,
                "movements": [{"marker_id": m["marker_id"], "distance": m["distance"]} for m in movements],
                "movement_description": movement_description,
                "gm_response": narrative_response["speech_segments"][0],
                "timestamp": datetime.now().isoformat()
            })
            
            # Play narrative segments
            self.play_narrative_segments(narrative_response)
            
            print("\n--- Response to Movement ---")
            for segment in narrative_response["speech_segments"]:
                print(segment)
            
            # Check for state advancement
            state_change = self.check_state_advancement(narrative_response)
            if state_change:
                return state_change
        
        elif self.game_state == "collapse":
            # In collapse phase, significant movement leads to resolution
            narrative_response = self.create_narrative_description(self.selected_elements, stage="collapse")
            
            # Update transcript
            self.transcript.append({
                "type": "movement_response",
                "game_state": self.game_state,
                "movements": [{"marker_id": m["marker_id"], "distance": m["distance"]} for m in movements],
                "movement_description": movement_description,
                "gm_response": narrative_response["speech_segments"][0],
                "timestamp": datetime.now().isoformat()
            })
            
            # Play narrative segments
            self.play_narrative_segments(narrative_response)
            
            # Check for state advancement
            state_change = self.check_state_advancement(narrative_response)
            if state_change:
                return state_change
    
    def voice_listener_thread(self):
        """Background thread to continuously listen for voice commands."""
        while True:
            # Only listen when not playing audio
            if not self.audio_playing:
                command = self.listen_for_command()
                if command:
                    with self.lock:
                        print(f"\nProcessing command: {command}")
                        result = self.handle_voice_command(command)
                        
                        if result and result["type"] == "exit":
                            self.save_transcript()
                            break
            
            # Short delay to prevent maxing CPU
            time.sleep(0.1)
    
    def check_marker_arrangement(self):
        """Check the current marker arrangement and potentially create a new narrative."""
        marker_changes = self.detect_marker_changes()
        current_time = time.time()
        
        # Complete reset if all markers removed then new ones added
        if len(marker_changes["current"]) >= 3 and self.game_state == "setup":
            # This is a fresh arrangement after clearing
            print("\nDetected new marker arrangement after clearing. Initializing new narrative.")
            return self.initialize_narrative()
            
        # Check for significant movements if we have an active narrative
        if self.game_state != "setup" and current_time - self.last_movement_check >= self.movement_check_interval:
            movements = self.detect_significant_movements()
            self.last_movement_check = current_time
            
            if movements:
                self.handle_movement_response(movements)
                return True
        
        return False
    
    def create_marker_mapping_announcement(self):
        """Create a text announcement of which marker IDs correspond to which narrative elements."""
        mapping_parts = []
        
        # Create the announcement text
        mapping_parts.append("Quantum markers calibrated.")
        
        # Add mappings for markers that are present
        for marker_id, element_type in self.marker_mapping.items():
            if marker_id in self.last_processed_markers and element_type in self.selected_elements:
                element = self.selected_elements[element_type]
                if element:
                    mapping_parts.append(f"Marker {marker_id} resonates with {element['name']}.")
        
        # Add a note about interaction
        mapping_parts.append("Arrange markers to influence the quantum narrative.")
        
        return " ".join(mapping_parts)

    def generate_location(self):
        """Generate a specific location within the current setting based on the goal and narrative elements."""
        if not self.selected_elements["setting"] or not self.selected_elements["goal"]:
            return None
            
        setting = self.selected_elements["setting"]
        goal = self.selected_elements["goal"]
        
        # Create a prompt for Claude to generate a location
        prompt = f"""Based on the following setting and goal, generate a specific location that would be relevant to the narrative:

SETTING:
{setting['name']}: {setting['description']}
Properties: {', '.join(setting['properties'][:2])}

GOAL:
{goal['name']}: {goal['description']}
Challenges: {', '.join(goal['challenges'][:2])}

Generate a specific location that:
1. Fits within the setting
2. Is relevant to achieving the goal
3. Has interesting properties that could affect the narrative
4. Could serve as a meaningful space for character interaction

Format your response as:
<name>Location Name</name>
<description>Detailed description of the location</description>
<properties>Property 1, Property 2, Property 3</properties>
<significance>Why this location matters to the goal</significance>"""
        
        try:
            message = anthropic.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=500,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response = message.content[0].text
            
            # Parse the response
            location = {
                "name": "",
                "description": "",
                "properties": [],
                "significance": ""
            }
            
            if "<name>" in response and "</name>" in response:
                location["name"] = response.split("<name>")[1].split("</name>")[0].strip()
            
            if "<description>" in response and "</description>" in response:
                location["description"] = response.split("<description>")[1].split("</description>")[0].strip()
            
            if "<properties>" in response and "</properties>" in response:
                properties = response.split("<properties>")[1].split("</properties>")[0].strip()
                location["properties"] = [p.strip() for p in properties.split(",")]
            
            if "<significance>" in response and "</significance>" in response:
                location["significance"] = response.split("<significance>")[1].split("</significance>")[0].strip()
            
            return location
            
        except Exception as e:
            print(f"Error generating location: {e}")
            return None

    def play_narrative_segments(self, narrative_response):
        """Play narrative segments with appropriate pauses between them."""
        if not narrative_response.get("speech_segments"):
            return
        
        # Play each speech segment with a pause between them
        for segment in narrative_response["speech_segments"]:
            self.generate_and_play_audio(segment)
            time.sleep(0.5)  # Short pause between segments
        
        # Play instructions if they exist
        if narrative_response.get("instructions"):
            time.sleep(1.0)  # Longer pause before instructions
            self.generate_and_play_audio(narrative_response["instructions"])

    def initialize_narrative(self):
        """Initialize a new narrative based on current marker positions."""
        current_markers = self.get_current_markers()
        
        if not current_markers:
            print("No markers detected. Please place some markers in view of the camera.")
            return False
        
        print(f"\nInitializing narrative with {len(current_markers)} markers...")
        
        # Calculate relationships and patterns
        relationships = self.calculate_marker_relationships(current_markers)
        patterns = self.detect_significant_patterns(current_markers, relationships)
        
        # Select elements for the narrative
        self.selected_elements = self.select_narrative_elements(current_markers, relationships, patterns)
        
        # Generate a specific location within the setting
        self.selected_elements["location"] = self.generate_location()
        
        # Reset narrative context
        self.narrative_context = {
            "recent_speech": [],
            "recent_movements": [],
            "phase_start_time": time.time(),
            "total_movements": 0,
            "last_state_change": time.time()
        }
        
        # Create narrative description
        self.narrative = self.create_narrative_description(self.selected_elements)
        
        # Update game state
        self.game_state = "introduction"
        self.last_scenario_time = time.time()
        self.last_processed_markers = set(current_markers.keys())
        
        # Update marker history
        for marker_id, data in current_markers.items():
            self.marker_history[marker_id] = data
        
        # Save the initial instruction
        self.current_instruction = self.narrative.get("instructions", "")
        
        # Update transcript
        self.transcript.append({
            "type": "narrative_initialization",
            "elements": {
                "protagonist": self.selected_elements["protagonist"]["name"],
                "antagonist": self.selected_elements["antagonist"]["name"],
                "goal": self.selected_elements["goal"]["name"],
                "setting": self.selected_elements["setting"]["name"],
                "location": self.selected_elements["location"]["name"] if self.selected_elements["location"] else None,
                "narrative_structure": self.selected_elements["narrative_structure"]["name"]
            },
            "speech_segments": self.narrative["speech_segments"],
            "instructions": self.narrative.get("instructions", ""),
            "timestamp": datetime.now().isoformat()
        })
        
        # Play initialization sound
        self.play_sound_effect("initialize")
        
        # Play narrative segments
        self.play_narrative_segments(self.narrative)
        
        print("\n=== New Quantum Narrative Initialized ===")
        print(f"Narrative Structure: {self.selected_elements['narrative_structure']['name']}")
        print(f"Protagonist: {self.selected_elements['protagonist']['name']}")
        print(f"Antagonist: {self.selected_elements['antagonist']['name']}")
        print(f"Goal: {self.selected_elements['goal']['name']}")
        print(f"Setting: {self.selected_elements['setting']['name']}")
        if self.selected_elements["location"]:
            print(f"Location: {self.selected_elements['location']['name']}")
        print(f"Tone: {self.selected_elements['tone']['name']}")
        print("\nNarrative Speech:")
        for segment in self.narrative["speech_segments"]:
            print(segment)
        if self.narrative.get("instructions"):
            print("\nInstructions:")
            print(self.narrative["instructions"])
        print("===========================================")
        
        # Create a mapping message to announce which marker corresponds to which entity
        marker_mapping_text = self.create_marker_mapping_announcement()
        
        # Play the mapping announcement after a short delay
        time.sleep(2)
        self.generate_and_play_audio(marker_mapping_text)
        
        return True
    
    def save_transcript(self):
        """Save the current session transcript to a file."""
        try:
            # Create a timestamp for the filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            transcript_file = TRANSCRIPTS_DIR / f"quantum_theater_session_{timestamp}.json"
            
            # Prepare transcript data
            transcript_data = {
                "session_info": {
                    "start_time": self.transcript[0]["timestamp"] if self.transcript else None,
                    "end_time": datetime.now().isoformat(),
                    "game_states": self.completed_phases,
                    "final_state": self.game_state
                },
                "narrative_elements": {
                    "protagonist": self.selected_elements["protagonist"]["name"] if self.selected_elements["protagonist"] else None,
                    "antagonist": self.selected_elements["antagonist"]["name"] if self.selected_elements["antagonist"] else None,
                    "goal": self.selected_elements["goal"]["name"] if self.selected_elements["goal"] else None,
                    "setting": self.selected_elements["setting"]["name"] if self.selected_elements["setting"] else None,
                    "location": self.selected_elements["location"]["name"] if self.selected_elements["location"] else None,
                    "narrative_structure": self.selected_elements["narrative_structure"]["name"] if self.selected_elements["narrative_structure"] else None
                },
                "transcript": self.transcript
            }
            
            # Save to file
            with open(transcript_file, 'w') as f:
                json.dump(transcript_data, f, indent=2)
            
            print(f"\nSession transcript saved to: {transcript_file}")
            
        except Exception as e:
            print(f"Error saving transcript: {e}")
            traceback.print_exc()

    def run(self):
        """Run the main game loop."""
        print("\n=== Quantum Theater .0 ===")
        print("Place markers in view of the camera to initialize a quantum narrative.")
        print("Say 'Oracle help' or 'Oracle clue' to get a hint (5 available).")
        print("Say 'Oracle progress' to advance the narrative when ready.")
        print("Say 'Oracle exit' or 'Oracle quit' to end the session.")
        print("==============================\n")
        
        # Start voice listener thread
        voice_thread = threading.Thread(target=self.voice_listener_thread, daemon=True)
        voice_thread.start()
        
        # Set up initial tracking
        self.current_phase_start_time = time.time()
        
        try:
            while True:
                # Check for marker changes and update narrative if needed
                self.check_marker_arrangement()
                
                # Short delay to prevent maxing CPU
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nProgram interrupted. Saving transcript and exiting...")
            self.save_transcript()
        finally:
            # Clean up pygame mixer
            pygame.mixer.quit()
            print("\nQuantum Theater session ended.")

def main():
    """Main entry point for the Quantum Theater .0 program."""
    try:
        # Check if required packages are installed
        try:
            import speech_recognition as sr
        except ImportError:
            print("SpeechRecognition package is required but not installed.")
            print("Please install it using: pip install SpeechRecognition")
            return
            
        theater = QuantumTheater()
        theater.run()
    except Exception as e:
        print(f"Error running Quantum Theater: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()