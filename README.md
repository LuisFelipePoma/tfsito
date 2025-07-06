# Distributed Ideological Multi-Agent System

A sophisticated distributed multi-agent system using the SPADE framework and Openfire XMPP server, where agents represent individuals with different ideologies that can influence each other and form communities based on constraint programming.

## Features

### Core Agent Capabilities
- **Ideological Beliefs**: Each agent has one of several ideologies (red, blue, green, yellow, purple)
- **Spatial Positioning**: Agents exist in a 2D grid world with configurable dimensions
- **Neighbor Influence**: Agents broadcast their ideology to neighbors within an influence radius
- **Ideology Change**: Agents can change ideology based on local majority influence with constraints
- **Community Formation**: Agents join/leave ideological communities using constraint programming
- **Communication**: All agent interaction via SPADE messaging over XMPP

### Constraint Programming Features
- **Ideology Switch Restrictions**: Agents can only change if >60% of neighbors differ (configurable)
- **Change Cooldown**: Minimum time between ideology changes (3 timesteps default)
- **Community Size Limits**: Maximum and minimum community sizes enforced
- **Community Coherence**: Communities must maintain ideological consistency

### Distributed Architecture
- **Multi-Host Support**: Agents can be distributed across multiple machines
- **Scalable Design**: Supports hundreds to thousands of agents
- **Openfire Integration**: Uses Openfire XMPP server for all communication
- **Automatic Registration**: Bulk agent registration/deletion via Openfire REST API

### Visualization & Monitoring
- **Web Interface**: Real-time visualization of the 2D grid with colored agents
- **Community Display**: Shows community formations and membership
- **Statistics Dashboard**: Tracks ideology distribution, changes, and conflicts
- **Real-time Updates**: Live updates of system state

## System Requirements

- Python 3.8+
- Openfire XMPP Server with REST API plugin
- Docker (for easy Openfire deployment)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd tfsito
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Openfire server:**
   ```bash
   cd src
   docker-compose up -d
   ```

   This starts Openfire with:
   - Admin console: http://localhost:9090 (admin/123)
   - XMPP port: 5222
   - REST API enabled

## Configuration

Key configuration parameters in `src/config.py`:

```python
# Grid dimensions
grid_width: int = 100
grid_height: int = 100

# Ideology system
ideologies = ['red', 'blue', 'green', 'yellow', 'purple']
influence_radius: float = 5.0
ideology_change_threshold: float = 0.6  # 60% of neighbors must differ
ideology_change_cooldown: int = 3  # Time steps between changes

# Community parameters
max_community_size: int = 50
min_community_size: int = 3
community_join_threshold: float = 0.7

# Distributed system
max_agents_per_host: int = 100
broadcast_interval: float = 2.0  # Seconds between broadcasts
```

## Usage

### Single Host Mode

Launch agents on a single host:

```bash
cd src
python main.py --host myhost --agent-count 20 --web
```

Parameters:
- `--host`: Unique identifier for this host
- `--agent-count`: Number of agents to spawn
- `--web`: Enable web interface (available at http://localhost:5000)
- `--openfire-host`: Openfire server hostname (default: localhost)
- `--openfire-port`: Openfire REST API port (default: 9090)

### Distributed Mode

Use the distributed launcher to run across multiple hosts:

```bash
python distributed_launcher.py --total-agents 100 --hosts 4 --openfire-host localhost
```

This will:
1. Distribute 100 agents across 4 host processes
2. Start web interface on the first host
3. Monitor all processes

### Custom Configuration

Create a JSON configuration file for custom setups:

```json
[
    {"host_id": "datacenter1", "agent_count": 50},
    {"host_id": "datacenter2", "agent_count": 30},
    {"host_id": "edge_node", "agent_count": 20}
]
```

Then launch with:
```bash
python distributed_launcher.py --config custom_config.json
```

## Web Interface

The web interface provides:

- **Real-time Grid Visualization**: 2D view with colored agents by ideology
- **Community Overlay**: Visual representation of community boundaries
- **Statistics Panel**: Live metrics including:
  - Total agents and communities
  - Ideology distribution
  - Number of ideology changes
  - Last update timestamp
- **Interactive Controls**: Refresh, auto-update toggle, view controls

Access at: http://localhost:5000 (when `--web` flag is used)

## Agent Behavior

### Ideology Broadcasting
- Agents periodically broadcast their current ideology to all neighbors
- Broadcast interval configurable (default: 2 seconds)
- Messages include position, ideology, community membership

### Decision Making
Agents use constraint programming to make decisions:

1. **Ideology Change Evaluation**:
   - Calculate ideology distribution among neighbors within influence radius
   - Check if >60% of neighbors have different ideology
   - Verify cooldown period has passed (3 timesteps minimum)
   - Select most popular different ideology among neighbors

2. **Community Management**:
   - Try to join communities of same ideology
   - Form new communities when enough like-minded neighbors exist
   - Leave communities that become too small or ideologically inconsistent
   - Respect maximum community size constraints

### Constraint Programming

The system uses OR-Tools for constraint satisfaction:

- **Ideology Constraints**: Enforces cooldown periods and threshold requirements
- **Community Optimization**: Minimizes number of communities while respecting size and coherence constraints
- **Spatial Constraints**: Considers neighbor proximity for influence calculations

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Host 1      │    │     Host 2      │    │     Host N      │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Agent 1-20  │ │    │ │ Agent 21-40 │ │    │ │ Agent N-M   │ │
│ │             │ │    │ │             │ │    │ │             │ │
│ │ Ideology    │ │    │ │ Ideology    │ │    │ │ Ideology    │ │
│ │ Constraints │ │    │ │ Constraints │ │    │ │ Constraints │ │
│ │ Communities │ │    │ │ Communities │ │    │ │ Communities │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    └─────────────────┘    └─────────────────┘
│ │ GUI Agent   │ │             │                       │
│ │ Web Interface│ │             │                       │
│ └─────────────┘ │             │                       │
└─────────────────┘             │                       │
         │                      │                       │
         └──────────────────────┼───────────────────────┘
                                │
                   ┌─────────────────┐
                   │ Openfire XMPP   │
                   │ Server          │
                   │                 │
                   │ - Message Bus   │
                   │ - User Registry │
                   │ - REST API      │
                   └─────────────────┘
```

## Scaling Considerations

### Performance Optimizations
- Agents use efficient neighbor discovery within influence radius
- Constraint solving is cached and optimized
- Web interface uses polling rather than real-time streaming
- Openfire handles message routing and delivery

### Distributed Deployment
- Each host can run independently
- Agents automatically discover each other via XMPP
- No central coordination required beyond Openfire
- Horizontal scaling by adding more hosts

### Resource Requirements
- ~10-50 MB RAM per 100 agents
- Minimal CPU usage during steady state
- Network bandwidth scales with agent density and broadcast frequency

## Troubleshooting

### Common Issues

1. **Openfire Connection Failed**
   - Verify Openfire is running: `docker ps`
   - Check admin console: http://localhost:9090
   - Ensure REST API plugin is enabled

2. **Agents Not Communicating**
   - Check XMPP port (5222) is accessible
   - Verify agent registration in Openfire admin console
   - Check firewall settings for XMPP traffic

3. **Web Interface Not Loading**
   - Ensure Flask dependencies are installed
   - Check if port 5000 is available
   - Verify GUI agent is running

4. **High Memory Usage**
   - Reduce agent count per host
   - Increase broadcast intervals
   - Monitor with system tools

### Logs

Application logs are written to:
- Console output (INFO level)
- `simulation.log` file (detailed logs)

Enable debug logging by modifying the logging level in `main.py`.

## Example Scenarios

### Small Test (10 agents, single host)
```bash
python main.py --host test --agent-count 10 --web
```

### Medium Simulation (100 agents, 3 hosts)
```bash
python distributed_launcher.py --total-agents 100 --hosts 3
```

### Large Scale (1000 agents, 10 hosts)
```bash
python distributed_launcher.py --total-agents 1000 --hosts 10
```

## Development

### Adding New Ideologies
1. Update `config.py` ideologies list
2. Add colors to web interface CSS/JavaScript
3. Test with different distributions

### Custom Constraint Rules
1. Extend `IdeologyConstraintSolver` class
2. Add new constraint types in `ideology_constraints.py`
3. Update agent decision-making logic

### New Agent Behaviors
1. Create new behavior classes in `ideological_agent.py`
2. Add to agent setup routine
3. Implement constraint validation

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request
