import rhinoscriptsyntax as rs
import random
import os
import time
import json
import math
from collections import deque

# --- CONFIG ---
NUM_VARIATIONS = 5
CELL_SIZE = 1.0      # x, y dimension
LAYER_HEIGHT = 2.0   # z dimension (tall voxels)
GRID_X = 10          # fixed 10x10 base
GRID_Y = 10
GRID_Z = 25          # 25 layers height

# --- Camera Configuration ---
CAMERA_DISTANCE_MULTIPLIER = 1.8225
CAMERA_TARGET_Z_FACTOR = 0.5
CAMERA_Z_FACTOR = 0.5


# --- OUTPUT DIRECTORY ---
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
    """Remove any voxels not connected to ground via face-adjacency (6-connectivity BFS)."""
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
    """Generate tower: clean stacked zones with directional setbacks, through-cuts, split peaks."""
    random.seed(seed)

    voxel_grid = [[[0 for _ in range(GRID_Z)] for _ in range(GRID_Y)] for _ in range(GRID_X)]

    # --- Step 1: Zone heights ---
    # References show bottom ~40-50% is wide base mass, tower rises from midpoint
    num_zones = random.randint(2, 4)
    zones = []

    # Base (podium) takes 40-50% of height
    base_layers = random.randint(10, 13)  # 40-52% of 25

    if num_zones == 2:
        # Simple: big podium + tower
        zones = [base_layers, GRID_Z - base_layers]
    elif num_zones == 3:
        # Podium + mid transition + tower
        mid_h = random.randint(3, 5)
        pod_h = base_layers - mid_h
        pod_h = max(pod_h, 5)
        mid_h = base_layers - pod_h
        tower_h = GRID_Z - pod_h - mid_h
        zones = [pod_h, mid_h, tower_h]
    else:
        # 4 zones: podium + 2 mid + tower
        mid1_h = random.randint(2, 4)
        mid2_h = random.randint(2, 4)
        pod_h = base_layers - mid1_h - mid2_h
        pod_h = max(pod_h, 4)
        # Recalc mids to fit
        leftover_base = base_layers - pod_h
        mid1_h = leftover_base // 2
        mid2_h = leftover_base - mid1_h
        tower_h = GRID_Z - pod_h - mid1_h - mid2_h
        zones = [pod_h, mid1_h, mid2_h, tower_h]

    # --- Step 2: Footprints with composition variety ---
    #   standard   - wide base, setback tower (classic taper)
    #   rectangular - minimal setbacks, nearly uniform width throughout
    comp_type = random.choice(['standard', 'rectangular'])

    footprints = []
    base_fp = [[1]*GRID_Y for _ in range(GRID_X)]
    footprints.append(base_fp)

    for i in range(1, len(zones)):
        prev = footprints[i - 1]

        # Setback amount depends on composition type
        if comp_type == 'rectangular':
            sb_type = random.choice(['centered_tiny', 'flush_edge_tiny', 'none'])
        else:
            # Standard: directional setbacks
            r = random.random()
            if r < 0.35:
                sb_type = 'flush_edge'
            elif r < 0.70:
                sb_type = 'flush_corner'
            elif r < 0.90:
                sb_type = 'centered_shrink'
            else:
                sb_type = 'centered_double'

        nfp = [[prev[x][y] for y in range(GRID_Y)] for x in range(GRID_X)]

        if sb_type == 'none':
            pass  # same footprint as reference

        elif sb_type == 'centered_tiny':
            nfp = [[0]*GRID_Y for _ in range(GRID_X)]
            for x in range(1, GRID_X - 1):
                for y in range(1, GRID_Y - 1):
                    nfp[x][y] = prev[x][y]

        elif sb_type == 'flush_edge_tiny':
            edge = random.choice(['left', 'right', 'top', 'bottom'])
            for x in range(GRID_X):
                for y in range(GRID_Y):
                    if edge == 'left' and x < 1: nfp[x][y] = 0
                    elif edge == 'right' and x >= GRID_X - 1: nfp[x][y] = 0
                    elif edge == 'top' and y >= GRID_Y - 1: nfp[x][y] = 0
                    elif edge == 'bottom' and y < 1: nfp[x][y] = 0

        elif sb_type == 'flush_edge':
            edge = random.choice(['left', 'right', 'top', 'bottom'])
            amt = random.randint(2, 4)
            for x in range(GRID_X):
                for y in range(GRID_Y):
                    if edge == 'left' and x < amt: nfp[x][y] = 0
                    elif edge == 'right' and x >= GRID_X - amt: nfp[x][y] = 0
                    elif edge == 'top' and y >= GRID_Y - amt: nfp[x][y] = 0
                    elif edge == 'bottom' and y < amt: nfp[x][y] = 0

        elif sb_type == 'flush_corner':
            corner = random.choice(['NE', 'NW', 'SE', 'SW'])
            ax = random.randint(1, 3)
            ay = random.randint(1, 3)
            for x in range(GRID_X):
                for y in range(GRID_Y):
                    if corner == 'NE' and (x >= GRID_X - ax or y >= GRID_Y - ay):
                        nfp[x][y] = 0
                    elif corner == 'NW' and (x < ax or y >= GRID_Y - ay):
                        nfp[x][y] = 0
                    elif corner == 'SE' and (x >= GRID_X - ax or y < ay):
                        nfp[x][y] = 0
                    elif corner == 'SW' and (x < ax or y < ay):
                        nfp[x][y] = 0

        elif sb_type == 'centered_shrink':
            nfp = [[0]*GRID_Y for _ in range(GRID_X)]
            for x in range(1, GRID_X - 1):
                for y in range(1, GRID_Y - 1):
                    nfp[x][y] = prev[x][y]

        elif sb_type == 'centered_double':
            nfp = [[0]*GRID_Y for _ in range(GRID_X)]
            for x in range(2, GRID_X - 2):
                for y in range(2, GRID_Y - 2):
                    nfp[x][y] = prev[x][y]

        footprints.append(nfp)

    # Fill voxel grid with zone footprints
    current_z = 0
    zone_transitions = []
    for zone_idx, zone_height in enumerate(zones):
        fp = footprints[min(zone_idx, len(footprints) - 1)]
        for layer in range(zone_height):
            z = current_z + layer
            if z >= GRID_Z:
                break
            for x in range(GRID_X):
                for y in range(GRID_Y):
                    if fp[x][y] == 1:
                        voxel_grid[x][y][z] = 1
        zone_transitions.append(current_z)
        current_z += zone_height

    # --- Step 3: Through-cut with optional split peaks ---
    if random.random() < 0.60:
        axis = random.choice(['x', 'y'])
        if axis == 'x':
            pos = random.randint(3, GRID_X - 4)
        else:
            pos = random.randint(3, GRID_Y - 4)

        # Through-cut start: sometimes from ground, sometimes above podium
        if random.random() < 0.5:
            ch_start = 0
        else:
            ch_start = zones[0]

        # Carve the through-cut
        if axis == 'x':
            for z in range(ch_start, GRID_Z):
                for y in range(GRID_Y):
                    voxel_grid[pos][y][z] = 0
        else:
            for z in range(ch_start, GRID_Z):
                for x in range(GRID_X):
                    voxel_grid[x][pos][z] = 0

        # Split peaks: one side shorter than the other (45% when cut exists)
        if random.random() < 0.45:
            cut_layers = random.randint(3, GRID_Z // 3)
            if axis == 'x':
                if random.random() < 0.5:
                    side_x = range(0, pos)
                else:
                    side_x = range(pos + 1, GRID_X)
                for z in range(GRID_Z - cut_layers, GRID_Z):
                    for x in side_x:
                        for y in range(GRID_Y):
                            voxel_grid[x][y][z] = 0
            else:
                if random.random() < 0.5:
                    side_y = range(0, pos)
                else:
                    side_y = range(pos + 1, GRID_Y)
                for z in range(GRID_Z - cut_layers, GRID_Z):
                    for x in range(GRID_X):
                        for y in side_y:
                            voxel_grid[x][y][z] = 0

    # --- Step 4: Optional large void on a face ---
    if random.random() < 0.30:
        face = random.choice(['x0', 'x_max', 'y0', 'y_max'])
        void_w = random.randint(3, 5)
        void_d = random.randint(2, 3)
        void_start = random.randint(GRID_Z // 5, GRID_Z // 2)
        void_height = random.randint(3, 6)

        if face == 'x0':
            vx, vy = 0, random.randint(0, max(0, GRID_Y - void_d))
        elif face == 'x_max':
            vx, vy = GRID_X - void_w, random.randint(0, max(0, GRID_Y - void_d))
        elif face == 'y0':
            vx, vy = random.randint(0, max(0, GRID_X - void_w)), 0
        else:
            vx, vy = random.randint(0, max(0, GRID_X - void_w)), GRID_Y - void_d

        for z in range(void_start, min(void_start + void_height, GRID_Z)):
            for dx in range(void_w):
                for dy in range(void_d):
                    nx, ny = vx + dx, vy + dy
                    if 0 <= nx < GRID_X and 0 <= ny < GRID_Y:
                        voxel_grid[nx][ny][z] = 0

    # --- Step 5: Optional recessed band at zone transition ---
    if random.random() < 0.25 and len(zone_transitions) > 1:
        band_z = zone_transitions[1]
        if 1 <= band_z < GRID_Z:
            for x in range(GRID_X):
                for y in range(GRID_Y):
                    if x == 0 or x == GRID_X - 1 or y == 0 or y == GRID_Y - 1:
                        voxel_grid[x][y][band_z] = 0

    # --- Step 6: Structural integrity ---
    voxel_grid, removed = ensure_structural_integrity(voxel_grid)
    if removed > 0:
        print(f"  Structural check: removed {removed} disconnected voxels")

    return voxel_grid

# --- MAIN ---
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
print("Images and params saved. Geometry cleaned from memory.")
