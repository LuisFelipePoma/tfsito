# Grid-Based Cardinal Movement System

## Overview
This taxi dispatch system has been simplified to use a **grid-based cardinal movement system** where taxis and passengers only move in **four cardinal directions**: up, left, down, and right (no diagonal movement).

## Key Features

### Grid System
- **Grid Size**: 10.0 units per cell
- **Map Bounds**: -40 to +40 in both X and Y directions (9x9 grid)
- **Alignment**: All positions are snapped to grid intersections

### Movement Rules
- **Cardinal Only**: Taxis move only UP, DOWN, LEFT, or RIGHT
- **No Diagonals**: No diagonal movement allowed
- **Grid Snapping**: All positions are automatically aligned to grid points
- **Visual Grid**: The GUI displays the underlying movement grid

### Implementation Details

#### TaxiVisual Class
- `grid_size = 10.0` - Size of each grid cell
- `snap_to_grid()` - Method to align positions to grid
- `_fallback_simple_roaming()` - Cardinal direction movement logic

#### ClientVisual Class
- Clients spawn at grid-aligned positions
- Destinations are also grid-aligned
- Minimum distance of 2 grid cells between client and destination

#### GUI System
- `generate_random_grid_position()` - Creates random grid-aligned positions
- Updated grid drawing to match logical movement grid
- Click-to-add-client snaps to nearest grid point

## Files Removed
The following complex movement files were removed as they're no longer needed:
- `src/agent/libs/intelligent_movement.py` - Complex movement algorithms
- `src/agent/libs/global_optimizer.py` - Global optimization
- `benchmark_agents.py` - Performance benchmarking
- `demo_enhanced_taxi_dispatch.py` - Enhanced demo with complex movement
- Various test files for complex movement features

## Usage
Run the simplified taxi system:
```bash
python demo_taxi_dispatch.py
```

Test the grid movement:
```bash
python test_quick.py
python test_movement_quality.py
```

The system now provides a clean, city-like grid movement where taxis move like they're on city blocks, making the simulation more intuitive and easier to understand.
