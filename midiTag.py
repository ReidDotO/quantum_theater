import json
import time
import mido
from pathlib import Path
import threading
import sys

class MIDIGridController:
    def __init__(self, port_name="loopMIDI Port 1"):
        """
        Initialize MIDI controller that maps grid positions to MIDI CC values
        
        Grid mapping:
        - Sections 1-4 -> CC11 (Expression)
        - Sections 5-8 -> CC12 (Effect Control 1)
        - Sections 9-12 -> CC13 (Effect Control 2)
        
        Values are scaled based on section position within each group
        """
        self.port_name = port_name
        self.midi_port = None
        self.running = False
        self.last_values = {
            11: 0,  # CC11 - Sections 1-4
            12: 0,  # CC12 - Sections 5-8
            13: 0   # CC13 - Sections 9-12
        }
        
        # Panning settings for CC values
        self.cc_panning = {
            11: {'active': False, 'values': [], 'current_index': 0, 'last_pan_time': 0},
            12: {'active': False, 'values': [], 'current_index': 0, 'last_pan_time': 0},
            13: {'active': False, 'values': [], 'current_index': 0, 'last_pan_time': 0}
        }
        self.pan_interval = 0.5  # Time between panning steps (seconds)
        
        # Track which notes are currently playing
        self.active_notes = set()
        
        # Arpeggiator settings
        self.arpeggio_notes = []  # List of notes to arpeggiate through
        self.current_arpeggio_index = 0
        self.last_arpeggio_time = 0
        self.arpeggio_interval = 0.2  # Time between arpeggio steps (seconds)
        
        # Grid section mappings (CC number, CC value, MIDI note)
        self.section_mappings = {
            # CC11: Sections 1-4
            1: (11, 0, 60),    # CC11, value 0, note C4
            2: (11, 42, 62),   # CC11, value 42, note D4
            3: (11, 84, 64),   # CC11, value 84, note E4
            4: (11, 127, 65),  # CC11, value 127, note F4
            
            # CC12: Sections 5-8
            5: (12, 0, 67),    # CC12, value 0, note G4
            6: (12, 42, 69),   # CC12, value 42, note A4
            7: (12, 84, 71),   # CC12, value 84, note B4
            8: (12, 127, 72),  # CC12, value 127, note C5
            
            # CC13: Sections 9-12
            9: (13, 0, 74),    # CC13, value 0, note D5
            10: (13, 42, 76),  # CC13, value 42, note E5
            11: (13, 84, 77),  # CC13, value 84, note F5
            12: (13, 127, 79)  # CC13, value 127, note G5
        }
        
        self.setup_midi_port()
    
    def setup_midi_port(self):
        """Setup MIDI port"""
        try:
            # Try to create virtual MIDI port first
            self.midi_port = mido.open_output(self.port_name, virtual=True)
            print(f"MIDI port '{self.port_name}' created successfully")
        except Exception as e:
            print(f"Virtual MIDI port not supported: {e}")
            print("Available ports:")
            available_ports = mido.get_output_names()
            for port in available_ports:
                print(f"  - {port}")
            
            if not available_ports:
                print("No MIDI output ports available.")
                print("Please install a virtual MIDI driver like:")
                print("  - loopMIDI (https://www.tobias-erichsen.de/software/loopmidi.html)")
                print("  - rtpMIDI (Windows built-in)")
                print("  - MIDI Yoke")
                sys.exit(1)
            
            # Try to use the specified port name if it exists
            if self.port_name in available_ports:
                try:
                    self.midi_port = mido.open_output(self.port_name)
                    print(f"Using MIDI port: {self.port_name}")
                except Exception as e2:
                    print(f"Error opening MIDI port {self.port_name}: {e2}")
                    sys.exit(1)
            else:
                # Fall back to first available port
                try:
                    self.midi_port = mido.open_output(available_ports[0])
                    print(f"Using existing MIDI port: {available_ports[0]}")
                except Exception as e2:
                    print(f"Error opening MIDI port: {e2}")
                    sys.exit(1)
    
    def send_midi_cc(self, cc_number, value):
        """Send MIDI CC message"""
        if self.midi_port and self.last_values[cc_number] != value:
            message = mido.Message('control_change', control=cc_number, value=value)
            self.midi_port.send(message)
            self.last_values[cc_number] = value
            print(f"MIDI CC{cc_number}: {value}")
    
    def send_midi_note(self, note, velocity=64, note_on=True):
        """Send MIDI note message"""
        if self.midi_port:
            if note_on:
                message = mido.Message('note_on', note=note, velocity=velocity)
                print(f"MIDI Note ON: {note} (velocity: {velocity})")
            else:
                message = mido.Message('note_off', note=note, velocity=0)
                print(f"MIDI Note OFF: {note}")
            self.midi_port.send(message)
    
    def calculate_cc_values(self, marker_data, current_time):
        """
        Calculate MIDI CC values based on marker positions with panning
        
        Returns dict with CC numbers as keys and current value for each CC
        """
        cc_values = {11: 0, 12: 0, 13: 0}
        
        # Collect all values for each CC
        cc_all_values = {11: [], 12: [], 13: []}
        
        for marker_id, data in marker_data.items():
            grid_section = data.get('grid_section')
            
            if grid_section in self.section_mappings:
                cc_number, value, note = self.section_mappings[grid_section]
                cc_all_values[cc_number].append(value)
        
        # Handle panning for each CC
        for cc_number in [11, 12, 13]:
            values = cc_all_values[cc_number]
            
            if len(values) == 0:
                # No markers in this CC range
                self.cc_panning[cc_number]['active'] = False
                cc_values[cc_number] = 0
            elif len(values) == 1:
                # Single marker, no panning needed
                self.cc_panning[cc_number]['active'] = False
                cc_values[cc_number] = values[0]
            else:
                # Multiple markers, enable panning
                if not self.cc_panning[cc_number]['active'] or set(values) != set(self.cc_panning[cc_number]['values']):
                    # Start new panning sequence
                    self.cc_panning[cc_number]['active'] = True
                    self.cc_panning[cc_number]['values'] = sorted(values)
                    self.cc_panning[cc_number]['current_index'] = 0
                    self.cc_panning[cc_number]['last_pan_time'] = current_time
                    cc_values[cc_number] = values[0]
                else:
                    # Continue panning
                    if current_time - self.cc_panning[cc_number]['last_pan_time'] >= self.pan_interval:
                        # Move to next value in sequence
                        self.cc_panning[cc_number]['current_index'] = (self.cc_panning[cc_number]['current_index'] + 1) % len(self.cc_panning[cc_number]['values'])
                        self.cc_panning[cc_number]['last_pan_time'] = current_time
                    
                    # Get current value
                    current_index = self.cc_panning[cc_number]['current_index']
                    cc_values[cc_number] = self.cc_panning[cc_number]['values'][current_index]
        
        return cc_values
    
    def handle_midi_notes(self, marker_data, current_time):
        """
        Handle MIDI note on/off messages based on marker positions with arpeggiation
        
        Returns set of currently active sections
        """
        current_sections = set()
        current_notes = set()
        
        for marker_id, data in marker_data.items():
            grid_section = data.get('grid_section')
            
            if grid_section in self.section_mappings:
                current_sections.add(grid_section)
                _, _, note = self.section_mappings[grid_section]
                current_notes.add(note)
        
        # Handle note off for notes that are no longer active
        notes_to_remove = set()
        for note in self.active_notes:
            if note not in current_notes:
                self.send_midi_note(note, velocity=0, note_on=False)
                notes_to_remove.add(note)
        
        # Remove stopped notes from active set
        self.active_notes -= notes_to_remove
        
        # Update arpeggio notes list
        self.arpeggio_notes = sorted(list(current_notes))
        
        # Handle arpeggiation
        if self.arpeggio_notes:
            # Check if it's time for the next arpeggio step
            if current_time - self.last_arpeggio_time >= self.arpeggio_interval:
                # Turn off all currently playing notes
                for note in self.active_notes:
                    self.send_midi_note(note, velocity=0, note_on=False)
                
                # Play the next note in the arpeggio
                if self.arpeggio_notes:
                    note_to_play = self.arpeggio_notes[self.current_arpeggio_index % len(self.arpeggio_notes)]
                    self.send_midi_note(note_to_play, velocity=64, note_on=True)
                    
                    # Update active notes set
                    self.active_notes = {note_to_play}
                    
                    # Move to next note in sequence
                    self.current_arpeggio_index += 1
                    self.last_arpeggio_time = current_time
        else:
            # No notes to play, clear active notes
            for note in self.active_notes:
                self.send_midi_note(note, velocity=0, note_on=False)
            self.active_notes.clear()
            self.current_arpeggio_index = 0
        
        return current_sections
    
    def read_grid_locations(self):
        """Read the perspective grid locations JSON file"""
        json_file = Path('narrative_elements/perspective_grid_locations.json')
        
        if not json_file.exists():
            print(f"Warning: {json_file} not found")
            return {}
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            return {}
    
    def run(self, update_interval=0.1):
        """
        Main loop that continuously reads grid positions and sends MIDI signals
        
        Args:
            update_interval: Time between updates in seconds
        """
        self.running = True
        print(f"Starting MIDI Grid Controller (update interval: {update_interval}s)")
        print("Press Ctrl+C to stop")
        
        try:
            while self.running:
                # Get current time
                current_time = time.time()
                
                # Read current marker positions
                marker_data = self.read_grid_locations()
                
                if marker_data:
                    # Handle MIDI notes (note on/off based on marker positions with arpeggiation)
                    self.handle_midi_notes(marker_data, current_time)
                    
                    # Calculate CC values based on marker positions with panning
                    cc_values = self.calculate_cc_values(marker_data, current_time)
                    
                    # Send MIDI CC messages
                    for cc_number, value in cc_values.items():
                        self.send_midi_cc(cc_number, value)
                
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            print("\nStopping MIDI Grid Controller...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up MIDI port"""
        if self.midi_port:
            self.midi_port.close()
            print("MIDI port closed")
    
    def print_status(self):
        """Print current status and mapping information"""
        print("\n=== MIDI Grid Controller Status ===")
        print(f"MIDI Port: {self.port_name}")
        print("\nGrid Section Mappings:")
        print("Sections 1-4 -> CC11 (Expression)")
        print("  Section 1: CC11 = 0, Note C4 (60)")
        print("  Section 2: CC11 = 42, Note D4 (62)")
        print("  Section 3: CC11 = 84, Note E4 (64)")
        print("  Section 4: CC11 = 127, Note F4 (65)")
        print("\nSections 5-8 -> CC12 (Effect Control 1)")
        print("  Section 5: CC12 = 0, Note G4 (67)")
        print("  Section 6: CC12 = 42, Note A4 (69)")
        print("  Section 7: CC12 = 84, Note B4 (71)")
        print("  Section 8: CC12 = 127, Note C5 (72)")
        print("\nSections 9-12 -> CC13 (Effect Control 2)")
        print("  Section 9:  CC13 = 0, Note D5 (74)")
        print("  Section 10: CC13 = 42, Note E5 (76)")
        print("  Section 11: CC13 = 84, Note F5 (77)")
        print("  Section 12: CC13 = 127, Note G5 (79)")
        print("\nNote: Multiple markers in the same CC range will pan between values")
        print("Notes will arpeggiate through active sections every 0.2 seconds")
        print("CC values will pan between multiple markers every 0.5 seconds")
        print("=" * 40)

def main():
    """Main function to run the MIDI Grid Controller"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MIDI Grid Controller for Quantum Theater')
    parser.add_argument('--port', default='loopMIDI Port 1', 
                       help='MIDI port name (default: loopMIDI Port 1)')
    parser.add_argument('--interval', type=float, default=0.1,
                       help='Update interval in seconds (default: 0.1)')
    parser.add_argument('--arpeggio-speed', type=float, default=0.2,
                       help='Arpeggio speed in seconds between notes (default: 0.2)')
    parser.add_argument('--pan-speed', type=float, default=0.5,
                       help='CC panning speed in seconds between values (default: 0.5)')
    parser.add_argument('--status', action='store_true',
                       help='Show status and mapping information')
    
    args = parser.parse_args()
    
    # Create controller
    controller = MIDIGridController(args.port)
    
    # Set arpeggio speed
    controller.arpeggio_interval = args.arpeggio_speed
    
    # Set panning speed
    controller.pan_interval = args.pan_speed
    
    if args.status:
        controller.print_status()
        return
    
    # Run the controller
    controller.run(args.interval)

if __name__ == "__main__":
    main()
