import cv2
import numpy as np
import json
import time
from datetime import datetime
from pathlib import Path

def detect_aruco_markers():
    # Configuration flags
    USE_GRAYSCALE = False   # Set to True for grayscale conversion
    USE_THRESHOLD = False   # Set to True for thresholding
    THRESHOLD_VALUE = 0  # Threshold value (0-255)
    THRESHOLD_TYPE = cv2.THRESH_OTSU  # Threshold type
    
    # Reference marker IDs for grid corners (in order: top-left, top-right, bottom-left, bottom-right)
    REFERENCE_MARKERS = [74, 79, 62, 67]
    
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
    
    # Default parameters with comments about which ones are most important to adjust
    parameters.adaptiveThreshWinSizeMin = 3  # Default: 3
    parameters.adaptiveThreshWinSizeMax = 23  # Default: 23
    parameters.adaptiveThreshWinSizeStep = 10  # Default: 10
    parameters.adaptiveThreshConstant = 7  # Default: 7 - Important: Controls threshold sensitivity
    parameters.minMarkerPerimeterRate = 0.03  # Default: 0.03 - Important: Controls minimum marker size
    parameters.maxMarkerPerimeterRate = 4.0  # Default: 4.0 - Important: Controls maximum marker size
    parameters.polygonalApproxAccuracyRate = 0.03  # Default: 0.03
    parameters.minCornerDistanceRate = 0.05  # Default: 0.05
    parameters.minMarkerDistanceRate = 0.05  # Default: 0.05
    parameters.minDistanceToBorder = 3  # Default: 3
    parameters.minOtsuStdDev = 5.0  # Default: 5.0 - Important: Controls threshold sensitivity
    parameters.perspectiveRemovePixelPerCell = 4  # Default: 4
    parameters.perspectiveRemoveIgnoredMarginPerCell = 0.13  # Default: 0.13
    parameters.maxErroneousBitsInBorderRate = 0.35  # Default: 0.35 - Important: Controls error tolerance
    parameters.errorCorrectionRate = 0.5  # Default: 0.6 - Important: Controls error correction
    
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    # Initialize variables for timing
    last_save_time = 0
    save_interval = 1  # second
    
    # Create narrative_elements directory if it doesn't exist
    elem_dir = Path('narrative_elements')
    elem_dir.mkdir(exist_ok=True)

    json_file = elem_dir / 'perspective_grid_locations.json'
    marker_data = {}  # Empty dictionary to store marker data
    with open(json_file, 'w') as f:
        json.dump(marker_data, f, indent=4)
    print("JSON file cleared and initialized")

    def get_grid_section(x, y, width, height):
        # Calculate grid section (1-9) in the perspective-corrected space
        section_width = width / 3
        section_height = height / 3
        
        grid_x = min(int(x / section_width), 2)
        grid_y = min(int(y / section_height), 2)
        
        # Convert to 1-9 grid numbering (1 is top-left, 9 is bottom-right)
        return grid_y * 3 + grid_x + 1

    def calculate_perspective_transform(corners, ids):
        # Initialize arrays to store marker corners and centers
        marker_corners = {}
        marker_centers = {}
        
        # Process each detected marker
        for i, marker_id in enumerate(ids):
            if marker_id[0] in REFERENCE_MARKERS:
                # Store the corners and calculate center
                marker_corners[marker_id[0]] = corners[i][0]
                center_x = np.mean([corner[0] for corner in corners[i][0]])
                center_y = np.mean([corner[1] for corner in corners[i][0]])
                marker_centers[marker_id[0]] = (center_x, center_y)
        
        # If we don't have all reference markers, return None
        if len(marker_centers) != 4:
            return None, None
        
        # Calculate the average orientation of the markers
        orientations = {}
        for marker_id in REFERENCE_MARKERS:
            corners = marker_corners[marker_id]
            # Calculate orientation based on marker corners
            top_left = corners[0]
            top_right = corners[1]
            bottom_right = corners[2]
            bottom_left = corners[3]
            
            # Calculate vectors for top and left edges
            top_vector = top_right - top_left
            left_vector = bottom_left - top_left
            
            # Store orientation vectors
            orientations[marker_id] = {
                'top': top_vector,
                'left': left_vector,
                'center': marker_centers[marker_id]
            }
        
        # Calculate average orientation
        avg_top = np.mean([o['top'] for o in orientations.values()], axis=0)
        avg_left = np.mean([o['left'] for o in orientations.values()], axis=0)
        
        # Normalize vectors
        avg_top = avg_top / np.linalg.norm(avg_top)
        avg_left = avg_left / np.linalg.norm(avg_left)
        
        # Calculate grid corners based on average orientation
        grid_size = 900  # Size of the grid in pixels
        src_points = []
        
        for marker_id in REFERENCE_MARKERS:
            center = orientations[marker_id]['center']
            # Calculate corner position based on average orientation
            if marker_id == REFERENCE_MARKERS[0]:  # top-left
                src_points.append(center)
            elif marker_id == REFERENCE_MARKERS[1]:  # top-right
                src_points.append(center)
            elif marker_id == REFERENCE_MARKERS[2]:  # bottom-left
                src_points.append(center)
            elif marker_id == REFERENCE_MARKERS[3]:  # bottom-right
                src_points.append(center)
        
        # Convert to numpy array
        src_points = np.float32(src_points)
        
        # Define destination points for a 3x3 grid
        dst_points = np.float32([
            [0, 0],           # top-left
            [grid_size, 0],   # top-right
            [0, grid_size],   # bottom-left
            [grid_size, grid_size]  # bottom-right
        ])
        
        # Calculate perspective transform
        transform = cv2.getPerspectiveTransform(src_points, dst_points)
        
        return transform, grid_size

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
                
                # Use Otsu's automatic thresholding
                _, processed_frame = cv2.threshold(gray_for_threshold, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                display_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)

            # Detect ArUco markers
            corners, ids, rejected = detector.detectMarkers(processed_frame)
            
            current_time = time.time()
            
            if ids is not None:
                # Draw all detected markers
                cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)
                
                # Calculate perspective transform based on marker orientations
                perspective_transform, grid_size = calculate_perspective_transform(corners, ids)
                
                if perspective_transform is not None:
                    # Draw the perspective-corrected grid
                    grid_points = []
                    for i in range(4):
                        for j in range(4):
                            grid_points.append([i * grid_size/3, j * grid_size/3])
                    
                    # Transform grid points back to original perspective
                    grid_points = np.array(grid_points, dtype=np.float32)
                    grid_points = grid_points.reshape(-1, 1, 2)
                    transformed_points = cv2.perspectiveTransform(grid_points, np.linalg.inv(perspective_transform))
                    
                    # Draw the grid lines
                    for i in range(4):
                        # Vertical lines
                        cv2.line(display_frame, 
                                (int(transformed_points[i][0][0]), int(transformed_points[i][0][1])),
                                (int(transformed_points[i+12][0][0]), int(transformed_points[i+12][0][1])),
                                (0, 255, 0), 2)
                        # Horizontal lines
                        cv2.line(display_frame,
                                (int(transformed_points[i*4][0][0]), int(transformed_points[i*4][0][1])),
                                (int(transformed_points[i*4+3][0][0]), int(transformed_points[i*4+3][0][1])),
                                (0, 255, 0), 2)
                    
                    # Process each detected marker for grid position
                    if current_time - last_save_time >= save_interval:
                        for i, marker_id in enumerate(ids):
                            if marker_id[0] not in REFERENCE_MARKERS:  # Skip reference markers
                                marker_corners = corners[i][0]
                                center_x = int(np.mean([corner[0] for corner in marker_corners]))
                                center_y = int(np.mean([corner[1] for corner in marker_corners]))
                                
                                # Transform marker center to perspective-corrected space
                                marker_point = np.array([[center_x, center_y]], dtype=np.float32)
                                marker_point = marker_point.reshape(-1, 1, 2)
                                transformed_point = cv2.perspectiveTransform(marker_point, perspective_transform)
                                
                                # Get grid section in perspective-corrected space
                                grid_section = get_grid_section(transformed_point[0][0][0], 
                                                             transformed_point[0][0][1],
                                                             grid_size, grid_size)
                                
                                # Update marker data only if section has changed
                                marker_id_str = str(marker_id[0])
                                if marker_id_str not in marker_data or marker_data[marker_id_str]["grid_section"] != grid_section:
                                    marker_data[marker_id_str] = {
                                        "grid_section": grid_section
                                    }
                                    print(f"Marker {marker_id[0]} moved to grid section {grid_section}")
                        
                        # Save to JSON file
                        with open(json_file, 'w') as f:
                            json.dump(marker_data, f, indent=4)
                        
                        last_save_time = current_time

            # Add status text
            status_text = []
            if USE_GRAYSCALE:
                status_text.append("Grayscale: ON")
            if USE_THRESHOLD:
                status_text.append(f"Threshold: ON ({THRESHOLD_VALUE})")
            
            # Display marker positions
            y_offset = 30
            for i, text in enumerate(status_text):
                cv2.putText(display_frame, text, (10, y_offset + i*25), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display all known marker positions
            y_offset = 80  # Start below the status text
            for marker_id, data in marker_data.items():
                if int(marker_id) not in REFERENCE_MARKERS:  # Skip reference markers
                    text = f"Marker {marker_id}: {data['grid_section']}"
                    cv2.putText(display_frame, text, (10, y_offset), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    y_offset += 25  # Move down for next marker

            # Display the frame
            cv2.imshow('Perspective Grid ArUco Marker Detection', display_frame)

            # Break loop with 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Clean up
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_aruco_markers()
