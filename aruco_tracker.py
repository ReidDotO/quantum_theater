import cv2
import numpy as np
import json
import time
from datetime import datetime
from pathlib import Path

def detect_aruco_markers():
    # Configuration flags
    USE_GRAYSCALE = True   # Set to True for grayscale conversion
    USE_THRESHOLD = True   # Set to True for thresholding
    THRESHOLD_VALUE = 127  # Threshold value (0-255)
    THRESHOLD_TYPE = cv2.THRESH_OTSU  # Threshold type
    
    # Alternative threshold types:
    # cv2.THRESH_BINARY_INV
    # cv2.THRESH_TRUNC
    # cv2.THRESH_TOZERO
    # cv2.THRESH_TOZERO_INV
    # cv2.THRESH_OTSU (automatic thresholding)
    
    # Initialize the camera
    cap = cv2.VideoCapture(4)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960) # Set width to 1280 pixels
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540) # Set height to 720 pixels
    
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

    json_file = elem_dir / 'marker_positions.json'
    marker_data = {}  # Empty dictionary to store marker data
    with open(json_file, 'w') as f:
        json.dump(marker_data, f, indent=4)
    print("JSON file cleared and initialized")

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
                # Convert back to BGR for display purposes
                display_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)
            
            # Apply thresholding if enabled
            if USE_THRESHOLD:
                if len(processed_frame.shape) == 3:  # If the frame is still in color
                    gray_for_threshold = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray_for_threshold = processed_frame
                
                # Apply threshold
                _, processed_frame = cv2.threshold(gray_for_threshold, THRESHOLD_VALUE, 255, THRESHOLD_TYPE)
                
                # Convert back to BGR for display purposes
                display_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)

            # Detect ArUco markers on the processed frame
            corners, ids, rejected = detector.detectMarkers(processed_frame)
            
            current_time = time.time()
            
            # If markers are detected and it's time to save (1 second interval)
            if ids is not None and (current_time - last_save_time) >= save_interval:
                # Draw markers on display frame
                cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)
                
                # Process each detected marker
                for i in range(len(ids)):
                    marker_id = str(ids[i][0])  # Convert to string for JSON key
                    
                    # Calculate marker center
                    marker_corners = corners[i][0]
                    center_x = int(np.mean([corner[0] for corner in marker_corners]))
                    center_y = int(np.mean([corner[1] for corner in marker_corners]))
                    
                    # Update or create marker data
                    if marker_id in marker_data:
                        marker_data[marker_id]["position"]["x"] = center_x
                        marker_data[marker_id]["position"]["y"] = center_y
                        #marker_data[marker_id]["times_seen"] += 1
                    else:
                        marker_data[marker_id] = {
                            "position": {
                                "x": center_x,
                                "y": center_y
                            }#,
                            #"times_seen": 1
                        }
                    
                    print(f"Marker {marker_id} updated - Position: ({center_x}, {center_y})") #, Times seen: {marker_data[marker_id]['times_seen']}
                
                # Save to JSON file once per second
                with open(json_file, 'w') as f:
                    json.dump(marker_data, f, indent=4)
                    
                last_save_time = current_time
            
            # Always draw markers even if not saving
            elif ids is not None:
                cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)

            # Add status text to display frame
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
            cv2.imshow('ArUco Marker Detection', display_frame)

            # Break loop with 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Clean up
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_aruco_markers()