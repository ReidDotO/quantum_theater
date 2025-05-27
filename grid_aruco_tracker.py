import cv2
import numpy as np
import json
import time
from datetime import datetime
from pathlib import Path

def detect_aruco_markers():
    # Configuration flags
    USE_GRAYSCALE = True   # Set to True for grayscale conversion
    USE_THRESHOLD = False   # Set to True for thresholding
    THRESHOLD_VALUE = 0  # Threshold value (0-255)
    THRESHOLD_TYPE = cv2.THRESH_OTSU  # Threshold type
    
    # Initialize the camera
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    # Check if camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Set up ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    # Initialize variables for timing
    last_save_time = 0
    save_interval = 1  # second
    
    # Create narrative_elements directory if it doesn't exist
    elem_dir = Path('narrative_elements')
    elem_dir.mkdir(exist_ok=True)

    json_file = elem_dir / 'grid_locations.json'
    marker_data = {}  # Empty dictionary to store marker data
    with open(json_file, 'w') as f:
        json.dump(marker_data, f, indent=4)
    print("JSON file cleared and initialized")

    def get_grid_section(x, y, frame_width, frame_height):
        # Calculate grid section (1-9)
        section_width = frame_width / 3
        section_height = frame_height / 3
        
        grid_x = min(int(x / section_width), 2)
        grid_y = min(int(y / section_height), 2)
        
        # Convert to 1-9 grid numbering (1 is top-left, 9 is bottom-right)
        return grid_y * 3 + grid_x + 1

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame.")
                break

            # Create a copy of the frame for display
            display_frame = frame.copy()
            
            # Process frame for ArUco detection
            processed_frame = frame.copy()
            
            # Convert to grayscale if enabled
            if USE_GRAYSCALE:
                processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY)
                display_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)
            
            # Apply thresholding if enabled
            if USE_THRESHOLD:
                if len(processed_frame.shape) == 3:
                    gray_for_threshold = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray_for_threshold = processed_frame
                
                _, processed_frame = cv2.threshold(gray_for_threshold, THRESHOLD_VALUE, 255, THRESHOLD_TYPE)
                display_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)

            # Detect ArUco markers
            corners, ids, rejected = detector.detectMarkers(processed_frame)
            
            current_time = time.time()
            
            # Draw grid lines
            height, width = display_frame.shape[:2]
            for i in range(1, 3):
                # Vertical lines
                cv2.line(display_frame, (width * i // 3, 0), (width * i // 3, height), (0, 255, 0), 2)
                # Horizontal lines
                cv2.line(display_frame, (0, height * i // 3), (width, height * i // 3), (0, 255, 0), 2)
            
            # If markers are detected and it's time to save
            if ids is not None and (current_time - last_save_time) >= save_interval:
                # Draw markers on display frame
                cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)
                
                # Process each detected marker
                for i in range(len(ids)):
                    marker_id = str(ids[i][0])
                    
                    # Calculate marker center
                    marker_corners = corners[i][0]
                    center_x = int(np.mean([corner[0] for corner in marker_corners]))
                    center_y = int(np.mean([corner[1] for corner in marker_corners]))
                    
                    # Get grid section
                    grid_section = get_grid_section(center_x, center_y, width, height)
                    
                    # Update marker data only if section has changed
                    if marker_id not in marker_data or marker_data[marker_id]["grid_section"] != grid_section:
                        marker_data[marker_id] = {
                            "grid_section": grid_section
                        }
                        print(f"Marker {marker_id} moved to grid section {grid_section}")
                
                # Save to JSON file
                with open(json_file, 'w') as f:
                    json.dump(marker_data, f, indent=4)
                    
                last_save_time = current_time
            
            # Always draw markers even if not saving
            elif ids is not None:
                cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)

            # Add status text
            status_text = []
            if USE_GRAYSCALE:
                status_text.append("Grayscale: ON")
            if USE_THRESHOLD:
                status_text.append(f"Threshold: ON ({THRESHOLD_VALUE})")
            
            if status_text:
                y_offset = 30
                for i, text in enumerate(status_text):
                    cv2.putText(display_frame, text, (10, y_offset + i*25), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Display the frame
            cv2.imshow('Grid ArUco Marker Detection', display_frame)

            # Break loop with 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Clean up
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_aruco_markers()
