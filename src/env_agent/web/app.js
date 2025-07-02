// Variables globales
let map;
let aircraftMarkers = {};
let towerMarkers = {};
let airportMarkers = {};

// Inicializar la aplicación
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    loadAirports();
    startDataUpdates();
});

// Inicializar el mapa
function initializeMap() {
    // Centrar en Buenos Aires
    map = L.map('map').setView([-34.6037, -58.3816], 10);
    
    // Añadir capa de mapa
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    console.log('[MAP] Mapa inicializado');
}

// Cargar aeropuertos
async function loadAirports() {
    try {
        const response = await fetch('/api/airports');
        const airports = await response.json();
        
        // Limpiar marcadores existentes
        Object.values(airportMarkers).forEach(marker => map.removeLayer(marker));
        airportMarkers = {};
        
        // Añadir marcadores de aeropuertos
        for (const [code, airport] of Object.entries(airports)) {
            const marker = L.marker([airport.position.lat, airport.position.lon], {
                icon: L.divIcon({
                    html: '<i class="fas fa-plane-departure" style="color: #17a2b8; font-size: 20px;"></i>',
                    iconSize: [30, 30],
                    className: 'airport-marker'
                })
            }).addTo(map);
            
            marker.bindPopup(`
                <div class="popup-content">
                    <h6><i class="fas fa-plane-departure"></i> ${airport.name}</h6>
                    <p><strong>Código:</strong> ${code}</p>
                    <p><strong>Pistas:</strong> ${airport.runways.join(', ')}</p>
                    <p><strong>Posición:</strong> ${airport.position.lat.toFixed(4)}, ${airport.position.lon.toFixed(4)}</p>
                </div>
            `);
            
            airportMarkers[code] = marker;
        }
        
        updateAirportsCount(Object.keys(airports).length);
        console.log('[DATA] Aeropuertos cargados:', Object.keys(airports).length);
        
    } catch (error) {
        console.error('[ERROR] Error al cargar aeropuertos:', error);
    }
}

// Actualizar datos de aeronaves
async function updateAircraftData() {
    try {
        const response = await fetch('/api/aircraft');
        const aircraft = await response.json();
        
        // Limpiar marcadores existentes
        Object.values(aircraftMarkers).forEach(marker => map.removeLayer(marker));
        aircraftMarkers = {};
        
        // Limpiar tabla
        const tableBody = document.getElementById('aircraft-table');
        tableBody.innerHTML = '';
        
        // Añadir nuevos datos
        for (const [id, data] of Object.entries(aircraft)) {
            if (data.position && data.position.lat && data.position.lon) {
                // Añadir marcador al mapa
                const marker = L.marker([data.position.lat, data.position.lon], {
                    icon: L.divIcon({
                        html: '<i class="fas fa-plane" style="color: #28a745; font-size: 16px;"></i>',
                        iconSize: [30, 30],
                        className: 'aircraft-marker'
                    })
                }).addTo(map);
                
                marker.bindPopup(`
                    <div class="popup-content">
                        <h6><i class="fas fa-plane"></i> ${id}</h6>
                        <p><strong>Altitud:</strong> ${data.altitude || 'N/A'} ft</p>
                        <p><strong>Torre:</strong> ${data.tower || 'N/A'}</p>
                        <p><strong>Posición:</strong> ${data.position.lat.toFixed(4)}, ${data.position.lon.toFixed(4)}</p>
                        <p><strong>Actualizado:</strong> ${new Date(data.timestamp * 1000).toLocaleTimeString()}</p>
                    </div>
                `);
                
                aircraftMarkers[id] = marker;
                
                // Añadir fila a la tabla
                const row = tableBody.insertRow();
                row.innerHTML = `
                    <td><i class="fas fa-plane text-success"></i> ${id}</td>
                    <td>${data.position.lat.toFixed(4)}, ${data.position.lon.toFixed(4)}</td>
                    <td>${data.altitude || 'N/A'} ft</td>
                    <td>${data.tower || 'N/A'}</td>
                `;
            }
        }
        
        updateAircraftCount(Object.keys(aircraft).length);
        console.log('[DATA] Aeronaves actualizadas:', Object.keys(aircraft).length);
        
    } catch (error) {
        console.error('[ERROR] Error al actualizar aeronaves:', error);
    }
}

// Actualizar datos de torres
async function updateTowersData() {
    try {
        const response = await fetch('/api/towers');
        const towers = await response.json();
        
        // Limpiar marcadores existentes
        Object.values(towerMarkers).forEach(marker => map.removeLayer(marker));
        towerMarkers = {};
        
        // Limpiar tabla
        const tableBody = document.getElementById('towers-table');
        tableBody.innerHTML = '';
        
        // Añadir nuevos datos
        for (const [id, data] of Object.entries(towers)) {
            // Añadir fila a la tabla
            const row = tableBody.insertRow();
            const statusClass = data.status === 'active' ? 'status-active' : 'status-inactive';
            const lastUpdate = new Date(data.last_update * 1000).toLocaleTimeString();
            
            row.innerHTML = `
                <td><i class="fas fa-tower-broadcast text-warning"></i> ${id}</td>
                <td>${data.airport || 'N/A'}</td>
                <td><span class="status-indicator ${statusClass}"></span>${data.status}</td>
                <td>${lastUpdate}</td>
            `;
        }
        
        updateTowersCount(Object.keys(towers).length);
        console.log('[DATA] Torres actualizadas:', Object.keys(towers).length);
        
    } catch (error) {
        console.error('[ERROR] Error al actualizar torres:', error);
    }
}

// Funciones de actualización de contadores
function updateAircraftCount(count) {
    document.getElementById('aircraft-count').textContent = count;
}

function updateTowersCount(count) {
    document.getElementById('towers-count').textContent = count;
}

function updateAirportsCount(count) {
    document.getElementById('airports-count').textContent = count;
}

function updateLastUpdate() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString();
}

// Iniciar actualizaciones automáticas
function startDataUpdates() {
    // Actualizar inmediatamente
    updateAircraftData();
    updateTowersData();
    updateLastUpdate();
    
    // Configurar actualizaciones periódicas
    setInterval(() => {
        updateAircraftData();
        updateTowersData();
        updateLastUpdate();
    }, 2000); // Actualizar cada 2 segundos
    
    console.log('[APP] Actualizaciones automáticas iniciadas');
}

// Estilos CSS adicionales para los marcadores
const style = document.createElement('style');
style.textContent = `
    .aircraft-marker {
        background: transparent !important;
        border: none !important;
    }
    
    .airport-marker {
        background: transparent !important;
        border: none !important;
    }
    
    .popup-content {
        font-size: 14px;
    }
    
    .popup-content h6 {
        margin-bottom: 8px;
        color: #333;
    }
    
    .popup-content p {
        margin-bottom: 4px;
        color: #666;
    }
`;
document.head.appendChild(style);
