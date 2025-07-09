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
    
    # Reference marker IDs for grid corners (any 4 markers can be used)
    REFERENCE_MARKERS = [1, 2, 3, 4]
    
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
    
    # Marker memory system - store last seen positions
    marker_memory = {}  # Store last seen positions of reference markers
    memory_timeout = 90.0  # How long to remember markers (seconds)
    
    # Non-corner marker memory system
    non_corner_marker_memory = {}  # Store last seen positions of non-corner markers
    non_corner_memory_timeout = 10.0  # How long to remember non-corner markers (seconds)
    
    # Create narrative_elements directory if it doesn't exist
    elem_dir = Path('narrative_elements')
    elem_dir.mkdir(exist_ok=True)

    json_file = elem_dir / 'perspective_grid_locations.json'
    marker_data = {}  # Empty dictionary to store marker data
    with open(json_file, 'w') as f:
        json.dump(marker_data, f, indent=4)
    print("JSON file cleared and initialized")

    def get_grid_section(x, y, width, height):
        # Calculate grid section (1-12) in the perspective-corrected space
        # 4 sections wide, 3 sections tall
        section_width = width / 4
        section_height = height / 3
        
        grid_x = min(int(x / section_width), 3)  # 0-3 for 4 columns
        grid_y = min(int(y / section_height), 2)  # 0-2 for 3 rows
        
        # Convert to 1-12 grid numbering (1 is top-left, 12 is bottom-right)
        # Row 1: 1,2,3,4 | Row 2: 5,6,7,8 | Row 3: 9,10,11,12
        return grid_y * 4 + grid_x + 1

    def update_non_corner_marker_memory(ids, corners, current_time):
        """
        Update memory for non-corner markers with 10-second timeout
        """
        if ids is not None:
            for i, marker_id in enumerate(ids):
                if marker_id[0] not in REFERENCE_MARKERS:  # Skip reference markers
                    marker_corners = corners[i][0]
                    center_x = np.mean([corner[0] for corner in marker_corners])
                    center_y = np.mean([corner[1] for corner in marker_corners])
                    
                    non_corner_marker_memory[marker_id[0]] = {
                        'center': (center_x, center_y),
                        'corners': marker_corners.copy(),
                        'timestamp': current_time
                    }
        
        # Clean up old non-corner marker memory
        for marker_id in list(non_corner_marker_memory.keys()):
            if current_time - non_corner_marker_memory[marker_id]['timestamp'] > non_corner_memory_timeout:
                del non_corner_marker_memory[marker_id]

    def get_all_non_corner_markers(current_time):
        """
        Get all non-corner markers (current + memory within timeout)
        """
        all_markers = {}
        
        # Add markers from memory that are still within timeout
        for marker_id, memory_data in non_corner_marker_memory.items():
            if current_time - memory_data['timestamp'] <= non_corner_memory_timeout:
                all_markers[marker_id] = memory_data['center']
        
        return all_markers

    def determine_grid_corners(marker_centers):
        """
        Automatically determine which markers are at which corners
        Returns: (top_left, top_right, bottom_left, bottom_right)
        """
        if len(marker_centers) != 4:
            return None
        
        # Convert to list of (id, center) tuples
        markers = list(marker_centers.items())
        
        # Find the center point of all markers
        center_x = np.mean([center[0] for _, center in markers])
        center_y = np.mean([center[1] for _, center in markers])
        
        # Sort markers by their position relative to center
        top_markers = []
        bottom_markers = []
        
        for marker_id, center in markers:
            if center[1] < center_y:  # Above center
                top_markers.append((marker_id, center))
            else:  # Below center
                bottom_markers.append((marker_id, center))
        
        # Sort top markers by x position (left to right)
        top_markers.sort(key=lambda x: x[1][0])
        bottom_markers.sort(key=lambda x: x[1][0])
        
        # Ensure we have 2 top and 2 bottom markers
        if len(top_markers) != 2 or len(bottom_markers) != 2:
            return None
        
        # Return in order: top-left, top-right, bottom-left, bottom-right
        return (top_markers[0][0], top_markers[1][0], 
                bottom_markers[0][0], bottom_markers[1][0])

    def calculate_perspective_transform(corners, ids, current_time):
        # Initialize arrays to store marker corners and centers
        marker_corners = {}
        marker_centers = {}
        
        # Process each detected marker (only if ids is not None)
        if ids is not None:
            for i, marker_id in enumerate(ids):
                if marker_id[0] in REFERENCE_MARKERS:
                    # Store the corners and calculate center
                    marker_corners[marker_id[0]] = corners[i][0]
                    center_x = np.mean([corner[0] for corner in corners[i][0]])
                    center_y = np.mean([corner[1] for corner in corners[i][0]])
                    marker_centers[marker_id[0]] = (center_x, center_y)
                    
                    # Update marker memory
                    marker_memory[marker_id[0]] = {
                        'center': (center_x, center_y),
                        'corners': corners[i][0].copy(),
                        'timestamp': current_time
                    }
        
        # Clean up old marker memory
        current_markers = set(marker_centers.keys())
        for marker_id in list(marker_memory.keys()):
            if current_time - marker_memory[marker_id]['timestamp'] > memory_timeout:
                del marker_memory[marker_id]
        
        # Combine current detections with recent memory
        all_markers = {}
        for marker_id, center in marker_centers.items():
            all_markers[marker_id] = center
        
        # Add markers from memory that aren't currently detected
        for marker_id, memory_data in marker_memory.items():
            if marker_id not in all_markers:
                all_markers[marker_id] = memory_data['center']
        
        # If we don't have at least 3 reference markers, return None
        if len(all_markers) < 3:
            return None, None
        
        # Determine grid corners automatically
        grid_corners = determine_grid_corners(all_markers)
        if grid_corners is None:
            return None, None
        
        # Use the determined corners to create the transform
        src_points = []
        for marker_id in grid_corners:
            if marker_id in all_markers:
                src_points.append(all_markers[marker_id])
            else:
                # If a corner marker is missing, skip this frame
                return None, None
        
        # Convert to numpy array
        src_points = np.float32(src_points)
        
        # Define destination points for a 3x3 grid
        grid_size = 900  # Size of the grid in pixels
        dst_points = np.float32([
            [0, 0],           # top-left
            [grid_size, 0],   # top-right
            [0, grid_size],   # bottom-left
            [grid_size, grid_size]  # bottom-right
        ])
        
        # Calculate perspective transform
        transform = cv2.getPerspectiveTransform(src_points, dst_points)
        
        return transform, grid_size

    def create_rectified_view(frame, perspective_transform, grid_size, marker_data, ids, corners, marker_memory, current_time):
        """
        Create a rectified view of the camera feed using corner pin transformation
        """
        if perspective_transform is None:
            return None
        
        # Use 1920x1080 resolution for the rectified view
        rectified_width = 1920
        rectified_height = 1080
        
        # Extract marker centers from memory for corner detection
        marker_centers = {}
        for marker_id, memory_data in marker_memory.items():
            if marker_id in REFERENCE_MARKERS:
                marker_centers[marker_id] = memory_data['center']
        
        # Get the source corner points from the detected reference markers
        src_corners = []
        grid_corners = determine_grid_corners(marker_centers)
        
        if grid_corners is None:
            return None
        
        # Get corner positions from memory
        for marker_id in grid_corners:
            if marker_id in marker_memory:
                src_corners.append(marker_memory[marker_id]['center'])
            else:
                return None  # Can't create transform without all corners
        
        # Convert to numpy array and ensure proper order: top-left, top-right, bottom-left, bottom-right
        src_corners = np.float32(src_corners)
        
        # Define destination corners for perfect rectangle (16:9 aspect ratio)
        dst_corners = np.float32([
            [0, 0],                           # top-left
            [rectified_width, 0],             # top-right
            [0, rectified_height],            # bottom-left
            [rectified_width, rectified_height]  # bottom-right
        ])
        
        # Calculate the corner pin transformation matrix
        corner_pin_transform = cv2.getPerspectiveTransform(src_corners, dst_corners)
        
        # Apply the corner pin transformation to the entire frame
        rectified_frame = cv2.warpPerspective(frame, corner_pin_transform, (rectified_width, rectified_height))
        
        # Create a list to track which sections contain markers
        occupied_sections = set()
        
        # Get all non-corner markers (current + memory within timeout)
        all_non_corner_markers = get_all_non_corner_markers(current_time)
        
        # Check all non-corner markers (current and from memory)
        for marker_id, center in all_non_corner_markers.items():
            # Transform marker center to perspective-corrected space
            marker_point = np.array([[center[0], center[1]]], dtype=np.float32)
            marker_point = marker_point.reshape(-1, 1, 2)
            transformed_point = cv2.perspectiveTransform(marker_point, corner_pin_transform)
            
            # Get grid section in perspective-corrected space
            grid_section = get_grid_section(transformed_point[0][0][0], 
                                         transformed_point[0][0][1],
                                         rectified_width, rectified_height)
            occupied_sections.add(grid_section)
        
        # Also check markers from persistent data
        for marker_id, data in marker_data.items():
            if int(marker_id) not in REFERENCE_MARKERS:
                occupied_sections.add(data['grid_section'])
        
        # Draw transparent blue overlay for occupied sections
        overlay = rectified_frame.copy()
        for section in occupied_sections:
            if 1 <= section <= 12:
                # Calculate section boundaries
                row = (section - 1) // 4  # 0, 1, 2
                col = (section - 1) % 4   # 0, 1, 2, 3
                
                x1 = int(col * rectified_width / 4)
                y1 = int(row * rectified_height / 3)
                x2 = int((col + 1) * rectified_width / 4)
                y2 = int((row + 1) * rectified_height / 3)
                
                # Draw semi-transparent blue rectangle
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 0, 0), -1)  # Blue fill
        
        # Blend the overlay with the original frame (transparency effect)
        alpha = 0.3  # Transparency factor (0.0 = fully transparent, 1.0 = fully opaque)
        rectified_frame = cv2.addWeighted(rectified_frame, 1 - alpha, overlay, alpha, 0)
        
        # Draw grid lines on the rectified view
        # Vertical lines (5 lines for 4 sections)
        for i in range(5):
            x = int(i * rectified_width / 4)
            cv2.line(rectified_frame, (x, 0), (x, rectified_height), (0, 255, 0), 2)
        
        # Horizontal lines (4 lines for 3 sections)
        for j in range(4):
            y = int(j * rectified_height / 3)
            cv2.line(rectified_frame, (0, y), (rectified_width, y), (0, 255, 0), 2)
        
        # Add section numbers
        for row in range(3):
            for col in range(4):
                section_num = row * 4 + col + 1
                center_x = int((col + 0.5) * rectified_width / 4)
                center_y = int((row + 0.5) * rectified_height / 3)
                cv2.putText(rectified_frame, str(section_num), (center_x - 10, center_y + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return rectified_frame

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
            
            # Update non-corner marker memory
            update_non_corner_marker_memory(ids, corners, current_time)
            
            # Always try to calculate perspective transform (uses memory if needed)
            perspective_transform, grid_size = calculate_perspective_transform(corners, ids, current_time)
            
            if ids is not None:
                # Draw all detected markers
                cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)
            
            # Draw grid if we have a valid transform
            if perspective_transform is not None:
                # Draw the perspective-corrected grid (4x3)
                grid_points = []
                for i in range(5):  # 5 vertical lines for 4 sections
                    for j in range(4):  # 4 horizontal lines for 3 sections
                        grid_points.append([i * grid_size/4, j * grid_size/3])
                
                # Transform grid points back to original perspective
                grid_points = np.array(grid_points, dtype=np.float32)
                grid_points = grid_points.reshape(-1, 1, 2)
                transformed_points = cv2.perspectiveTransform(grid_points, np.linalg.inv(perspective_transform))
                
                # Draw the grid lines
                # Vertical lines (5 lines for 4 sections)
                for i in range(5):
                    for j in range(3):  # 3 horizontal positions
                        start_idx = i * 4 + j
                        end_idx = i * 4 + j + 1
                        if end_idx < len(transformed_points):
                            cv2.line(display_frame, 
                                    (int(transformed_points[start_idx][0][0]), int(transformed_points[start_idx][0][1])),
                                    (int(transformed_points[end_idx][0][0]), int(transformed_points[end_idx][0][1])),
                                    (0, 255, 0), 2)
                
                # Horizontal lines (4 lines for 3 sections)
                for j in range(4):
                    for i in range(4):  # 4 vertical positions
                        start_idx = i * 4 + j
                        end_idx = (i + 1) * 4 + j
                        if end_idx < len(transformed_points):
                            cv2.line(display_frame,
                                    (int(transformed_points[start_idx][0][0]), int(transformed_points[start_idx][0][1])),
                                    (int(transformed_points[end_idx][0][0]), int(transformed_points[end_idx][0][1])),
                                    (0, 255, 0), 2)
                
                # Process each detected marker for grid position
                if current_time - last_save_time >= save_interval:
                    # Get all non-corner markers (current + memory within timeout)
                    all_non_corner_markers = get_all_non_corner_markers(current_time)
                    
                    for marker_id, center in all_non_corner_markers.items():
                        # Transform marker center to perspective-corrected space
                        marker_point = np.array([[center[0], center[1]]], dtype=np.float32)
                        marker_point = marker_point.reshape(-1, 1, 2)
                        transformed_point = cv2.perspectiveTransform(marker_point, perspective_transform)
                        
                        # Get grid section in perspective-corrected space
                        grid_section = get_grid_section(transformed_point[0][0][0], 
                                                     transformed_point[0][0][1],
                                                     grid_size, grid_size)
                        
                        # Update marker data only if section has changed
                        marker_id_str = str(marker_id)
                        if marker_id_str not in marker_data or marker_data[marker_id_str]["grid_section"] != grid_section:
                            marker_data[marker_id_str] = {
                                "grid_section": grid_section
                            }
                            print(f"Marker {marker_id} moved to grid section {grid_section}")
                    
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
            
            # Display memory status
            memory_count = len(marker_memory)
            status_text.append(f"Memory: {memory_count}/4 reference markers")
            
            # Display marker positions
            y_offset = 30
            for i, text in enumerate(status_text):
                cv2.putText(display_frame, text, (10, y_offset + i*25), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display all known marker positions
            y_offset = 80 + len(status_text) * 25  # Start below the status text
            for marker_id, data in marker_data.items():
                if int(marker_id) not in REFERENCE_MARKERS:  # Skip reference markers
                    text = f"Marker {marker_id}: {data['grid_section']}"
                    cv2.putText(display_frame, text, (10, y_offset), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    y_offset += 25  # Move down for next marker
            
            # Display reference marker status
            y_offset += 25  # Add some space
            cv2.putText(display_frame, "Reference Markers:", (10, y_offset), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            y_offset += 25
            
            for marker_id in REFERENCE_MARKERS:
                if marker_id in marker_memory:
                    age = current_time - marker_memory[marker_id]['timestamp']
                    if age < 0.1:  # Currently detected
                        status = "DETECTED"
                        color = (0, 255, 0)
                    else:  # From memory
                        status = f"MEMORY ({age:.1f}s)"
                        color = (0, 255, 255)
                else:
                    status = "MISSING"
                    color = (0, 0, 255)
                
                cv2.putText(display_frame, f"Marker {marker_id}: {status}", (10, y_offset), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y_offset += 20
            
            # Display non-corner marker status
            y_offset += 25  # Add some space
            cv2.putText(display_frame, "Non-Corner Markers:", (10, y_offset), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            y_offset += 25
            
            # Get all non-corner markers for display
            all_non_corner_markers = get_all_non_corner_markers(current_time)
            
            if all_non_corner_markers:
                for marker_id, center in all_non_corner_markers.items():
                    if marker_id in non_corner_marker_memory:
                        age = current_time - non_corner_marker_memory[marker_id]['timestamp']
                        if age < 0.1:  # Currently detected
                            status = "DETECTED"
                            color = (0, 255, 0)
                        else:  # From memory
                            time_left = non_corner_memory_timeout - age
                            status = f"MEMORY ({time_left:.1f}s left)"
                            color = (0, 255, 255)
                        
                        cv2.putText(display_frame, f"Marker {marker_id}: {status}", (10, y_offset), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        y_offset += 20
            else:
                cv2.putText(display_frame, "No non-corner markers detected", (10, y_offset), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
                y_offset += 20

            # Display the frame
            cv2.imshow('Perspective Grid ArUco Marker Detection', display_frame)
            
            # Create and display rectified view
            if perspective_transform is not None:
                rectified_frame = create_rectified_view(frame, perspective_transform, grid_size, marker_data, ids, corners, marker_memory, current_time)
                if rectified_frame is not None:
                    cv2.imshow('Rectified Camera View', rectified_frame)
            else:
                # If no transform available, show a blank or message frame
                blank_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)  # 1920x1080 resolution
                cv2.putText(blank_frame, "Waiting for 4 reference markers...", (700, 540),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.imshow('Rectified Camera View', blank_frame)

            # Break loop with 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Clean up
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_aruco_markers()
