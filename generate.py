import rhinoscriptsyntax as rs
import random
import os
import time
import json
import math
from collections import deque

# CONFIG
NUM_VARIATIONS = 15
CELL_SIZE = 1.0      
LAYER_HEIGHT = 2.0   
GRID_X = 10          
GRID_Y = 10
GRID_Z = 25          

# Camera Configuration
CAMERA_DISTANCE_MULTIPLIER = 1.8225
CAMERA_TARGET_Z_FACTOR = 0.5
CAMERA_Z_FACTOR = 0.5

# OUTPUT DIRECTORY
ROOT_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "architecture-ai-engine", "GeometryImagesRhino.nosync")
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)

def get_bounding_box_center_coords(bbox_points):
    if not bbox_points or len(bbox_points) < 8: return None
    min_pt, max_pt = bbox_points[0], bbox_points[6]
    return ((min_pt[0] + max_pt[0]) / 2.0,
            (min_pt[1] + max_pt[1]) / 2.0,
            (min_pt[2] + max_pt[2]) / 2.0)

def setup_angled_perspective_view(target_point, camera_distance, building_height, lens_length,
                                  target_z_factor, camera_z_factor, horizontal_angle_deg):
    angle_rad = math.radians(horizontal_angle_deg)
    direction_xy = (-math.cos(angle_rad), -math.sin(angle_rad))

    cam_x = target_point[0] + direction_xy[0] * camera_distance
    cam_y = target_point[1] + direction_xy[1] * camera_distance

    target_z = building_height * target_z_factor
    camera_z = building_height * camera_z_factor

    camera_location = (cam_x, cam_y, camera_z)
    target_location = list(target_point)
    target_location[2] = target_z

    rs.Command("_-SetActiveViewport Perspective", False)
    rs.ViewCameraTarget(camera=camera_location, target=target_location)
    rs.Command("_-Lens " + str(lens_length), False)

def capture_view(filepath):
    rs.UnselectAllObjects()
    rs.Command("_-SetDisplayMode _Shaded _Enter", True)
    command = (
        '-_ViewCaptureToFile "{}" '
        "Width=512 Height=1024 "
        "LockAspectRatio=Yes "
        "TransparentBackground=No "
        "_Enter"
    ).format(filepath)
    rs.Command(command, False)
    time.sleep(0.1)

def ensure_structural_integrity(grid):
    visited = [[[False]*GRID_Z for _ in range(GRID_Y)] for _ in range(GRID_X)]
    queue = deque()

    for x in range(GRID_X):
        for y in range(GRID_Y):
            if grid[x][y][0] == 1:
                visited[x][y][0] = True
                queue.append((x, y, 0))

    while queue:
        x, y, z = queue.popleft()
        for dx, dy, dz in [(-1,0,0),(1,0,0),(0,-1,0),(0,1,0),(0,0,-1),(0,0,1)]:
            nx, ny, nz = x+dx, y+dy, z+dz
            if 0 <= nx < GRID_X and 0 <= ny < GRID_Y and 0 <= nz < GRID_Z:
                if grid[nx][ny][nz] == 1 and not visited[nx][ny][nz]:
                    visited[nx][ny][nz] = True
                    queue.append((nx, ny, nz))

    removed = 0
    for x in range(GRID_X):
        for y in range(GRID_Y):
            for z in range(GRID_Z):
                if grid[x][y][z] == 1 and not visited[x][y][z]:
                    grid[x][y][z] = 0
                    removed += 1

    return grid, removed

def generate_tower(seed):
    random.seed(seed)
    voxel_grid = [[[0 for _ in range(GRID_Z)] for _ in range(GRID_Y)] for _ in range(GRID_X)]
    
    # 1. Main Core (Forces the fat rectangular top)
    cw = random.randint(4, 7)
    cd = random.randint(4, 7)
    ch = random.randint(20, 25)
    
    # Center the core
    cx = (GRID_X - cw) // 2
    cy = (GRID_Y - cd) // 2
    
    for x in range(cx, cx + cw):
        for y in range(cy, cy + cd):
            for z in range(ch):
                voxel_grid[x][y][z] = 1

    # 2. Stepped Base (Creates the wide bottom that shrinks upward)
    base_h = random.randint(8, 14)
    current_min_x, current_max_x = 0, GRID_X
    current_min_y, current_max_y = 0, GRID_Y
    
    tier_height = 0
    for z in range(base_h):
        # Every 2-4 layers, shrink the bounding box on random sides
        if tier_height > random.randint(2, 4):
            # Shrink, but never smaller than the main core
            if current_min_x < cx and random.random() < 0.6: current_min_x += 1
            if current_max_x > cx + cw and random.random() < 0.6: current_max_x -= 1
            if current_min_y < cy and random.random() < 0.6: current_min_y += 1
            if current_max_y > cy + cd and random.random() < 0.6: current_max_y -= 1
            tier_height = 0
            
        for x in range(current_min_x, current_max_x):
            for y in range(current_min_y, current_max_y):
                voxel_grid[x][y][z] = 1
        tier_height += 1

    # 3. Asymmetric Mid-blocks (Breaks perfect symmetry, adds chunkiness)
    for _ in range(random.randint(1, 3)):
        bw = random.randint(2, 5)
        bd = random.randint(2, 5)
        bh = random.randint(10, ch - 4)
        
        # Clamp to the sides of the core
        bx = cx + random.choice([-2, -1, cw - 2, cw - 1])
        by = cy + random.choice([-2, -1, cd - 2, cd - 1])
        
        bx = max(0, min(bx, GRID_X - bw))
        by = max(0, min(by, GRID_Y - bd))
        
        for x in range(bx, bx + bw):
            for y in range(by, by + bd):
                for z in range(bh):
                    voxel_grid[x][y][z] = 1

    # 4. Vertical Subtraction (The deep split/trench)
    if random.random() < 0.85:
        slot_w = random.randint(1, 2)
        slot_start_z = random.randint(base_h - 2, base_h + 3)
        axis = random.choice(['x', 'y'])
        
        if axis == 'x' and cw >= 4:
            # Cut through X axis
            sx = cx + random.randint(1, cw - slot_w - 1)
            for x in range(sx, sx + slot_w):
                for y in range(GRID_Y):
                    for z in range(slot_start_z, GRID_Z):
                        voxel_grid[x][y][z] = 0
        elif axis == 'y' and cd >= 4:
            # Cut through Y axis
            sy = cy + random.randint(1, cd - slot_w - 1)
            for y in range(sy, sy + slot_w):
                for x in range(GRID_X):
                    for z in range(slot_start_z, GRID_Z):
                        voxel_grid[x][y][z] = 0

    return voxel_grid
# MAIN
rs.EnableRedraw(False)
rs.DeleteObjects(rs.AllObjects())

existing_towers = [d for d in os.listdir(ROOT_DIR) if d.startswith("tower_") and os.path.isdir(os.path.join(ROOT_DIR, d))]
if existing_towers:
    max_idx = max(int(t.split("_")[1]) for t in existing_towers)
    START_IDX = max_idx + 1
else:
    START_IDX = 0

print(f"Starting from tower {START_IDX:03d}")

for idx in range(START_IDX, START_IDX + NUM_VARIATIONS):
    layer_name = f"T{idx}"
    if rs.IsLayer(layer_name): rs.PurgeLayer(layer_name)
    rs.AddLayer(layer_name)

    cell_centers = []
    current_seed = 42 + idx

    grid = generate_tower(current_seed)

    building_objs = []
    vox = 0

    for x in range(GRID_X):
        for y in range(GRID_Y):
            for z in range(GRID_Z):
                if grid[x][y][z] == 1:
                    x0 = x * CELL_SIZE
                    y0 = y * CELL_SIZE
                    z0 = z * LAYER_HEIGHT
                    corners = [
                        (x0, y0, z0),
                        (x0 + CELL_SIZE, y0, z0),
                        (x0 + CELL_SIZE, y0 + CELL_SIZE, z0),
                        (x0, y0 + CELL_SIZE, z0),
                        (x0, y0, z0 + LAYER_HEIGHT),
                        (x0 + CELL_SIZE, y0, z0 + LAYER_HEIGHT),
                        (x0 + CELL_SIZE, y0 + CELL_SIZE, z0 + LAYER_HEIGHT),
                        (x0, y0 + CELL_SIZE, z0 + LAYER_HEIGHT)
                    ]
                    building_objs.append(rs.AddBox(corners))
                    cell_centers.append([x0 + CELL_SIZE/2.0, y0 + CELL_SIZE/2.0, z0 + LAYER_HEIGHT/2.0])
                    vox += 1

    if not building_objs:
        print(f"Tower {idx:03d} resulted in no geometry. Skipping.")
        continue

    rs.ObjectLayer(building_objs, layer_name)

    bbox = rs.BoundingBox(building_objs)
    if bbox:
        move_vector = rs.VectorSubtract((0,0,0), ((bbox[0][0]+bbox[6][0])/2, (bbox[0][1]+bbox[6][1])/2, bbox[0][2]))
        rs.MoveObjects(building_objs, move_vector)

    ground_plane_size = GRID_X * CELL_SIZE * 3.0
    ground_plane = rs.AddPlaneSurface(rs.WorldXYPlane(), ground_plane_size, ground_plane_size)
    if ground_plane:
        rs.MoveObject(ground_plane, (-ground_plane_size/2.0, -ground_plane_size/2.0, 0))

    tower_dir = os.path.join(ROOT_DIR, "tower_%03d" % idx)
    if not os.path.exists(tower_dir):
        os.makedirs(tower_dir)

    tower_bbox_at_origin = rs.BoundingBox(building_objs)
    if tower_bbox_at_origin:
        target_coords = get_bounding_box_center_coords(tower_bbox_at_origin)
        if target_coords:
            building_height = tower_bbox_at_origin[6][2] - tower_bbox_at_origin[0][2]
            building_width = tower_bbox_at_origin[6][0] - tower_bbox_at_origin[0][0]
            building_depth = tower_bbox_at_origin[6][1] - tower_bbox_at_origin[0][1]
            largest_dim = max(building_width, building_depth, building_height)

            cam_dist = largest_dim * CAMERA_DISTANCE_MULTIPLIER

            compass_views = [
                ("northeast", 33),
                ("southeast", 123),
                ("southwest", 213),
                ("northwest", 303)
            ]

            for view_name, angle in compass_views:
                setup_angled_perspective_view(
                    target_coords,
                    cam_dist,
                    building_height,
                    50,
                    CAMERA_TARGET_Z_FACTOR,
                    CAMERA_Z_FACTOR,
                    angle
                )
                filepath = os.path.join(tower_dir, f"{view_name}.png")
                capture_view(filepath)

    if ground_plane: rs.DeleteObject(ground_plane)

    output_data = {
        "tower_info": {
            "ID": idx,
            "grid_size": [GRID_X, GRID_Y, GRID_Z],
            "cell_size": [CELL_SIZE, CELL_SIZE, LAYER_HEIGHT],
            "total_cells": vox,
            "seed": current_seed,
            "prompt": ""
        },
        "cell_centers": cell_centers
    }
    with open(os.path.join(tower_dir, "params.json"), "w") as fp:
        json.dump(output_data, fp, indent=2)

    rs.DeleteObjects(building_objs)
    if rs.IsLayer(layer_name):
        rs.PurgeLayer(layer_name)

    print(f"Generated and captured tower {idx:03d} with {vox} voxels")

rs.EnableRedraw(True)
print(f"\nProcess complete. Generated {NUM_VARIATIONS} towers in {ROOT_DIR}")